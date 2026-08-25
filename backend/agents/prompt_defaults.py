"""Registry of the agent prompt constants the Admin Control Panel's prompt editor can
override — see agents/prompt_store.py. A single import point so main.py's admin endpoints
don't need to import each agent module directly just to read its default constant."""
from agents.analyzer import ANALYZER_PROMPT
from agents.debugger import DEBUGGER_PROMPT
from agents.finalizer import FINALIZER_PROMPT
from agents.query_clarity import QUERY_CLARITY_PROMPT
from agents.question_generator import QUESTION_GENERATOR_PROMPT
from agents.report_evaluator import REPORT_EVALUATOR_PROMPT
from agents.router_agent import ROUTER_PROMPT
from agents.verifier import VERIFIER_PROMPT

# planner/writer deliberately excluded — see prompt_store.py's module docstring.
AGENT_PROMPT_DEFAULTS = {
    "analyzer":           ANALYZER_PROMPT,
    "debugger":           DEBUGGER_PROMPT,
    "finalizer":          FINALIZER_PROMPT,
    "query_clarity":      QUERY_CLARITY_PROMPT,
    "question_generator": QUESTION_GENERATOR_PROMPT,
    "report_evaluator":   REPORT_EVALUATOR_PROMPT,
    "router":             ROUTER_PROMPT,
    "verifier":           VERIFIER_PROMPT,
}
