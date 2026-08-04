"""Best-effort repair pass for a specific, observed LLM-generated-script defect: an
f-string format spec with a stray space after the thousands-separator comma, e.g.
`f"{x:, .2f}"` instead of the valid `f"{x:,.2f}"`. Python raises `ValueError` for the
malformed form at execution time — a hard failure that previously had no repair path,
just the generic debug-and-retry loop with no guaranteed graceful degradation (a script
that only fails on this could burn every retry and still fail the whole task).

Applied unconditionally before every generated script runs (see executor.execute_script)
rather than only after a first failure, since it's a pure, narrowly-targeted text fix with
no legitimate Python construct it could clobber — see the regex comment below.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Matches `:,` (format spec starts with the thousands-separator flag) immediately
# followed by whitespace, then the rest of the spec up to the closing brace — e.g.
# `:, .2f}`, `:, .0%}`, `:,   d}`. Restricted to a colon+comma with NOTHING between them
# (no width/alignment chars) directly followed by whitespace: that combination has no
# legitimate meaning in Python (a dict/set literal can't have a bare `:,` immediately
# followed by whitespace and then close with `}` either), so this only ever matches the
# one defect it targets.
_STRAY_COMMA_FORMAT_SPEC = re.compile(r'(:,)[ \t]+([^{}\n]*?)\}')


def repair_fstring_format_specs(script: str) -> str:
    fixed, count = _STRAY_COMMA_FORMAT_SPEC.subn(r'\1\2}', script)
    if count:
        logger.warning(f"Repaired {count} malformed f-string format spec(s) (stray comma before format code)")
    return fixed
