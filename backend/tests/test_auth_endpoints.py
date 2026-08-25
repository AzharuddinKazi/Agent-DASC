from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _users_table_mock(mock_sb, existing=None, inserted_id="new-user-id"):
    users_table = mock_sb.table.return_value
    users_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[existing] if existing else []
    )
    users_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": inserted_id}])
    return users_table


def test_auth_google_401s_on_an_invalid_credential():
    with patch("main.verify_google_id_token", side_effect=ValueError("bad token")):
        response = client.post("/api/v1/auth/google", json={"credential": "garbage"})
    assert response.status_code == 401


def test_auth_google_creates_a_new_user_and_sets_the_session_cookie():
    claims = {"sub": "g-sub-1", "email": "new@example.com", "name": "New Person", "picture": None}
    with patch("main.verify_google_id_token", return_value=claims), \
         patch("main.ADMIN_EMAILS", set()), \
         patch("main.supabase") as mock_sb:
        table = mock_sb.table.return_value
        # existing lookup by google_sub -> none, then insert -> new row, then final select -> full row
        table.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[]),                                    # existing check
            MagicMock(data=[{
                "id": "new-user-id", "email": "new@example.com", "name": "New Person",
                "picture_url": None, "is_admin": False, "is_banned": False,
            }]),                                                    # final reload
        ]
        table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "new-user-id"}])

        response = client.post("/api/v1/auth/google", json={"credential": "valid-token"})

    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"
    assert "session" in response.cookies


def test_auth_google_grants_admin_when_email_is_on_the_allowlist():
    claims = {"sub": "g-sub-2", "email": "admin@example.com", "name": "Admin", "picture": None}
    with patch("main.verify_google_id_token", return_value=claims), \
         patch("main.ADMIN_EMAILS", {"admin@example.com"}), \
         patch("main.supabase") as mock_sb:
        table = mock_sb.table.return_value
        table.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[]),
            MagicMock(data=[{
                "id": "u2", "email": "admin@example.com", "name": "Admin",
                "picture_url": None, "is_admin": True, "is_banned": False,
            }]),
        ]
        table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "u2"}])

        response = client.post("/api/v1/auth/google", json={"credential": "valid-token"})

    assert response.status_code == 200
    assert response.json()["is_admin"] is True
    inserted = table.insert.call_args[0][0]
    assert inserted["is_admin"] is True


def test_auth_google_403s_for_a_banned_returning_user():
    claims = {"sub": "g-sub-3", "email": "banned@example.com", "name": "Banned", "picture": None}
    with patch("main.verify_google_id_token", return_value=claims), \
         patch("main.ADMIN_EMAILS", set()), \
         patch("main.supabase") as mock_sb:
        table = mock_sb.table.return_value
        table.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "u3"}]),   # existing user found
            MagicMock(data=[{
                "id": "u3", "email": "banned@example.com", "name": "Banned",
                "picture_url": None, "is_admin": False, "is_banned": True,
            }]),
        ]
        table.update.return_value.eq.return_value.execute.return_value = MagicMock()

        response = client.post("/api/v1/auth/google", json={"credential": "valid-token"})

    assert response.status_code == 403


def test_login_options_reflects_demo_mode_flag():
    with patch("main.feature_flags.is_enabled", return_value=False):
        response = client.get("/api/v1/auth/login_options")
    assert response.status_code == 200
    assert response.json() == {"guest_login_enabled": False}

    with patch("main.feature_flags.is_enabled", return_value=True):
        response = client.get("/api/v1/auth/login_options")
    assert response.json() == {"guest_login_enabled": True}


def test_auth_logout_clears_the_session_cookie():
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"status": "signed_out"}


def test_auth_guest_403s_when_demo_mode_is_disabled():
    with patch("main.feature_flags.is_enabled", return_value=False):
        response = client.post("/api/v1/auth/guest", json={"name": "Priya"})
    assert response.status_code == 403


def test_auth_guest_creates_a_new_account_and_sets_the_session_cookie():
    with patch("main.supabase") as mock_sb, \
         patch("main.feature_flags.is_enabled", return_value=True):
        table = mock_sb.table.return_value
        # existing-guests-by-name lookup (checked in Python) -> none match
        table.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[]),
            MagicMock(data=[{
                "id": "guest-1", "email": None, "name": "Priya", "picture_url": None,
                "is_admin": False, "is_banned": False, "auth_provider": "guest",
            }]),
        ]
        table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "guest-1"}])

        response = client.post("/api/v1/auth/guest", json={"name": "Priya"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Priya"
    assert body["email"] is None
    assert body["is_admin"] is False
    assert "session" in response.cookies
    inserted = table.insert.call_args[0][0]
    assert inserted["auth_provider"] == "guest"
    assert inserted["is_admin"] is False


def test_auth_guest_reuses_the_existing_account_for_a_case_insensitive_name_match():
    with patch("main.supabase") as mock_sb, \
         patch("main.feature_flags.is_enabled", return_value=True):
        table = mock_sb.table.return_value
        table.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "guest-1", "name": "Priya"}]),   # existing guests
            MagicMock(data=[{
                "id": "guest-1", "email": None, "name": "Priya", "picture_url": None,
                "is_admin": False, "is_banned": False, "auth_provider": "guest",
            }]),
        ]
        table.update.return_value.eq.return_value.execute.return_value = MagicMock()

        response = client.post("/api/v1/auth/guest", json={"name": "priya"})

    assert response.status_code == 200
    assert response.json()["id"] == "guest-1"
    table.insert.assert_not_called()


def test_auth_guest_422s_on_a_blank_name():
    with patch("main.feature_flags.is_enabled", return_value=True):
        response = client.post("/api/v1/auth/guest", json={"name": "   "})
    assert response.status_code == 422


def test_auth_guest_403s_for_a_banned_guest():
    with patch("main.supabase") as mock_sb, \
         patch("main.feature_flags.is_enabled", return_value=True):
        table = mock_sb.table.return_value
        table.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "guest-2", "name": "Banned Guest"}]),
            MagicMock(data=[{
                "id": "guest-2", "email": None, "name": "Banned Guest", "picture_url": None,
                "is_admin": False, "is_banned": True, "auth_provider": "guest",
            }]),
        ]
        table.update.return_value.eq.return_value.execute.return_value = MagicMock()

        response = client.post("/api/v1/auth/guest", json={"name": "Banned Guest"})

    assert response.status_code == 403
