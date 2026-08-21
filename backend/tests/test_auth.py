from dataclasses import dataclass
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from auth import get_current_admin


@dataclass
class FakeUser:
    email: str


@pytest.mark.asyncio
async def test_get_current_admin_allows_listed_email():
    with patch.dict("os.environ", {"ADMIN_EMAILS": "admin@example.com, other@example.com"}):
        user = await get_current_admin(user=FakeUser(email="admin@example.com"))
    assert user.email == "admin@example.com"


@pytest.mark.asyncio
async def test_get_current_admin_is_case_insensitive():
    with patch.dict("os.environ", {"ADMIN_EMAILS": "Admin@Example.com"}):
        user = await get_current_admin(user=FakeUser(email="admin@example.com"))
    assert user.email == "admin@example.com"


@pytest.mark.asyncio
async def test_get_current_admin_rejects_unlisted_email():
    with patch.dict("os.environ", {"ADMIN_EMAILS": "admin@example.com"}):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(user=FakeUser(email="someone-else@example.com"))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_admin_fails_closed_when_allowlist_unset():
    with patch.dict("os.environ", {"ADMIN_EMAILS": ""}):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(user=FakeUser(email="admin@example.com"))
    assert exc_info.value.status_code == 403
