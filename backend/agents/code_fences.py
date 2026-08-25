import re

_OPEN_FENCE = re.compile(r"^```[a-zA-Z]*\n?")
_CLOSE_FENCE = re.compile(r"\n?```$")

# Some models (observed: qwen/qwen3-coder-next, 2026-08-23 — see TASKS.md) emit
# [python]...[/python]-style tags instead of, or alongside, a markdown fence — a
# leaked trailing "[/python]" line then becomes a real SyntaxError in the executed
# script, burning a self-debug attempt on a stripping bug rather than an actual code
# bug. Stripped as a second, independent pass after the backtick fence so either
# convention (or both, if a model wraps a markdown fence in bracket tags too) is
# handled the same way.
_OPEN_BRACKET_TAG = re.compile(r"^\[python\]\n?", re.IGNORECASE)
_CLOSE_BRACKET_TAG = re.compile(r"\n?\[/python\]$", re.IGNORECASE)


def strip_code_fences(text: str) -> str:
    """Strips a leading/trailing markdown code fence (or [python]/[/python] tag) from
    an LLM response, if present.

    Strips the opening marker unconditionally and the closing one only if it's actually
    there. A response cut off mid-completion (hit a token limit, connection dropped) has
    no closing marker — the previous per-agent implementation of this (`split("\n")[1:-1]`,
    independently duplicated in analyzer.py, coder.py, debugger.py, and finalizer.py)
    always dropped the last line assuming it was the closing fence, silently truncating
    the last real line of code in exactly that case.
    """
    if text.startswith("```"):
        text = _OPEN_FENCE.sub("", text)
        text = _CLOSE_FENCE.sub("", text).strip()
    if text.startswith("[python]") or text.startswith("[PYTHON]"):
        text = _OPEN_BRACKET_TAG.sub("", text)
        text = _CLOSE_BRACKET_TAG.sub("", text).strip()
    return text
