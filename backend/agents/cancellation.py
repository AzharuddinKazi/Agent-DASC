"""Cooperative task interruption (Stop and Pause) via graph-node boundary checks.

There's no clean way to forcibly kill a Python thread running a synchronous
`graph.invoke()` call (the pattern main.py's run_graph() uses via run_in_executor), so
interruption here is cooperative: a task_id gets flagged, and each graph node checks the
flag before running — see graph.py's `_cancellable` wrapper — raising a distinguishing
exception to unwind out of graph.invoke() through run_in_executor to run_graph()'s
exception handler.

That alone bounds the delay to "however long the currently-running node takes," which is
fine for LLM-call nodes (seconds) but not for the Docker-executing node, which can block
up to 120s on a single script — executor.py's execute_script() additionally polls both
flags while its subprocess runs and force-kills the container, so a stop/pause mid-
execution takes effect in under a second rather than up to two minutes.

Stop vs Pause both interrupt the same way; they differ only in what happens after:
- Stop (TaskCancelled): run_graph marks the task "stopped", permanently. Nothing resumes.
- Pause (TaskPaused): run_graph marks the task "paused". LangGraph's checkpointer (see
  main.py's lifespan — this only works now that the checkpointer is actually kept alive
  and passed into build_graph(), which it previously wasn't) has already durably saved
  the state as of the last node that *completed* before the pause was noticed — the
  interrupted node's own work never happened, since _cancellable raises before calling
  it, not after. Resuming (`graph.invoke(None, config)` with the same thread_id) replays
  from that checkpoint, re-running the interrupted node from scratch and continuing on.
  This is "restart the in-flight step," a deliberate simplicity choice over trying to
  losslessly freeze/resume mid-step work (e.g. a half-finished LLM completion or Docker
  script) — verified empirically that LangGraph's checkpoint-per-completed-superstep
  behavior supports exactly this resume shape.

Module-level, in-process state — correct as long as this runs as a single worker process
(true here: `uvicorn main:app` with no --workers flag). A multi-worker deployment would
need this in Postgres/Redis instead, since each worker would have its own copy.
"""

_cancelled: set[str] = set()
_paused: set[str] = set()

# Pending human decisions for the report-mode refine-vs-finalize checkpoint (see
# graph.py's human_review_gate). Same module-level, in-process pattern and the same
# single-worker-process caveat as _cancelled/_paused above — not durable across a
# multi-worker deployment, but this codebase runs `uvicorn main:app` with no --workers.
_review_decisions: dict[str, str] = {}


class TaskCancelled(Exception):
    """Raised from within a graph node to unwind a stopped task's graph.invoke() call."""


class TaskPaused(Exception):
    """Raised from within a graph node to unwind a paused task's graph.invoke() call,
    leaving its last checkpoint intact for a later resume."""


class AwaitingReview(Exception):
    """Raised from human_review_gate to unwind a report-mode task's graph.invoke() call
    when require_human_review is set and no decision has been recorded yet for the
    current round. Same unwind mechanism as TaskPaused (the checkpointer already holds
    state as of report_evaluator's last completed run), but a distinct exception so
    main.py's run_graph can set a distinct status ("awaiting_review" vs "paused") — the
    two differ in what makes them resumable: a plain Pause just needs a Resume call, this
    needs an actual decision (see record_review_decision/get_review_decision)."""


def request_stop(task_id: str) -> None:
    _cancelled.add(task_id)


def request_pause(task_id: str) -> None:
    _paused.add(task_id)


def is_cancelled(task_id: str) -> bool:
    return task_id in _cancelled


def is_paused(task_id: str) -> bool:
    return task_id in _paused


def record_review_decision(task_id: str, decision: str) -> None:
    _review_decisions[task_id] = decision


def get_review_decision(task_id: str) -> str | None:
    """Pops the recorded decision (if any) — a decision is consumed exactly once, so the
    *next* round's human_review_gate visit finds nothing recorded and pauses fresh again,
    with no separate reset step needed."""
    return _review_decisions.pop(task_id, None)


def check_interrupt(task_id: str) -> None:
    """Checked at the top of every graph node (via _cancellable) and inside
    execute_script()'s Docker-polling loop. Stop takes priority over Pause on the rare
    chance both were requested — a permanent stop is a stronger signal than a pause."""
    if is_cancelled(task_id):
        raise TaskCancelled(f"Task {task_id} was stopped by the user")
    if is_paused(task_id):
        raise TaskPaused(f"Task {task_id} was paused by the user")


def clear(task_id: str) -> None:
    """Called in run_graph's `finally` for every outcome — success, stop, pause, or a
    genuine error. Clearing the pause flag here (not just on stop) is required, not just
    tidy: the flag's job is "make the current run stop soon," and once that run has
    actually stopped, a future run (resume) must start unflagged, or it would immediately
    re-raise TaskPaused on its very first node and never make progress. Also caps the
    in-memory sets from growing unboundedly over the process's lifetime."""
    _cancelled.discard(task_id)
    _paused.discard(task_id)
    _review_decisions.pop(task_id, None)
