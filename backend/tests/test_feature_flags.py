from unittest.mock import patch, MagicMock

import feature_flags


def test_is_enabled_defaults_to_true_when_never_toggled():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("feature_flags.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert feature_flags.is_enabled("domain_packs") is True


def test_is_enabled_reads_stored_false():
    mock_result = MagicMock()
    mock_result.data = [{"value": "false"}]
    with patch("feature_flags.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert feature_flags.is_enabled("domain_packs") is False


def test_is_enabled_reads_stored_true():
    mock_result = MagicMock()
    mock_result.data = [{"value": "true"}]
    with patch("feature_flags.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert feature_flags.is_enabled("domain_packs") is True


def test_is_enabled_falls_back_to_default_on_db_error():
    with patch("feature_flags.supabase") as mock_sb:
        mock_sb.table.side_effect = RuntimeError("unreachable")
        assert feature_flags.is_enabled("domain_packs") is True


def test_demo_mode_defaults_to_false_when_never_toggled():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("feature_flags.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert feature_flags.is_enabled("demo_mode") is False


def test_is_enabled_unknown_feature_defaults_true():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("feature_flags.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert feature_flags.is_enabled("something_undefined") is True


def test_set_enabled_upserts_the_flag_key():
    with patch("feature_flags.supabase") as mock_sb:
        feature_flags.set_enabled("domain_packs", False)
        mock_sb.table.assert_called_with("app_settings")
        mock_sb.table.return_value.upsert.assert_called_once_with(
            {"key": "feature:domain_packs", "value": "false"}
        )


def test_set_enabled_rejects_unknown_feature():
    try:
        feature_flags.set_enabled("not_a_real_feature", True)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_all_flags_covers_every_known_feature():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("feature_flags.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        flags = feature_flags.all_flags()
    assert set(flags.keys()) == set(feature_flags.KNOWN_FEATURES.keys())
