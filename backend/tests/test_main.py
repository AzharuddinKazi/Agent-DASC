from dataclasses import dataclass
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app, _reconcile_orphaned_tasks
from auth import get_current_user

client = TestClient(app)


@dataclass
class FakeUser:
    id: str = "00000000-0000-0000-0000-000000000001"


app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_health_check():
    """Mocks all three dependency pings — /health legitimately returns 503 when a real
    dependency is unreachable (by design), so asserting 200 unconditionally means this
    test was accidentally dependent on live Supabase/Gemini/Docker being reachable.
    """
    with patch("main.supabase") as mock_sb, \
         patch("main.requests.get") as mock_llm_get, \
         patch("main.subprocess.run") as mock_docker:
        mock_sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        mock_llm_get.return_value = MagicMock(raise_for_status=MagicMock())
        mock_docker.return_value = MagicMock()

        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["docker"]["status"] == "ok"
    assert body["checks"]["llm"]["status"] == "ok"


def test_submit_task_returns_task_id():
    mock_result = MagicMock()
    mock_result.data = [{"task_id": "123"}]

    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/submit_task", json={
            "query": "What is the total transaction volume?",
            "formatting_guidelines": "Return a number"
        })

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "running"
    assert data["query"] == "What is the total transaction volume?"
    assert data["require_human_review"] is False  # opt-in flag defaults off


def test_submit_task_echoes_require_human_review_when_set():
    mock_result = MagicMock()
    mock_result.data = [{"task_id": "123"}]

    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/submit_task", json={
            "query": "Summarise fraud risk across entities",
            "task_type": "report",
            "require_human_review": True,
        })

    assert response.status_code == 202
    assert response.json()["require_human_review"] is True


def test_clarify_task_returns_questions():
    with patch("main.generate_clarifying_questions") as mock_generate:
        mock_generate.return_value = [
            {"question": "Which timeframe?", "header": "Timeframe",
             "options": [{"label": "30d", "description": ""}, {"label": "90d", "description": ""}]}
        ]
        response = client.post("/api/v1/clarify_task", json={
            "query": "How are recent sales trending?",
            "task_type": "qa",
        })

    assert response.status_code == 200
    body = response.json()
    assert len(body["questions"]) == 1
    mock_generate.assert_called_once_with("How are recent sales trending?", "qa", None)


def test_clarify_task_returns_empty_list_when_unambiguous():
    with patch("main.generate_clarifying_questions", return_value=[]):
        response = client.post("/api/v1/clarify_task", json={"query": "Row count in transactions.csv?"})

    assert response.status_code == 200
    assert response.json() == {"questions": []}


def test_clarify_task_normalizes_invalid_task_type_to_qa():
    with patch("main.generate_clarifying_questions") as mock_generate:
        mock_generate.return_value = []
        client.post("/api/v1/clarify_task", json={"query": "test", "task_type": "not-a-real-mode"})

    mock_generate.assert_called_once_with("test", "qa", None)


