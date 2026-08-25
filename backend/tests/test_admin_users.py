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
    is_admin: bool = True


app.dependency_overrides[get_current_user] = lambda: FakeUser()
app.dependency_overrides[get_current_admin] = lambda: FakeUser()


def test_admin_list_users_returns_real_rows():
    mock_result = MagicMock()
    mock_result.data = [
        {"id": "u1", "email": "a@example.com", "name": "A", "is_admin": False,
         "is_banned": False, "created_at": "2026-01-01T00:00:00Z", "last_sign_in_at": None},
        {"id": "u2", "email": "b@example.com", "name": "B", "is_admin": True,
         "is_banned": True, "created_at": "2026-01-02T00:00:00Z", "last_sign_in_at": None},
    ]
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = mock_result
        response = client.get("/api/v1/admin/users")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[1]["is_banned"] is True


def test_admin_ban_user_404s_when_missing():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/admin/users/missing/ban")
    assert response.status_code == 404


def test_admin_ban_user_refuses_to_ban_self():
    # Every test module in this suite shares one FastAPI `app` and overrides the same
    # get_current_admin dependency at import time — whichever module import ran last wins
    # for the whole process, so this test can't trust the module-level FakeUser() above to
    # still be active by the time it runs. Override locally, deterministically, and
    # restore afterward so it doesn't leak into other tests either.
    previous_override = app.dependency_overrides[get_current_admin]
    app.dependency_overrides[get_current_admin] = lambda: FakeUser(id="self-1")
    try:
        mock_result = MagicMock()
        mock_result.data = [{"id": "self-1"}]
        with patch("main.supabase") as mock_sb:
            mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            response = client.post("/api/v1/admin/users/self-1/ban")
    finally:
        app.dependency_overrides[get_current_admin] = previous_override
    assert response.status_code == 422


def test_admin_ban_user_sets_is_banned():
    mock_result = MagicMock()
    mock_result.data = [{"id": "u1"}]
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/admin/users/u1/ban")

    assert response.status_code == 200
    mock_sb.table.return_value.update.assert_called_once_with({"is_banned": True})


def test_admin_unban_user_clears_is_banned():
    mock_result = MagicMock()
    mock_result.data = [{"id": "u1"}]
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        response = client.post("/api/v1/admin/users/u1/unban")

    assert response.status_code == 200
    mock_sb.table.return_value.update.assert_called_once_with({"is_banned": False})


def test_admin_list_admins_reflects_admin_emails_env(monkeypatch):
    monkeypatch.setattr("main.ADMIN_EMAILS", {"a@example.com", "b@example.com"})
    response = client.get("/api/v1/admin/admins")

    assert response.status_code == 200
    body = response.json()
    assert body["emails"] == ["a@example.com", "b@example.com"]
    assert "note" in body
