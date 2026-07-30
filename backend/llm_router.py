"""
LLM routing layer for DS-STAR.

All LLM calls in the system go through this module.
No agent node or API handler should ever call a model provider directly.
Swapping models or adding new providers requires changes only here.

Typical usage:
    router = LLMRouter()
    result = router.complete(agent="planner", prompt="...")
"""

from dotenv import load_dotenv
import logging
import os
import time
import requests

from agents.logger import log_event

logger = logging.getLogger(__name__)

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

VALID_SPEED_PROFILES = {"free", "fast_paid"}


def get_speed_profile() -> str:
    """Reads the live LLM speed profile from app_settings — a toggle, not a deployment
    setting, so it's read fresh on every call rather than cached/baked in at import
    time. Set via POST /api/v1/llm_speed_profile, takes effect on the very next LLM
    call with no restart needed. "free" is the hardcoded default — both before anyone
    has ever toggled it (no app_settings row yet) and if the DB is unreachable — so a
    stray leftover env var or a DB hiccup can never silently switch a run onto billed
    models (matches domain_pack.py's own fail-closed-to-generic pattern)."""
    from db import supabase
    try:
        row = supabase.table("app_settings").select("value").eq("key", "llm_speed_profile").execute()
        value = row.data[0]["value"] if row.data else "free"
        return value if value in VALID_SPEED_PROFILES else "free"
    except Exception:
        return "free"


# Matches the sandbox executor's own 120s ceiling (executor.py) — without this, a hung
# API call (network partition, provider stall) leaves a task running forever with no
# error and no way to tell "still working" from "silently dead".
LLM_TIMEOUT_S = 120

# Free OpenRouter models are rate-limited far more aggressively than a paid Gemini
# project was (per-minute caps, occasional 429/503 under shared-pool load) — a couple of
# short retries absorbs that instead of failing a whole multi-round task on one blip.
MAX_RETRIES = 2
RETRYABLE_STATUS = {429, 502, 503, 504}


