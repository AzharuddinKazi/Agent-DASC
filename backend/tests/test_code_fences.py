from agents.code_fences import strip_code_fences


def test_strips_fenced_block_with_language_tag():
    text = "```python\nprint(1)\nprint(2)\n```"
    assert strip_code_fences(text) == "print(1)\nprint(2)"


def test_strips_fenced_block_without_language_tag():
    text = "```\nprint(1)\n```"
    assert strip_code_fences(text) == "print(1)"


def test_leaves_unfenced_text_unchanged():
    text = "print(1)\nprint(2)"
    assert strip_code_fences(text) == text


def test_does_not_drop_last_line_when_closing_fence_is_missing():
    """The bug this module exists to fix: a response cut off mid-completion has no
    closing fence, and a naive `split("\\n")[1:-1]` would drop the last real line."""
    text = "```python\nprint(1)\nprint(2)"
    assert strip_code_fences(text) == "print(1)\nprint(2)"


def test_handles_single_line_fenced_block():
    text = "```python\nprint(1)\n```"
    assert strip_code_fences(text) == "print(1)"


def test_handles_fence_with_no_content():
    text = "```python\n```"
    assert strip_code_fences(text) == ""
