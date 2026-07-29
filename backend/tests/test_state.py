from agents.state import TaskState, current_objective


def test_task_state_has_required_keys():
    required_keys = [
        "task_id", "query", "formatting_guidelines",
        "data_descriptions", "cumulative_plan",
        "current_script", "execution_result", "exit_code",
        "current_round", "max_rounds", "verifier_verdict",
        "router_decision", "status", "final_result"
    ]
    annotations = TaskState.__annotations__
    for key in required_keys:
        assert key in annotations, f"Missing key: {key}"


def test_task_state_types():
    annotations = TaskState.__annotations__
    assert annotations["task_id"] == str
    assert annotations["current_round"] == int
    assert annotations["cumulative_plan"] == list
    assert annotations["data_descriptions"] == dict


def test_current_objective_falls_back_to_query_in_qa_mode():
    """No sub_questions at all (plain QA mode) — must return the top-level query
    unchanged, same behavior as before current_objective() existed."""
    state = {"query": "What is the total transaction volume?"}
    assert current_objective(state) == "What is the total transaction volume?"


def test_current_objective_falls_back_to_query_when_sub_questions_exhausted():
    state = {
        "query": "Top-level query",
        "sub_questions": ["Sub-question 1?"],
        "current_sub_idx": 1,
    }
    assert current_objective(state) == "Top-level query"


def test_current_objective_returns_current_sub_question_in_report_mode():
    """Regression test: planner/verifier/router_agent used to always read state["query"]
    here, ignoring which sub-question was actually being worked on — every sub-question's
    mini-pipeline ran against the same top-level query."""
    state = {
        "query": "Top-level query",
        "sub_questions": ["Sub-question 1?", "Sub-question 2?", "Sub-question 3?"],
        "current_sub_idx": 1,
    }
    assert current_objective(state) == "Sub-question 2?"