class LLMRouter:
    """Routes LLM calls to the appropriate model based on agent type.

    DS-STAR uses a three-tier model assignment to balance cost and quality.
    High-tier agents handle complex reasoning and code generation.
    Medium-tier agents handle structured, bounded tasks.
    Low-tier agents handle fast, cheap classification and profiling.

    Calls go through OpenRouter (https://openrouter.ai), an OpenAI-compatible proxy in
    front of many providers — this lets DS-STAR run entirely on free-tier models (no
    billing account needed) by picking `:free`-suffixed model ids. OpenRouter's free
    catalog rotates as providers add/retire free listings; check
    https://openrouter.ai/api/v1/models (filter for ids ending in ":free") if a default
    below stops being served, and override it with the matching env var below rather
    than editing this file.

    Attributes:
        AGENT_TIERS: Maps each DS-STAR agent to its quality tier.

    The active speed profile ("free" or "fast_paid" — see get_speed_profile()) is a
    live, DB-backed toggle read fresh on every complete() call, not baked in at import
    time — flip it via POST /api/v1/llm_speed_profile and it applies to the very next
    call, no restart needed. Change a tier's model via the matching
    OPENROUTER_MODEL_*/OPENROUTER_MODEL_*_FAST env var.

    Example:
        router = LLMRouter()
        result = router.complete(agent="planner", prompt="...")
        print(result["text"])
    """

    # Maps tier names to OpenRouter model ids. All three are free-tier as of this
    # writing (verified against GET /api/v1/models) — no billing required.
    _FREE_MODELS = {
        # 120B MoE, explicitly built for "complex multi-agent applications" — the
        # largest free model available, used for the agents where reasoning quality
        # matters most.
        "high":   os.getenv("OPENROUTER_MODEL_HIGH",   "nvidia/nemotron-3-super-120b-a12b:free"),
        # OpenAI's open-weight 21B MoE — solid general-purpose middle ground.
        "medium": os.getenv("OPENROUTER_MODEL_MEDIUM", "openai/gpt-oss-20b:free"),
        # Small/fast, tuned for lightweight classification-style tasks.
        "low":    os.getenv("OPENROUTER_MODEL_LOW",    "nvidia/nemotron-nano-9b-v2:free"),
    }

    # Paid model actually chosen for cheapest-and-still-fast (not just "not free") — for
    # the fast_paid profile's speed testing, not everyday use. `:nitro` is
    # OpenRouter's own throughput-priority routing shortcut (equivalent to
    # provider.sort="throughput") — it always picks whichever provider serving this
    # model currently has the highest tokens/sec, which is the actual "fast" half of
    # "cheap but fast." At ~$0.02/$0.04 per M input/output tokens, a full pipeline run
    # costs a small fraction of a cent — verify current pricing at
    # https://openrouter.ai/meta-llama/llama-3.1-8b-instruct before relying on it,
    # OpenRouter pricing and model availability both change.
    _FAST_MODEL_DEFAULT = "meta-llama/llama-3.1-8b-instruct:nitro"
    _FAST_PAID_MODELS = {
        "high":   os.getenv("OPENROUTER_MODEL_HIGH_FAST",   _FAST_MODEL_DEFAULT),
        "medium": os.getenv("OPENROUTER_MODEL_MEDIUM_FAST", _FAST_MODEL_DEFAULT),
        # low (analyzer, sub_result_collector) is lightweight, infrequent work — not
        # the speed bottleneck this profile exists to test, so it stays on the same
        # genuinely free model as the free profile rather than paying for it too.
        "low":    os.getenv("OPENROUTER_MODEL_LOW_FAST",    _FREE_MODELS["low"]),
    }

    @classmethod
    def models_for_profile(cls, profile: str) -> dict:
        return cls._FAST_PAID_MODELS if profile == "fast_paid" else cls._FREE_MODELS

    # Maps each DS-STAR agent to its quality tier.
    # Planner, Coder, Verifier, Debugger use high — errors here compound downstream.
    # Router and Finalizer use medium — constrained, templated decisions.
    # QueryClarity and Analyzer use low — run frequently, simplicity matters.
    AGENT_TIERS = {
        "planner":       "high",    # multi-step reasoning over query + file descriptions
        "coder":         "high",    # generates Python scripts — correctness is critical
        "verifier":      "high",    # judges plan sufficiency — false positives are dangerous
        "debugger":      "high",    # reads tracebacks and patches code
        "router":        "medium",  # binary decision: add_step or backtrack
        "finalizer":     "medium",  # formats a known result into output structure
        # medium: observed nemotron-nano-9b-v2:free (low tier) failing to produce a
        # single flat JSON array for >1 question — it wrapped each question object in
        # its own separate [...] instead, e.g. "[{...}], {...}, {...}()]" — same class
        # of structured-output unreliability as question_generator below, same fix.
        "query_clarity": "medium",  # classifies ambiguity + mode — runs before every task
        "analyzer":      "low",     # generates file profiling scripts — runs once per file
        # DS-STAR+ report pipeline agents
        # high: a single multi-hypothesis JSON array (4-7 objects) over a long,
        # multi-file prompt — medium (gpt-oss-20b:free) was observed garbling the
        # array mid-generation (truncated/malformed JSON) on exactly this shape of
        # task, silently producing 0 usable sub-questions for report-mode runs.
        "question_generator":     "high",
        "writer":                 "high",
        "report_evaluator":       "medium",
        "gap_question_generator": "medium",
        "report_finalizer":       "medium",
        "sub_result_collector":   "low",
    }

    def __init__(self):
        """Initialises the OpenRouter HTTP session using the API key from environment
        variables. Get a free key at https://openrouter.ai/keys — no payment method
        required to call `:free` models."""
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Get a free key at https://openrouter.ai/keys "
                "and add it to backend/.env."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            # Optional but recommended by OpenRouter for attribution/rankings — not
            # required for calls to succeed.
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
            "X-Title":      "DS-STAR",
        })

    def complete(self, agent: str, prompt: str, task_id: str | None = None) -> dict:
        """Routes a prompt to the appropriate model for the given agent.

        Looks up the agent's tier, selects the corresponding model,
        makes the API call, and returns the response with usage metadata.
        All response data is returned so the observability layer can log
        cost and latency without making a second API call.

        Args:
            agent: The DS-STAR agent making the call. Must be a key in
                AGENT_TIERS. Unknown agents default to medium tier.
            prompt: The full prompt string to send to the model.
            task_id: When given, retry attempts and terminal failures are written to
                tasks.logs via log_event — the same feed the UI polls and any API
                caller reads from GET /api/v1/get_task/{id}, so a caller watching
                either has visibility into "retrying" vs. "still waiting on a slow
                free-tier response" vs. "genuinely failed", not silence either way.
                Omit for out-of-task usage (e.g. `uv run python llm_router.py`).

        Returns:
            A dict containing the following keys:
                text: The model's response as a string.
                model: The actual model id used.
                input_tokens: Number of tokens in the prompt.
                output_tokens: Number of tokens in the response.
                duration_ms: Wall-clock API latency in milliseconds.
                agent: The agent name passed in.
                tier: The tier assigned to that agent.

        Raises:
            RuntimeError: If the OpenRouter call fails due to network issues,
                invalid credentials, or a non-retryable/exhausted-retry error.

        Example:
            result = router.complete(
                agent="planner",
                prompt="Generate a plan step for: total volume by currency"
            )
            print(result["text"])
        """
        # Look up which tier this agent belongs to.
        # Unknown agents default to medium — safe fallback but should be investigated.
        tier = self.AGENT_TIERS.get(agent, "medium")
        model = self.models_for_profile(get_speed_profile())[tier]

        start = time.time()
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.session.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=LLM_TIMEOUT_S,
                )
            except requests.RequestException as e:
                last_error = str(e)
                if attempt < MAX_RETRIES:
                    if task_id:
                        log_event(task_id, agent,
                                   f"Network error calling {model} ({last_error[:100]}) — "
                                   f"retrying (attempt {attempt + 2}/{MAX_RETRIES + 1})",
                                   "error", {"retry_attempt": attempt + 2})
                    time.sleep(2 ** attempt)
                    continue
                if task_id:
                    log_event(task_id, agent,
                               f"Model call failed after {MAX_RETRIES + 1} attempts: {last_error[:150]}",
                               "error")
                raise RuntimeError(
                    f"LLMRouter API call failed for agent '{agent}' with model '{model}': {last_error}") from e

            if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                last_error = f"{response.status_code}: {response.text[:300]}"
                if task_id:
                    log_event(task_id, agent,
                               f"{model} returned {response.status_code} (rate-limited/overloaded) — "
                               f"retrying (attempt {attempt + 2}/{MAX_RETRIES + 1})",
                               "error", {"retry_attempt": attempt + 2, "http_status": response.status_code})
                time.sleep(2 ** attempt)
                continue

            if response.status_code != 200:
                if task_id:
                    log_event(task_id, agent,
                               f"Model call failed: {response.status_code} {response.text[:150]}",
                               "error")
                raise RuntimeError(
                    f"LLMRouter API call failed for agent '{agent}' with model '{model}': "
                    f"{response.status_code} {response.text[:500]}"
                )

            data = response.json()

            # OpenRouter can return HTTP 200 with an error body instead of a completion
            # (e.g. upstream provider hiccup) — this crashed with a bare, undiagnosable
            # `KeyError: 'choices'` before this check existed. Treat it exactly like a
            # retryable HTTP error: retry with backoff if attempts remain, else raise
            # with the actual response body so the failure is diagnosable.
            if not data.get("choices"):
                last_error = f"200 with no choices in body: {response.text[:300]}"
                if attempt < MAX_RETRIES:
                    if task_id:
                        log_event(task_id, agent,
                                   f"{model} returned 200 but no completion — "
                                   f"retrying (attempt {attempt + 2}/{MAX_RETRIES + 1})",
                                   "error", {"retry_attempt": attempt + 2})
                    time.sleep(2 ** attempt)
                    continue
                if task_id:
                    log_event(task_id, agent, f"Model call failed: {last_error}", "error")
                raise RuntimeError(
                    f"LLMRouter API call failed for agent '{agent}' with model '{model}': {last_error}")

            duration_ms = int((time.time() - start) * 1000)
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return {
                "text":          choice["message"]["content"] or "",
                "model":         data.get("model", model),
                "input_tokens":  usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "duration_ms":   duration_ms,
                "agent":         agent,
                "tier":          tier,
            }

        raise RuntimeError(
            f"LLMRouter API call failed for agent '{agent}' with model '{model}' "
            f"after {MAX_RETRIES + 1} attempts: {last_error}")


# ── Quick test ────────────────────────────────────────────────────────────────
# Run directly to verify the router is working:
#   uv run python llm_router.py
if __name__ == "__main__":
    router = LLMRouter()

    result = router.complete(
        agent="planner",
        prompt="Generate one specific plan step to answer this query: what is the total transaction volume by currency?"
    )

    print(f"Agent:    {result['agent']} ({result['tier']} tier)")
    print(f"Model:    {result['model']}")
    print(f"Response: {result['text']}")
    print(f"Tokens:   {result['input_tokens']} in / {result['output_tokens']} out")
    print(f"Duration: {result['duration_ms']}ms")
