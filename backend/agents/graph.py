from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy
from agents.state import TaskState
from agents.analyzer import analyzer
from agents.planner import planner
from agents.coder import coder
from agents.executor import executor
from agents.verifier import verifier
from agents.router_agent import router_agent
from agents.debugger import debugger
from agents.finalizer import finalizer
from agents.question_generator import question_generator
from agents.writer import writer
from agents.report_evaluator import report_evaluator
from agents.logger import log_event
from agents.cancellation import check_interrupt, AwaitingReview, get_review_decision, TaskCancelled, TaskPaused
import json


# ── DS-STAR QA routing ────────────────────────────────────────────────────────

def route_after_analyzer(state: TaskState) -> str:
    """After analyzing data: branch into QA or DS-STAR+ report mode."""
    if state.get("task_type") == "report":
        return "question_generator"
    return "planner"


def route_after_executor(state: TaskState) -> str:
    if state["exit_code"] != 0:
        if state.get("debug_attempts", 0) < 2:
            return "debugger"
        return "finalizer"
    return "verifier"


def route_after_debugger(state: TaskState) -> str:
    return "executor"


def route_after_verifier(state: TaskState) -> str:
    if state["verifier_verdict"] == "sufficient":
        # In report mode, store result and move to next sub-question
        if state.get("task_type") == "report":
            return "sub_result_collector"
        return "finalizer"
    if state["current_round"] >= state["max_rounds"]:
        if state.get("task_type") == "report":
            return "sub_result_collector"
        return "finalizer"
    return "router_agent"


def route_after_router(state: TaskState) -> str:
    return "planner"


# ── DS-STAR+ report routing ───────────────────────────────────────────────────

def sub_result_collector(state: TaskState) -> dict:
    """Store the current sub-question result and prepare state for the next one."""
    from db import supabase

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    sub_results     = dict(state.get("sub_results", {}))

    # Parse and store the result for the current sub-question
    current_q = sub_questions[current_sub_idx] if current_sub_idx < len(sub_questions) else None
    if current_q:
        raw = state.get("final_result") or state.get("execution_result", "")
        parsed = {}
        try:
            s = raw.strip()
            if s.startswith("```"):
                import re
                s = re.sub(r"^```[a-z]*\n?", "", s).rstrip("`").strip()
            candidate = json.loads(s)
            # A script that prints a bare number/string (e.g. "71.55") is valid JSON but
            # not a dict — writer.py's sr.get("summary", ...) crashes with AttributeError
            # on anything else, so only accept genuinely dict-shaped results here.
            if not isinstance(candidate, dict):
                raise ValueError("parsed JSON is not an object")
            parsed = candidate
        except Exception:
            parsed = {"summary": raw, "key_findings": [], "columns": [], "rows": []}
        sub_results[current_q] = parsed

    next_idx = current_sub_idx + 1

    supabase.table("tasks").update({
        "current_agent": f"sub_result_{current_sub_idx + 1}_of_{len(sub_questions)}"
    }).eq("task_id", state["task_id"]).execute()

    if current_q:
        log_event(state["task_id"], "sub_result_collector",
                  f"✓ Sub-Q {current_sub_idx + 1}/{len(sub_questions)} complete — '{current_q[:80]}'",
                  "success",
                  {"sub_q_idx": current_sub_idx + 1, "sub_q_total": len(sub_questions), "sub_q_text": current_q})

    return {
        "sub_results":      sub_results,
        "current_sub_idx":  next_idx,
        # Reset QA pipeline state for the next sub-question
        "cumulative_plan":  [],
        "current_script":   "",
        "execution_result": "",
        "exit_code":        0,
        "debug_attempts":   0,
        "current_round":    0,
        "verifier_verdict": "",
        "router_decision":  "",
        "final_result":     None,
    }


def route_after_sub_collector(state: TaskState) -> str:
    """After collecting a sub-result: run next sub-question or move to Writer."""
    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)

    if current_sub_idx < len(sub_questions):
        return "planner"   # Process next sub-question
    return "writer"        # All done — generate report


def route_after_writer(state: TaskState) -> str:
    max_rounds = state.get("max_report_rounds", 2)
    if state.get("report_rounds", 0) >= max_rounds:
        return "report_finalizer"
    return "report_evaluator"


def route_after_report_evaluator(state: TaskState) -> str:
    max_rounds = state.get("max_report_rounds", 2)
    at_round_limit = state.get("report_rounds", 0) >= max_rounds

    # Opt-in paper-fidelity checkpoint: let a human pick refine-vs-finalize instead of
    # trusting report_evaluator's LLM verdict automatically — but only when refining is
    # actually still a real choice. At the round limit there's nothing to decide (refine
    # isn't an option), so skip straight to finalizing exactly like the automatic path.
    if state.get("require_human_review") and not at_round_limit:
        return "human_review_gate"

    if state.get("report_verdict") == "sufficient":
        return "report_finalizer"
    if at_round_limit:
        return "report_finalizer"
    # Add gap sub-questions and loop
    return "gap_question_generator"


