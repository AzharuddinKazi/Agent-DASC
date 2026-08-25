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


def test_admin_list_models_returns_every_tiered_agent():
    with patch("main.supabase") as mock_sb, \
         patch("main._local_ollama_tags", return_value=["dsstar-high:16k"]):
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        response = client.get("/api/v1/admin/models")

    assert response.status_code == 200
    body = response.json()
    agent_names = {a["agent_name"] for a in body["agents"]}
    assert "planner" in agent_names
    assert body["available_models"] == ["dsstar-high:16k"]


def test_admin_list_models_shows_the_coder_model_for_code_agents():
    """coder/debugger/finalizer should show whatever _FREE_MODELS["coder"]/
    _FAST_PAID_MODELS["coder"] actually is, not their AGENT_TIERS entry (finalizer is
    nominally "medium") — mirrors LLMRouter.complete()'s own routing."""
    from llm_router import LLMRouter
    with patch("main.supabase") as mock_sb, \
         patch("main._local_ollama_tags", return_value=[]):
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        response = client.get("/api/v1/admin/models")

    agents = {a["agent_name"]: a for a in response.json()["agents"]}
    for agent in ("coder", "debugger", "finalizer"):
        assert agents[agent]["effective_model"] == LLMRouter._FREE_MODELS["coder"]


def test_admin_list_models_reflects_a_db_override():
    with patch("main.supabase") as mock_sb, \
         patch("main._local_ollama_tags", return_value=[]):
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[
            {"agent_name": "planner", "model_id": "custom-model"},
        ])
        response = client.get("/api/v1/admin/models")

    planner = next(a for a in response.json()["agents"] if a["agent_name"] == "planner")
    assert planner["db_override"] == "custom-model"
    assert planner["effective_model"] == "custom-model"


def test_admin_set_model_override_404s_for_an_unknown_agent():
    response = client.put("/api/v1/admin/models/not_a_real_agent", json={"model_id": "x"})
    assert response.status_code == 404


def test_admin_set_model_override_upserts_when_given_a_model_id():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        response = client.put("/api/v1/admin/models/planner", json={"model_id": "custom-model"})

    assert response.status_code == 200
    upserted = mock_sb.table.return_value.upsert.call_args[0][0]
    assert upserted["agent_name"] == "planner"
    assert upserted["model_id"] == "custom-model"


def test_admin_set_model_override_clears_when_model_id_is_null():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        response = client.put("/api/v1/admin/models/planner", json={"model_id": None})

    assert response.status_code == 200
    mock_sb.table.return_value.delete.return_value.eq.assert_called_once_with("agent_name", "planner")
