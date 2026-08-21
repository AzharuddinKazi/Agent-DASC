from unittest.mock import patch, MagicMock

import domain_pack


def test_get_active_pack_config_returns_generic_defaults_when_feature_disabled():
    """The 'domain_packs' flag being off must override even an explicit override_pack_id
    and the DB's active_domain_pack setting — this is the single choke point every agent
    calls, so this is where disabling the feature actually has to take effect."""
    with patch("domain_pack._feature_enabled", return_value=False), \
         patch("domain_pack.supabase") as mock_sb:
        result = domain_pack.get_active_pack_config(override_pack_id="fraud-aml")

    mock_sb.table.assert_not_called()
    assert result == {
        "pack_id":                None,
        "report_persona":         "You are a senior data analyst writing a report for a business stakeholder.",
        "report_classification":  None,
        "subquestion_dimensions": [],
    }


def test_get_active_pack_config_reads_db_when_feature_enabled():
    mock_row = MagicMock()
    mock_row.data = [{
        "report_persona":         "You are an AML investigator.",
        "report_classification":  "Confidential",
        "subquestion_dimensions": ["Transaction risk"],
    }]
    with patch("domain_pack._feature_enabled", return_value=True), \
         patch("domain_pack.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_row
        result = domain_pack.get_active_pack_config(override_pack_id="fraud-aml")

    assert result["pack_id"] == "fraud-aml"
    assert result["report_persona"] == "You are an AML investigator."