def test_clarify_task_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/api/v1/clarify_task", json={"query": "test"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_stop_task_requests_cancellation_for_a_running_task():
    mock_result = MagicMock()
    mock_result.data = [{"status": "running"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.request_stop") as mock_request_stop, \
         patch("main.log_event"):
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/task-123/stop")

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-123", "status": "stopping"}
    mock_request_stop.assert_called_once_with("task-123")


def test_stop_task_returns_404_when_task_not_found_or_not_owned():
    mock_result = MagicMock()
    mock_result.data = []

    with patch("main.supabase") as mock_sb, \
         patch("main.request_stop") as mock_request_stop:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/nonexistent/stop")

    assert response.status_code == 404
    mock_request_stop.assert_not_called()


def test_stop_task_returns_409_when_task_is_not_running():
    mock_result = MagicMock()
    mock_result.data = [{"status": "completed"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.request_stop") as mock_request_stop:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/task-123/stop")

    assert response.status_code == 409
    mock_request_stop.assert_not_called()


def test_stop_task_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/api/v1/tasks/task-123/stop")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_stop_task_stops_directly_when_awaiting_review():
    """No in-flight graph.invoke() to cooperatively interrupt while parked at
    human_review_gate — must stop directly, not via request_stop (which only takes
    effect the next time the graph actually runs, which may be never)."""
    mock_result = MagicMock()
    mock_result.data = [{"status": "awaiting_review"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.request_stop") as mock_request_stop, \
         patch("main.clear_cancellation") as mock_clear, \
         patch("main.log_event"):
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        response = client.post("/api/v1/tasks/task-123/stop")

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-123", "status": "stopped"}
    mock_request_stop.assert_not_called()
    mock_clear.assert_called_once_with("task-123")
    update_kwargs = mock_sb.table.return_value.update.call_args[0][0]
    assert update_kwargs["status"] == "stopped"


def test_pause_task_requests_pause_for_a_running_task():
    mock_result = MagicMock()
    mock_result.data = [{"status": "running"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.request_pause") as mock_request_pause, \
         patch("main.log_event"):
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/task-123/pause")

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-123", "status": "pausing"}
    mock_request_pause.assert_called_once_with("task-123")


def test_pause_task_returns_404_when_task_not_found_or_not_owned():
    mock_result = MagicMock()
    mock_result.data = []

    with patch("main.supabase") as mock_sb, \
         patch("main.request_pause") as mock_request_pause:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/nonexistent/pause")

    assert response.status_code == 404
    mock_request_pause.assert_not_called()


def test_pause_task_returns_409_when_task_is_not_running():
    mock_result = MagicMock()
    mock_result.data = [{"status": "paused"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.request_pause") as mock_request_pause:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/task-123/pause")

    assert response.status_code == 409
    mock_request_pause.assert_not_called()


def test_pause_task_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/api/v1/tasks/task-123/pause")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_resume_task_marks_running_and_schedules_run_graph_with_none_state():
    """None as initial_state is the actual resume signal LangGraph relies on — see
    run_graph's docstring — so this is the one detail worth pinning down explicitly."""
    mock_result = MagicMock()
    mock_result.data = [{"status": "paused"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.log_event"), \
         patch("main.run_graph") as mock_run_graph:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        response = client.post("/api/v1/tasks/task-123/resume")

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-123", "status": "running"}
    update_kwargs = mock_sb.table.return_value.update.call_args[0][0]
    assert update_kwargs == {"status": "running"}
    mock_run_graph.assert_called_once_with("task-123", None)


def test_resume_task_returns_404_when_task_not_found_or_not_owned():
    mock_result = MagicMock()
    mock_result.data = []

    with patch("main.supabase") as mock_sb, \
         patch("main.run_graph") as mock_run_graph:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/nonexistent/resume")

    assert response.status_code == 404
    mock_run_graph.assert_not_called()


def test_resume_task_returns_409_when_task_is_not_paused():
    mock_result = MagicMock()
    mock_result.data = [{"status": "running"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.run_graph") as mock_run_graph:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/task-123/resume")

    assert response.status_code == 409
    mock_run_graph.assert_not_called()


def test_resume_task_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/api/v1/tasks/task-123/resume")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_submit_review_decision_records_decision_and_schedules_run_graph():
    mock_result = MagicMock()
    mock_result.data = [{"status": "awaiting_review"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.log_event"), \
         patch("main.record_review_decision") as mock_record, \
         patch("main.run_graph") as mock_run_graph:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        response = client.post("/api/v1/tasks/task-123/review", json={"decision": "refine"})

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-123", "status": "running"}
    mock_record.assert_called_once_with("task-123", "refine")
    update_kwargs = mock_sb.table.return_value.update.call_args[0][0]
    assert update_kwargs == {"status": "running"}
    mock_run_graph.assert_called_once_with("task-123", None)


def test_submit_review_decision_accepts_finalize():
    mock_result = MagicMock()
    mock_result.data = [{"status": "awaiting_review"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.log_event"), \
         patch("main.record_review_decision") as mock_record, \
         patch("main.run_graph"):
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        response = client.post("/api/v1/tasks/task-123/review", json={"decision": "finalize"})

    assert response.status_code == 200
    mock_record.assert_called_once_with("task-123", "finalize")


def test_submit_review_decision_rejects_invalid_decision():
    with patch("main.record_review_decision") as mock_record:
        response = client.post("/api/v1/tasks/task-123/review", json={"decision": "maybe"})

    assert response.status_code == 422
    mock_record.assert_not_called()


def test_submit_review_decision_returns_404_when_task_not_found_or_not_owned():
    mock_result = MagicMock()
    mock_result.data = []

    with patch("main.supabase") as mock_sb, \
         patch("main.record_review_decision") as mock_record:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/nonexistent/review", json={"decision": "refine"})

    assert response.status_code == 404
    mock_record.assert_not_called()


def test_submit_review_decision_returns_409_when_task_is_not_awaiting_review():
    mock_result = MagicMock()
    mock_result.data = [{"status": "running"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.record_review_decision") as mock_record:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/tasks/task-123/review", json={"decision": "refine"})

    assert response.status_code == 409
    mock_record.assert_not_called()


def test_submit_review_decision_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/api/v1/tasks/task-123/review", json={"decision": "refine"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_submit_task_missing_query():
    response = client.post("/api/v1/submit_task", json={})
    assert response.status_code == 422


def test_submit_task_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/api/v1/submit_task", json={"query": "test"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_get_tasks():
    mock_result = MagicMock()
    mock_result.data = [
        {"task_id": "abc", "query": "test", "status": "running"}
    ]

    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result
        response = client.get("/api/v1/get_tasks")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_task_not_found():
    mock_result = MagicMock()
    mock_result.data = []

    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        response = client.get("/api/v1/get_task/nonexistent-id")

    assert response.status_code == 404


def test_get_domain_pack_config_returns_404_for_unknown_pack():
    response = client.get("/api/v1/domain_packs/not-a-real-pack/config")
    assert response.status_code == 404


def test_get_domain_pack_config_returns_prompt_config_fields():
    with patch("main.domain_pack.get_active_pack_config") as mock_get_config:
        mock_get_config.return_value = {
            "pack_id": "fraud-aml",
            "report_persona": "You are a senior AML investigator.",
            "report_classification": "Confidential — Supervisory Use Only",
            "subquestion_dimensions": ["Transaction risk", "KYC compliance"],
        }
        response = client.get("/api/v1/domain_packs/fraud-aml/config")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "report_persona": "You are a senior AML investigator.",
        "report_classification": "Confidential — Supervisory Use Only",
        "subquestion_dimensions": ["Transaction risk", "KYC compliance"],
    }
    mock_get_config.assert_called_once_with(override_pack_id="fraud-aml")


def test_get_llm_speed_profile_returns_current_profile_and_models():
    with patch("main.get_speed_profile", return_value="free"):
        response = client.get("/api/v1/llm_speed_profile")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "free"
    assert set(body["models"]) == {"high", "medium", "low"}
    assert all(m.endswith(":free") for m in body["models"].values())


def test_set_llm_speed_profile_to_fast_paid_upserts_app_settings():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        response = client.post("/api/v1/llm_speed_profile", json={"profile": "fast_paid"})

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "fast_paid"
    assert not body["models"]["high"].endswith(":free")
    assert not body["models"]["medium"].endswith(":free")
    mock_sb.table.return_value.upsert.assert_called_once_with(
        {"key": "llm_speed_profile", "value": "fast_paid"})


def test_set_llm_speed_profile_rejects_an_invalid_profile():
    response = client.post("/api/v1/llm_speed_profile", json={"profile": "ludicrous_speed"})
    assert response.status_code == 422


def test_set_llm_speed_profile_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/api/v1/llm_speed_profile", json={"profile": "free"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_reconcile_orphaned_tasks_marks_running_tasks_as_failed():
    """The core bug this fixes: a task killed mid-run by a server restart is stuck at
    "running" forever with nothing to ever flip it — this runs once at startup, before
    any request is served, so any "running" row found here is provably orphaned from a
    previous process."""
    mock_select_result = MagicMock()
    mock_select_result.data = [{"task_id": "orphan-1"}, {"task_id": "orphan-2"}]

    with patch("main.supabase") as mock_sb, \
         patch("main.log_event") as mock_log_event:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_select_result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        _reconcile_orphaned_tasks()

    mock_sb.table.return_value.select.return_value.eq.assert_called_once_with("status", "running")
    update_calls = mock_sb.table.return_value.update.call_args_list
    assert len(update_calls) == 2
    for call in update_calls:
        body = call[0][0]
        assert body["status"] == "failed"
        assert "restart" in body["final_result"].lower()
    assert mock_log_event.call_count == 2


def test_reconcile_orphaned_tasks_is_a_noop_when_nothing_is_orphaned():
    mock_select_result = MagicMock()
    mock_select_result.data = []

    with patch("main.supabase") as mock_sb, patch("main.log_event") as mock_log_event:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_select_result

        _reconcile_orphaned_tasks()

    mock_sb.table.return_value.update.assert_not_called()
    mock_log_event.assert_not_called()


def test_reconcile_orphaned_tasks_does_not_crash_if_the_db_is_unreachable():
    """Startup must not fail just because this best-effort cleanup couldn't run — a DB
    outage here shouldn't block the whole app from starting."""
    with patch("main.supabase") as mock_sb:
        mock_sb.table.side_effect = Exception("connection refused")
        _reconcile_orphaned_tasks()   # must not raise
