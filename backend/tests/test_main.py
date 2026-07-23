from dataclasses import dataclass
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth import get_current_user

client = TestClient(app)


@dataclass
class FakeUser:
    id: str = "00000000-0000-0000-0000-000000000001"


app.dependency_overrides[get_current_user] = lambda: FakeUser()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ("ok", "degraded")


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
