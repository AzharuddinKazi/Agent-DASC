from dataclasses import dataclass
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app
from auth import get_current_user, get_current_admin

client = TestClient(app)


@dataclass
class FakeUser:
    id: str = "00000000-0000-0000-0000-000000000001"
    email: str = "fake-admin@example.com"


app.dependency_overrides[get_current_user] = lambda: FakeUser()
app.dependency_overrides[get_current_admin] = lambda: FakeUser()


def test_admin_list_tasks_returns_rows_across_all_users():
    mock_result = MagicMock()
    mock_result.data = [{"task_id": "t1", "user_id": "u1"}, {"task_id": "t2", "user_id": "u2"}]
    with patch("main.supabase") as mock_sb:
        chain = mock_sb.table.return_value.select.return_value.order.return_value
        chain.range.return_value.execute.return_value = mock_result
        response = client.get("/api/v1/admin/tasks")

    assert response.status_code == 200
    assert len(response.json()) == 2
    mock_sb.table.return_value.select.return_value.order.return_value.eq.assert_not_called()


def test_admin_list_tasks_filters_by_status_and_user_id():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("main.supabase") as mock_sb:
        chain = mock_sb.table.return_value.select.return_value.order.return_value
        chain.eq.return_value.eq.return_value.range.return_value.execute.return_value = mock_result
        response = client.get("/api/v1/admin/tasks?status=running&user_id=u1")

    assert response.status_code == 200
    chain.eq.assert_called_once_with("status", "running")
    chain.eq.return_value.eq.assert_called_once_with("user_id", "u1")


def test_admin_get_task_404s_when_missing():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.get("/api/v1/admin/tasks/missing")
    assert response.status_code == 404


def test_admin_get_task_parses_json_string_fields():
    mock_result = MagicMock()
    mock_result.data = [{"task_id": "t1", "sub_results": '{"a": 1}', "logs": "[]"}]
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.get("/api/v1/admin/tasks/t1")

    assert response.status_code == 200
    body = response.json()
    assert body["sub_results"] == {"a": 1}
    assert body["logs"] == []


def test_admin_stop_task_404s_when_missing():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/admin/tasks/missing/stop")
    assert response.status_code == 404


def test_admin_stop_task_409s_when_not_running():
    mock_result = MagicMock()
    mock_result.data = [{"status": "completed"}]
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/admin/tasks/t1/stop")
    assert response.status_code == 409


def test_admin_stop_task_requests_cancellation_for_a_running_task():
    mock_result = MagicMock()
    mock_result.data = [{"status": "running"}]
    with patch("main.supabase") as mock_sb, patch("main.request_stop") as mock_stop:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/admin/tasks/t1/stop")

    assert response.status_code == 200
    assert response.json() == {"task_id": "t1", "status": "stopping"}
    mock_stop.assert_called_once_with("t1")


def test_admin_rerun_task_creates_a_new_task_id_and_copies_the_query():
    mock_result = MagicMock()
    mock_result.data = [{
        "task_id": "t1", "query": "How many rows?", "formatting_guidelines": "",
        "task_type": "qa", "user_id": "u1",
    }]
    with patch("main.supabase") as mock_sb, patch("main.run_graph") as mock_run_graph:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
        response = client.post("/api/v1/admin/tasks/t1/rerun")

    assert response.status_code == 202
    body = response.json()
    assert body["rerun_of"] == "t1"
    assert body["task_id"] != "t1"
    inserted = mock_sb.table.return_value.insert.call_args[0][0]
    assert inserted["query"] == "How many rows?"
    assert inserted["user_id"] == "u1"
    mock_run_graph.assert_called_once()
    assert mock_run_graph.call_args[0][0] == body["task_id"]


def test_admin_rerun_task_404s_when_missing():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/admin/tasks/missing/rerun")
    assert response.status_code == 404


def test_admin_delete_task_removes_the_row():
    mock_select = MagicMock()
    mock_select.data = [{"task_id": "t1"}]
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_select
        response = client.delete("/api/v1/admin/tasks/t1")

    assert response.status_code == 200
    mock_sb.table.return_value.delete.return_value.eq.assert_called_once_with("task_id", "t1")


def test_admin_delete_task_404s_when_missing():
    mock_select = MagicMock()
    mock_select.data = []
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_select
        response = client.delete("/api/v1/admin/tasks/missing")
    assert response.status_code == 404
