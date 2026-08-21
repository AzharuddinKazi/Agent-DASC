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


@dataclass
class FakeAuthUser:
    id: str
    email: str
    created_at: str
    last_sign_in_at: str | None
    banned_until: str | None = None


app.dependency_overrides[get_current_user] = lambda: FakeUser()
app.dependency_overrides[get_current_admin] = lambda: FakeUser()


def test_admin_list_users_maps_supabase_auth_users():
    fake_users = [
        FakeAuthUser(id="u1", email="a@example.com", created_at="2026-01-01T00:00:00Z", last_sign_in_at=None),
    ]
    with patch("main.supabase") as mock_sb:
        mock_sb.auth.admin.list_users.return_value = fake_users
        response = client.get("/api/v1/admin/users")

    assert response.status_code == 200
    assert response.json() == [{
        "id": "u1", "email": "a@example.com", "created_at": "2026-01-01T00:00:00Z",
        "last_sign_in_at": None, "banned_until": None,
    }]


def test_admin_ban_user_sets_a_long_ban_duration():
    with patch("main.supabase") as mock_sb:
        response = client.post("/api/v1/admin/users/u1/ban")

    assert response.status_code == 200
    assert response.json() == {"user_id": "u1", "banned": True}
    mock_sb.auth.admin.update_user_by_id.assert_called_once_with("u1", {"ban_duration": "876000h"})


def test_admin_unban_user_clears_the_ban_duration():
    with patch("main.supabase") as mock_sb:
        response = client.post("/api/v1/admin/users/u1/unban")

    assert response.status_code == 200
    assert response.json() == {"user_id": "u1", "banned": False}
    mock_sb.auth.admin.update_user_by_id.assert_called_once_with("u1", {"ban_duration": "none"})


def test_admin_list_admins_returns_the_sorted_allowlist():
    with patch("main._admin_emails", return_value={"z@example.com", "a@example.com"}):
        response = client.get("/api/v1/admin/admins")

    assert response.status_code == 200
    body = response.json()
    assert body["emails"] == ["a@example.com", "z@example.com"]
    assert "note" in body


def test_admin_list_users_requires_admin():
    app.dependency_overrides.pop(get_current_admin, None)
    try:
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 403
    finally:
        app.dependency_overrides[get_current_admin] = lambda: FakeUser()