def route_after_human_review_gate(state: TaskState) -> str:
    if state.get("human_review_decision") == "refine":
        return "gap_question_generator"
    return "report_finalizer"


def human_review_gate(state: TaskState) -> dict:
    """Opt-in checkpoint between report_evaluator and finalize/refine (see
    route_after_report_evaluator). get_review_decision pops the decision recorded via
    POST /api/v1/tasks/{id}/review — None means nobody's answered yet for this round, so
    raise AwaitingReview to unwind graph.invoke() the same way a Pause does (the
    checkpointer already durably holds state as of report_evaluator's last completed
    run). Once a decision is recorded, main.py's run_graph resumes with
    initial_state=None, which replays this node from scratch — this time it finds the
    decision and returns normally."""
    from db import supabase

    decision = get_review_decision(state["task_id"])
    if decision is None:
        supabase.table("tasks").update({"current_agent": "human_review_gate"}).eq("task_id", state["task_id"]).execute()
        log_event(state["task_id"], "human_review_gate",
                  "Awaiting your decision — refine further or finalize the report",
                  "info", {
                      "verdict": state.get("report_verdict"),
                      "gaps":    state.get("report_gaps"),
                      "round":   state.get("report_rounds", 0),
                  })
        raise AwaitingReview(f"Task {state['task_id']} awaiting human review decision")

    log_event(state["task_id"], "human_review_gate", f"Reviewer chose: {decision}", "success")
    return {"human_review_decision": decision}


def gap_question_generator(state: TaskState) -> dict:
    """Add new sub-questions for identified gaps and loop back through DS-STAR.

    report_evaluator.gaps is a list of {"question", "hypothesis"} objects (structured the
    same way as question_generator's output) so a follow-up hypothesis genuinely continues
    the narrative arc instead of bolting on an unrelated topic — see current_objective() in
    state.py for why the hypothesis needs to travel with its question, not just get logged.
    """
    from db import supabase
    gaps          = state.get("report_gaps", [])
    sub_questions = list(state.get("sub_questions", []))
    hypotheses    = dict(state.get("hypotheses", {}))
    sub_question_rounds = dict(state.get("sub_question_rounds", {}))

    # report_rounds was already bumped by report_evaluator's return value before this node
    # runs, so it's exactly the refine-round number these new sub-questions belong to (1 for
    # the first refine loop, 2 for the second, ...) — see writer.py's citation labeling.
    round_num = state.get("report_rounds", 0)

    new_qs = []
    for gap in gaps:
        q = gap["question"] if "?" in gap["question"] else f"{gap['question']}?"
        new_qs.append(q)
        sub_question_rounds[q] = round_num
        if gap.get("hypothesis"):
            hypotheses[q] = gap["hypothesis"]
    sub_questions.extend(new_qs)

    new_hypotheses = {q: hypotheses[q] for q in new_qs if q in hypotheses}
    supabase.table("tasks").update({"current_agent": "gap_question_generator"}).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "gap_question_generator",
              f"Identified {len(gaps)} gap(s) — adding {len(new_qs)} new sub-question(s)",
              "info", {"gaps": gaps, "new_questions": new_qs, "hypotheses": new_hypotheses})

    return {
        "sub_questions":       sub_questions,
        "hypotheses":          hypotheses,
        "sub_question_rounds": sub_question_rounds,
        "cumulative_plan": [],
        "current_script":  "",
        "execution_result": "",
        "exit_code":       0,
        "debug_attempts":  0,
        "current_round":   0,
        "verifier_verdict": "",
        "router_decision": "",
        "final_result":    None,
    }


def report_finalizer(state: TaskState) -> dict:
    """Store the final report in Supabase as the task's final_result."""
    from db import supabase
    draft = state.get("draft_report", "{}")
    supabase.table("tasks").update({
        "current_agent": "report_finalizer",
        "final_result":  draft,
    }).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "report_finalizer", "Report finalised ✓", "success")

    return {"final_result": draft, "status": "completed"}


# ── Graph builder ─────────────────────────────────────────────────────────────

def _is_retryable(exc: Exception) -> bool:
    """Retry a failed node for anything — a connection timeout, a Docker daemon hiccup,
    an LLM call that exhausted llm_router's own internal retries — except our own
    deliberate control-flow signals. Stop/Pause/awaiting-review aren't failures, so
    retrying them would just re-raise the same signal after a pointless delay."""
    return not isinstance(exc, (TaskCancelled, TaskPaused, AwaitingReview))


