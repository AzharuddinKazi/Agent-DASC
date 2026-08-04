from agents.script_repair import repair_fstring_format_specs


def test_removes_stray_space_after_thousands_separator():
    script = 'print(f"Total: {x:, .2f}")'
    assert repair_fstring_format_specs(script) == 'print(f"Total: {x:,.2f}")'


def test_removes_stray_space_with_percent_format():
    script = 'print(f"Share: {x:, .0%}")'
    assert repair_fstring_format_specs(script) == 'print(f"Share: {x:,.0%}")'


def test_handles_multiple_occurrences():
    script = 'print(f"{a:, .2f} and {b:, .1f}")'
    assert repair_fstring_format_specs(script) == 'print(f"{a:,.2f} and {b:,.1f}")'


def test_leaves_well_formed_format_specs_untouched():
    script = 'print(f"Total: {x:,.2f}")'
    assert repair_fstring_format_specs(script) == script


def test_leaves_unrelated_code_untouched():
    script = "df = pd.DataFrame({'a': [1, 2]})\nprint(df.to_dict())"
    assert repair_fstring_format_specs(script) == script
