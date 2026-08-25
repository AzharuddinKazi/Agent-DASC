from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import auth
from auth import get_current_user, get_current_admin, issue_session_cookie, _read_session_cookie


class FakeRequest:
    def __init__(self, cookies):
        self.cookies = cookies


def _user_row(**overrides):
    row = {
        "id": "u1", "google_sub": "g-sub-1", "email": "person@example.com",
        "name": "Person", "picture_url": None, "is_admin": False, "is_banned": False,
    }
    row.update(overrides)
    return row


def test_issue_and_read_session_cookie_round_trips():
    token = issue_session_cookie("u1")
    assert _read_session_cookie(token) == "u1"


def test_read_session_cookie_returns_none_for_garbage():
    assert _read_session_cookie("not-a-real-jwt") is None


@pytest.mark.asyncio
async def test_get_current_user_401s_with_no_cookie():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(FakeRequest(cookies={}))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_401s_when_user_row_no_longer_exists():
    token = issue_session_cookie("gone")
    with patch("auth.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(FakeRequest(cookies={"session": token}))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_403s_for_a_banned_user():
    token = issue_session_cookie("u1")
    with patch("auth.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_user_row(is_banned=True)]
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(FakeRequest(cookies={"session": token}))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_returns_a_valid_authuser():
    token = issue_session_cookie("u1")
    with patch("auth.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_user_row(is_admin=True)]
        )
        user = await get_current_user(FakeRequest(cookies={"session": token}))
    assert user.id == "u1"
    assert user.email == "person@example.com"
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_get_current_admin_403s_for_a_non_admin():
    non_admin = auth.AuthUser(id="u1", email="a@b.com", is_admin=False)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(user=non_admin)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_admin_passes_through_an_admin():
    admin = auth.AuthUser(id="u1", email="a@b.com", is_admin=True)
    result = await get_current_admin(user=admin)
    assert result is admin
