import re

_OPEN_FENCE = re.compile(r"^```[a-zA-Z]*\n?")
_CLOSE_FENCE = re.compile(r"\n?```$")


def strip_code_fences(text: str) -> str:
    """Strips a leading/trailing markdown code fence from an LLM response, if present.

    Strips the opening fence unconditionally and the closing one only if it's actually
    there. A response cut off mid-completion (hit a token limit, connection dropped) has
    no closing fence — the previous per-agent implementation of this (`split("\n")[1:-1]`,
    independently duplicated in analyzer.py, coder.py, debugger.py, and finalizer.py)
    always dropped the last line assuming it was the closing fence, silently truncating
    the last real line of code in exactly that case.
    """
    if not text.startswith("```"):
        return text
    text = _OPEN_FENCE.sub("", text)
    return _CLOSE_FENCE.sub("", text).strip()
