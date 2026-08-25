from dataclasses import dataclass
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from auth import get_current_user, get_current_admin

client = TestClient(app)


@dataclass
class FakeUser:
    id: str = "admin-1"
    email: str = "fake-admin@example.com"


app.dependency_overrides[get_current_user] = lambda: FakeUser()
app.dependency_overrides[get_current_admin] = lambda: FakeUser()


def test_admin_list_prompts_marks_uncustomized_agents():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        response = client.get("/api/v1/admin/prompts")

    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert all(not p["is_customized"] for p in body)
    assert all(p["prompt_text"] == p["default_text"] for p in body)


def test_admin_list_prompts_reflects_an_existing_override():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[
            {"agent_name": "analyzer", "prompt_text": "custom", "updated_at": "2026-01-01T00:00:00Z", "updated_by": "a@b.com"},
        ])
        response = client.get("/api/v1/admin/prompts")

    assert response.status_code == 200
    analyzer = next(p for p in response.json() if p["agent_name"] == "analyzer")
    assert analyzer["is_customized"] is True
    assert analyzer["prompt_text"] == "custom"


def test_admin_set_prompt_404s_for_an_unknown_agent():
    response = client.put("/api/v1/admin/prompts/not_a_real_agent", json={"prompt_text": "x"})
    assert response.status_code == 404


def test_admin_set_prompt_upserts_and_returns_customized():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        response = client.put("/api/v1/admin/prompts/analyzer", json={"prompt_text": "new prompt"})

    assert response.status_code == 200
    body = response.json()
    assert body["is_customized"] is True
    upserted = mock_sb.table.return_value.upsert.call_args[0][0]
    assert upserted["agent_name"] == "analyzer"
    assert upserted["prompt_text"] == "new prompt"


def test_admin_reset_prompt_deletes_the_override():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        response = client.post("/api/v1/admin/prompts/analyzer/reset")

    assert response.status_code == 200
    assert response.json()["is_customized"] is False
    mock_sb.table.return_value.delete.return_value.eq.assert_called_once_with("agent_name", "analyzer")
