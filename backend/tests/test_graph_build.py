import pytest
from agents.graph import build_graph, _cancellable
from agents.cancellation import request_stop, request_pause, clear, TaskCancelled, TaskPaused


def test_graph_builds_without_error():
    graph = build_graph()
    assert "analyzer" in graph.nodes
    assert "finalizer" in graph.nodes


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
