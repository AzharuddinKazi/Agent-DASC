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


def test_admin_system_overview_combines_health_speed_profile_and_flags():
    with patch("main.supabase") as mock_sb, \
         patch("main.requests.get") as mock_llm_get, \
         patch("main.subprocess.run") as mock_docker, \
         patch("main.get_speed_profile", return_value="free"), \
         patch("main.feature_flags.all_flags", return_value={"domain_packs": True}):
        mock_sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        mock_llm_get.return_value = MagicMock(raise_for_status=MagicMock())
        mock_docker.return_value = MagicMock()

        response = client.get("/api/v1/admin/system")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["llm_speed_profile"] == "free"
    assert body["feature_flags"] == {"domain_packs": True}
    assert "concurrency" in body


def test_admin_system_overview_requires_admin():
    app.dependency_overrides.pop(get_current_admin, None)
    try:
        response = client.get("/api/v1/admin/system")
        assert response.status_code == 403
    finally:
        app.dependency_overrides[get_current_admin] = lambda: FakeUser()