# Conservative on top of llm_router's own internal retries (2 retries with exponential
# backoff before it gives up and raises) — this is a safety net for whatever gets past
# that, not the primary retry mechanism, so one retry here is enough.
NODE_RETRY_POLICY = RetryPolicy(retry_on=_is_retryable, max_attempts=2, initial_interval=1.0, backoff_factor=2.0)


def _cancellable(fn):
    """Checks for a Stop or Pause request before running a node — see cancellation.py.
    Applied to every node uniformly here (not scattered across each agent file) since
    every node function has the same (state: TaskState) -> dict signature."""
    def wrapped(state):
        check_interrupt(state["task_id"])
        return fn(state)
    wrapped.__name__ = getattr(fn, "__name__", "node")
    return wrapped


def build_graph(checkpointer=None):
    builder = StateGraph(TaskState)

    # ── DS-STAR base nodes ────────────────────────────────────────────────────
    builder.add_node("analyzer",          _cancellable(analyzer),          retry_policy=NODE_RETRY_POLICY)
    builder.add_node("planner",           _cancellable(planner),           retry_policy=NODE_RETRY_POLICY)
    builder.add_node("coder",             _cancellable(coder),             retry_policy=NODE_RETRY_POLICY)
    builder.add_node("executor",          _cancellable(executor),          retry_policy=NODE_RETRY_POLICY)
    builder.add_node("verifier",          _cancellable(verifier),          retry_policy=NODE_RETRY_POLICY)
    builder.add_node("router_agent",      _cancellable(router_agent),      retry_policy=NODE_RETRY_POLICY)
    builder.add_node("debugger",          _cancellable(debugger),          retry_policy=NODE_RETRY_POLICY)
    builder.add_node("finalizer",         _cancellable(finalizer),         retry_policy=NODE_RETRY_POLICY)

    # ── DS-STAR+ nodes ────────────────────────────────────────────────────────
    builder.add_node("question_generator",   _cancellable(question_generator),   retry_policy=NODE_RETRY_POLICY)
    builder.add_node("sub_result_collector", _cancellable(sub_result_collector), retry_policy=NODE_RETRY_POLICY)
    builder.add_node("writer",               _cancellable(writer),               retry_policy=NODE_RETRY_POLICY)
    builder.add_node("report_evaluator",     _cancellable(report_evaluator),     retry_policy=NODE_RETRY_POLICY)
    builder.add_node("gap_question_generator", _cancellable(gap_question_generator), retry_policy=NODE_RETRY_POLICY)
    builder.add_node("human_review_gate",    _cancellable(human_review_gate),    retry_policy=NODE_RETRY_POLICY)
    builder.add_node("report_finalizer",     _cancellable(report_finalizer),     retry_policy=NODE_RETRY_POLICY)

    # ── Entry ─────────────────────────────────────────────────────────────────
    builder.set_entry_point("analyzer")

    # Analyzer branches: QA → planner, Report → question_generator
    builder.add_conditional_edges(
        "analyzer",
        route_after_analyzer,
        {"planner": "planner", "question_generator": "question_generator"}
    )

    # ── DS-STAR QA loop ───────────────────────────────────────────────────────
    builder.add_edge("planner",  "coder")
    builder.add_edge("coder",    "executor")

    builder.add_conditional_edges(
        "executor",
        route_after_executor,
        {"debugger": "debugger", "verifier": "verifier", "finalizer": "finalizer"}
    )

    builder.add_conditional_edges(
        "debugger",
        route_after_debugger,
        {"executor": "executor"}
    )

    builder.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "finalizer":          "finalizer",
            "router_agent":       "router_agent",
            "sub_result_collector": "sub_result_collector",
        }
    )

    builder.add_conditional_edges(
        "router_agent",
        route_after_router,
        {"planner": "planner"}
    )

    builder.add_edge("finalizer", END)

    # ── DS-STAR+ report loop ──────────────────────────────────────────────────
    builder.add_edge("question_generator", "planner")  # first sub-question → planner

    builder.add_conditional_edges(
        "sub_result_collector",
        route_after_sub_collector,
        {"planner": "planner", "writer": "writer"}
    )

    builder.add_conditional_edges(
        "writer",
        route_after_writer,
        {"report_evaluator": "report_evaluator", "report_finalizer": "report_finalizer"}
    )

    builder.add_conditional_edges(
        "report_evaluator",
        route_after_report_evaluator,
        {
            "report_finalizer":      "report_finalizer",
            "gap_question_generator": "gap_question_generator",
            "human_review_gate":     "human_review_gate",
        }
    )

    builder.add_conditional_edges(
        "human_review_gate",
        route_after_human_review_gate,
        {
            "report_finalizer":       "report_finalizer",
            "gap_question_generator": "gap_question_generator",
        }
    )

    builder.add_edge("gap_question_generator", "planner")
    builder.add_edge("report_finalizer", END)

    return builder.compile(checkpointer=checkpointer)
