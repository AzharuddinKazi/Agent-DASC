from unittest.mock import MagicMock, patch

from agents.prompt_store import get_prompt


def test_get_prompt_returns_default_when_no_override_exists():
    with patch("agents.prompt_store.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        result = get_prompt("analyzer", "default text")
    assert result == "default text"


def test_get_prompt_returns_db_override_when_present():
    with patch("agents.prompt_store.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"prompt_text": "custom text"}]
        )
        result = get_prompt("analyzer", "default text")
    assert result == "custom text"


def test_get_prompt_fails_closed_to_default_on_db_error():
    with patch("agents.prompt_store.supabase") as mock_sb:
        mock_sb.table.side_effect = RuntimeError("db down")
        result = get_prompt("analyzer", "default text")
    assert result == "default text"
