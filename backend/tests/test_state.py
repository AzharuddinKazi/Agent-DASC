from agents.state import TaskState


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