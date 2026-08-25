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


def get_model_override(agent: str) -> str | None:
    """Admin Control Panel per-agent model override (see TASKS.md) — same shape as
    get_speed_profile() below: read fresh on every call, fails closed (None, meaning "fall
    through to the normal tier/OPENROUTER_MODEL_CODER lookup") on any DB error so a
    Postgres hiccup never breaks every LLM call in the pipeline."""
    from db import supabase
    try:
        row = supabase.table("agent_model_overrides").select("model_id").eq("agent_name", agent).execute()
        return row.data[0]["model_id"] if row.data else None
    except Exception:
        return None


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
# error and no way to tell "still working" from "silently dead". Override via env for
# local inference: a consumer-GPU 14B model generating a multi-thousand-token
# completion (observed up to ~8k tokens from the coder/writer agents) can genuinely
# take several minutes — 120s is tuned for a hosted API's token throughput, not a
# single local GPU's.
LLM_TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "120"))

# No `max_tokens` was ever sent in the request body — meaning every call rode on
# whatever the provider's own unstated default completion cap happened to be. Silently
# fine for most agents' short/structured outputs, but writer.py explicitly asks for a
# "genuinely comprehensive" multi-section report ("do not artificially limit length")
# — observed live 2026-08-23 (see TASKS.md): a real report got cut off mid-sentence
# with no closing JSON braces at all, `final_result` unparseable, "Report could not be
# parsed" in the UI and a 422 from the new docx-export endpoint. Setting an explicit,
# generous ceiling doesn't force shorter completions to run longer — it only raises the
# limit, so this is safe to apply to every agent, not just the long-form ones.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))

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

    Works unmodified against any OpenAI-compatible `/chat/completions` endpoint, not
    just OpenRouter — including a local Ollama server, which exposes exactly this
    shape at http://localhost:11434/v1. To run entirely local: set
    OPENROUTER_BASE_URL="http://localhost:11434/v1", OPENROUTER_API_KEY to any
    non-empty placeholder (Ollama ignores it — the check below just requires the var
    be set), and the OPENROUTER_MODEL_* vars to your local Ollama tags. Ollama's
    OpenAI-compat layer already strips a thinking model's reasoning into a separate
    `reasoning` field, so `choice["message"]["content"]` below stays clean without any
    special-casing. Bake each tag's context window in via a Modelfile
    (`PARAMETER num_ctx N`) rather than relying on a default — this endpoint accepts no
    `options`/`num_ctx` override, and an uncapped default context can be large enough
    to spill part of the model onto CPU (slow) or exceed VRAM outright.

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

    # Maps tier names to OpenRouter model ids, plus a "coder" pseudo-tier (see
    # _CODE_AGENTS below) — four keys per profile, not three. Researched and assigned
    # 2026-08-23 against OpenRouter's live catalog (GET /api/v1/models) and current
    # published benchmarks; re-verify before trusting these long-term, both change.
    #
    # All four are free-tier as of this writing — no billing required.
    _FREE_MODELS = {
        # 550B MoE (55B active), NVIDIA's current largest free model — 48.2 on
        # Artificial Analysis's Intelligence Index (reasoning/knowledge/math/coding
        # composite) and 71.9% SWE-bench Verified, a real step up from the 120B model
        # this replaced. Used for the agents where reasoning quality matters most.
        "high":   os.getenv("OPENROUTER_MODEL_HIGH",   "nvidia/nemotron-3-ultra-550b-a55b:free"),
        # 30B MoE (3B active) — solid general-purpose middle ground. Replaces
        # openai/gpt-oss-20b:free, which OpenRouter retired from its free tier
        # 2026-08 (started 404ing with "use openai/gpt-oss-20b [paid] instead").
        # Picked a same-vendor (nvidia) model as "high"/"low" for consistent behavior
        # across tiers rather than re-introducing a different provider's free model.
        "medium": os.getenv("OPENROUTER_MODEL_MEDIUM", "nvidia/nemotron-3-nano-30b-a3b:free"),
        # Small/fast, tuned for lightweight classification-style tasks.
        "low":    os.getenv("OPENROUTER_MODEL_LOW",    "nvidia/nemotron-nano-9b-v2:free"),
        # Reuses "high" rather than introducing a separate untested free model — its
        # 71.9% SWE-bench Verified score already makes it a solid code-generation pick
        # on its own merits, not just a fallback. See _CODE_AGENTS for who uses this.
        "coder":  os.getenv("OPENROUTER_MODEL_CODER_FREE", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    }

    # Paid models actually chosen for cheap-and-capable, not just "not free" — this
    # profile exists for real speed/quality testing against billed models, not
    # everyday use. Previously a single flat meta-llama/llama-3.1-8b-instruct:nitro
    # across every tier, including "high" — an 8B model doing planner/verifier/writer
    # work, weaker than the *free* tier's model it was supposedly upgrading from. Each
    # tier now gets its own pick. Verify current pricing/availability at
    # https://openrouter.ai/models before relying on these, both change.
    _FAST_PAID_MODELS = {
        # Qwen3-235B-A22B (262K ctx) — large capable MoE at ~$0.09/$0.55 per M
        # input/output tokens, cheap for its scale. General reasoning, not code-gen —
        # see "coder" below for that.
        "high":   os.getenv("OPENROUTER_MODEL_HIGH_FAST",   "qwen/qwen3-235b-a22b-2507"),
        # Gemini 2.5 Flash-Lite — ~$0.10/$0.40 per M, 1M ctx, built for low-latency/
        # reliable structured output, which is most of what router/query_clarity/
        # report_evaluator/gap_question_generator/report_finalizer actually need.
        "medium": os.getenv("OPENROUTER_MODEL_MEDIUM_FAST", "google/gemini-2.5-flash-lite"),
        # low (analyzer, sub_result_collector) is lightweight, infrequent work — not
        # the speed bottleneck this profile exists to test, so it stays on the same
        # genuinely free model as the free profile rather than paying for it too.
        "low":    os.getenv("OPENROUTER_MODEL_LOW_FAST",    "nvidia/nemotron-nano-9b-v2:free"),
        # Qwen3-Coder-Next — ~$0.12/$0.80 per M, 262K ctx, purpose-built coding-agent
        # model: 70.6% SWE-bench Verified (vs. the 235B general model's weaker showing
        # on the same benchmark). See _CODE_AGENTS below for who uses this.
        "coder":  os.getenv("OPENROUTER_MODEL_CODER_FAST", "qwen/qwen3-coder-next"),
    }

    @classmethod
    def models_for_profile(cls, profile: str) -> dict:
        return cls._FAST_PAID_MODELS if profile == "fast_paid" else cls._FREE_MODELS

    # coder and debugger both read/write Python; finalizer does too despite
    # AGENT_TIERS nominally calling it "medium — formats a known result into output
    # structure" — finalizer.py actually generates and executes a real Python script
    # (see FINALIZER_PROMPT), the same job as coder/debugger, with its own bounded
    # self-debug loop. Live-tested against llama3.1:8b (medium tier's old local
    # default): it burned both debug attempts on plain syntax errors (an unterminated
    # string, "importfisher_exact" with a missing space) and the task failed outright.
    # Once correctness-critical code generation is actually happening, the model needs
    # to match coder/debugger, not whatever tier label AGENT_TIERS happens to give it —
    # so all three look up the "coder" key in _FREE_MODELS/_FAST_PAID_MODELS above
    # (profile-aware, unlike the old flat _AGENT_OVERRIDES) rather than their nominal
    # tier's generalist model.
    _CODE_AGENTS = {"coder", "debugger", "finalizer"}

    # Manual pin, e.g. for a local Ollama tag — takes priority over everything above
    # regardless of speed profile (OPENROUTER_MODEL_CODER has no _FREE/_FAST suffix on
    # purpose: someone pinning a specific model doesn't want it silently swapped out
    # from under them by a profile toggle). Unset by default, in which case complete()
    # falls through to the profile-aware "coder" key instead.
    _AGENT_OVERRIDES = {
        "coder":     os.getenv("OPENROUTER_MODEL_CODER"),
        "debugger":  os.getenv("OPENROUTER_MODEL_CODER"),
        "finalizer": os.getenv("OPENROUTER_MODEL_CODER"),
    }

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
        # multi-file prompt — the medium tier's old default (gpt-oss-20b:free) was
        # observed garbling the array mid-generation (truncated/malformed JSON) on
        # exactly this shape of task, silently producing 0 usable sub-questions for
        # report-mode runs. Medium's default has since changed (see _FREE_MODELS
        # above) — re-verify this failure mode against the new model before trusting
        # it's still a reason to keep this agent on "high".
        "question_generator":     "high",
        "writer":                 "high",
        "report_evaluator":       "medium",
        "gap_question_generator": "medium",
        "report_finalizer":       "medium",
        "sub_result_collector":   "low",
    }

    def __init__(self):
        """Initialises the OpenAI-compatible HTTP session using the API key from
        environment variables. Get a free OpenRouter key at https://openrouter.ai/keys
        — no payment method required to call `:free` models. Running against a local
        Ollama server instead (see the class docstring): this still needs to be set to
        *something* non-empty — Ollama doesn't check the value — so use any
        placeholder string."""
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Get a free key at https://openrouter.ai/keys "
                "and add it to backend/.env — or, if OPENROUTER_BASE_URL points at a local "
                "Ollama server, set this to any non-empty placeholder (Ollama ignores it)."
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
        # Look up which tier this agent belongs to — except coder/debugger/finalizer,
        # which use the profile's "coder" pick regardless of their nominal tier (see
        # _CODE_AGENTS above). Unknown non-code agents default to medium — safe
        # fallback but should be investigated.
        tier = "coder" if agent in self._CODE_AGENTS else self.AGENT_TIERS.get(agent, "medium")
        model = (
            get_model_override(agent)
            or self._AGENT_OVERRIDES.get(agent)
            or self.models_for_profile(get_speed_profile())[tier]
        )

        start = time.time()
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.session.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": LLM_MAX_TOKENS,
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

            # Not retried (a longer completion attempt would just as plausibly hit the
            # same LLM_MAX_TOKENS ceiling again) — surfaced so a truncated report/answer
            # is a visible, diagnosable event next time instead of a bare downstream
            # JSON-parse failure with no indication of why.
            if choice.get("finish_reason") == "length":
                logger.warning(f"{agent} ({model}) hit the {LLM_MAX_TOKENS}-token completion "
                                f"cap — output is truncated")
                if task_id:
                    log_event(task_id, agent,
                               f"{model}'s response hit the token limit and was cut off — "
                               f"the result may be incomplete or fail to parse",
                               "error")

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
