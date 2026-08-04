import math
from agents.json_sanitize import sanitize_json_floats


def test_replaces_nan_with_none():
    assert sanitize_json_floats(float("nan")) is None


def test_replaces_infinities_with_none():
    assert sanitize_json_floats(float("inf")) is None
    assert sanitize_json_floats(float("-inf")) is None


def test_leaves_finite_floats_and_other_types_unchanged():
    assert sanitize_json_floats(3.14) == 3.14
    assert sanitize_json_floats("nan") == "nan"
    assert sanitize_json_floats(None) is None
    assert sanitize_json_floats(True) is True


def test_recurses_into_nested_dicts_and_lists():
    value = {
        "summary": "ok",
        "rows": [[1, float("nan")], [2, 3.5]],
        "chart": {"data": [{"y": float("inf")}]},
    }
    result = sanitize_json_floats(value)
    assert result["rows"] == [[1, None], [2, 3.5]]
    assert result["chart"]["data"][0]["y"] is None
    assert result["summary"] == "ok"


def test_output_is_always_json_serializable_without_allow_nan():
    import json
    value = {"a": float("nan"), "b": [float("inf"), float("-inf"), 1.0]}
    dumped = json.dumps(sanitize_json_floats(value), allow_nan=False)
    assert "NaN" not in dumped
    assert "Infinity" not in dumped
