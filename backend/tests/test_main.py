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
    """Mocks all three dependency pings — /health legitimately returns 503 when a real
    dependency is unreachable (by design), so asserting 200 unconditionally means this
    test was accidentally dependent on live Supabase/Gemini/Docker being reachable.
    """
    with patch("main.supabase") as mock_sb, \
         patch("main._genai_client") as mock_genai, \
         patch("main.subprocess.run") as mock_docker:
        mock_sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        mock_genai.models.list.return_value = []
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
