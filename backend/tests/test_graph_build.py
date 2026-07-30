import pytest
from agents.graph import build_graph, _cancellable, _is_retryable
from agents.cancellation import request_stop, request_pause, clear, TaskCancelled, TaskPaused, AwaitingReview


def test_graph_builds_without_error():
    graph = build_graph()
    assert "analyzer" in graph.nodes
    assert "finalizer" in graph.nodes


def test_every_node_has_a_retry_policy_configured():
    """A connection timeout, a Docker daemon hiccup, or any other transient failure in
    any single node shouldn't fail the whole task outright — see _is_retryable below for
    the one deliberate carve-out."""
    graph = build_graph()
    for name, node in graph.nodes.items():
        if name == "__start__":
            continue
        assert node.retry_policy, f"node {name!r} has no retry_policy configured"


@pytest.mark.parametrize("exc", [
    RuntimeError("llm_router gave up after retries"),
    ConnectionError("connection reset"),
    TimeoutError("timed out"),
    OSError("docker daemon unreachable"),
    ValueError("something unrelated"),
])
def test_is_retryable_true_for_ordinary_failures(exc):
    assert _is_retryable(exc) is True


@pytest.mark.parametrize("exc", [
    TaskCancelled("stopped by user"),
    TaskPaused("paused by user"),
    AwaitingReview("awaiting human review"),
])
def test_is_retryable_false_for_deliberate_control_flow_signals(exc):
    """Retrying a Stop/Pause/awaiting-review isn't a safety net — it would just
    re-raise the same signal again after a pointless delay."""
    assert _is_retryable(exc) is False


def test_a_node_that_fails_once_then_succeeds_is_retried_transparently():
    """Exercises the actual retry mechanism end-to-end (not just that a policy object is
    attached) — a minimal throwaway graph rather than the full build_graph(), and a
    near-zero interval rather than production's 1s, so this stays fast."""
    from langgraph.graph import StateGraph, END
    from langgraph.types import RetryPolicy

    calls = {"n": 0}

    def flaky(state):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("transient network blip")
        return {"result": "ok"}

    fast_policy = RetryPolicy(retry_on=_is_retryable, max_attempts=2, initial_interval=0.01, backoff_factor=1.0)
    builder = StateGraph(dict)
    builder.add_node("flaky", flaky, retry_policy=fast_policy)
    builder.set_entry_point("flaky")
    builder.add_edge("flaky", END)
    graph = builder.compile()

    result = graph.invoke({})

    assert result == {"result": "ok"}
    assert calls["n"] == 2   # failed once, succeeded on the retry


def test_a_stop_signal_is_not_retried_even_though_it_is_an_exception():
    from langgraph.graph import StateGraph, END
    from langgraph.types import RetryPolicy

    calls = {"n": 0}

    def stopped(state):
        calls["n"] += 1
        raise TaskCancelled("stopped by user")

    fast_policy = RetryPolicy(retry_on=_is_retryable, max_attempts=3, initial_interval=0.01, backoff_factor=1.0)
    builder = StateGraph(dict)
    builder.add_node("stopped", stopped, retry_policy=fast_policy)
    builder.set_entry_point("stopped")
    builder.add_edge("stopped", END)
    graph = builder.compile()

    with pytest.raises(TaskCancelled):
        graph.invoke({})

    assert calls["n"] == 1   # never retried


def test_cancellable_raises_before_calling_the_wrapped_node_when_stopped():
    """The Stop button's whole mechanism: every node in the graph is wrapped with this,
    so a stopped task never runs another node's actual work, regardless of which node it
    currently is."""
    calls = []
    def fake_node(state):
        calls.append(state)
        return {}

    wrapped = _cancellable(fake_node)
    request_stop("task-cancel-test")
    try:
        with pytest.raises(TaskCancelled):
            wrapped({"task_id": "task-cancel-test"})
    finally:
        clear("task-cancel-test")

    assert calls == []  # the real node body must never have run


def test_cancellable_raises_task_paused_before_calling_the_wrapped_node_when_paused():
    """Pause's mechanism: same interception point as Stop, but a distinguishable
    exception so run_graph can tell "stop permanently" from "resumable pause" apart."""
    calls = []
    def fake_node(state):
        calls.append(state)
        return {}

    wrapped = _cancellable(fake_node)
    request_pause("task-pause-test")
    try:
        with pytest.raises(TaskPaused):
            wrapped({"task_id": "task-pause-test"})
    finally:
        clear("task-pause-test")

    assert calls == []


def test_cancellable_calls_the_wrapped_node_when_not_stopped():
    calls = []
    def fake_node(state):
        calls.append(state)
        return {"result": "ok"}

    wrapped = _cancellable(fake_node)
    result = wrapped({"task_id": "task-not-cancelled"})

    assert result == {"result": "ok"}
    assert len(calls) == 1


def test_graph_wires_the_key_report_mode_transitions():
    """The node-existence check above would pass even if edges were wired wrong (e.g.
    sub_result_collector never actually routed to writer) — the transitions below are
    what turn a sequence of nodes into the DS-STAR+ report loop and are worth protecting
    directly, not just implicitly through a full pipeline run."""
    edges = {(e.source, e.target) for e in build_graph().get_graph().edges}

    assert ("analyzer", "question_generator") in edges
    assert ("question_generator", "planner") in edges
    assert ("verifier", "sub_result_collector") in edges
    assert ("sub_result_collector", "planner") in edges
    assert ("sub_result_collector", "writer") in edges
    assert ("writer", "report_evaluator") in edges
    assert ("writer", "report_finalizer") in edges
    assert ("report_evaluator", "gap_question_generator") in edges
    assert ("gap_question_generator", "planner") in edges
    assert ("report_evaluator", "report_finalizer") in edges
    assert ("report_finalizer", "__end__") in edges
    # Opt-in human-in-the-loop refine-vs-finalize checkpoint (see route_after_report_evaluator)
    assert ("report_evaluator", "human_review_gate") in edges
    assert ("human_review_gate", "report_finalizer") in edges
    assert ("human_review_gate", "gap_question_generator") in edges


def test_graph_wires_the_key_qa_mode_transitions():
    edges = {(e.source, e.target) for e in build_graph().get_graph().edges}

    assert ("analyzer", "planner") in edges
    assert ("planner", "coder") in edges
    assert ("coder", "executor") in edges
    assert ("executor", "debugger") in edges
    assert ("executor", "verifier") in edges
    assert ("executor", "finalizer") in edges
    assert ("debugger", "executor") in edges
    assert ("verifier", "router_agent") in edges
    assert ("verifier", "finalizer") in edges
    assert ("router_agent", "planner") in edges
    assert ("finalizer", "__end__") in edges
