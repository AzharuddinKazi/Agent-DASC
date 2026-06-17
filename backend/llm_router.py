"""
LLM routing layer for DS-STAR.

All LLM calls in the system go through this module.
No agent node or API handler should ever call Gemini directly.
Swapping models or adding new providers requires changes only here.

Typical usage:
    router = LLMRouter()
    result = router.complete(agent="planner", prompt="...")
"""

from google import genai
from dotenv import load_dotenv
import os
import time



load_dotenv()


class LLMRouter:
    """Routes LLM calls to the appropriate model based on agent type.

    DS-STAR uses a three-tier model assignment to balance cost and quality.
    High-tier agents handle complex reasoning and code generation.
    Medium-tier agents handle structured, bounded tasks.
    Low-tier agents handle fast, cheap classification and profiling.

    Attributes:
        MODELS: Maps tier names to Gemini model strings. Change a model
            here and it applies everywhere — no other file needs updating.
        AGENT_TIERS: Maps each DS-STAR agent to its quality tier.
        client: The Gemini API client instance, initialised once and reused.

    Example:
        router = LLMRouter()
        result = router.complete(agent="planner", prompt="...")
        print(result["text"])
    """

    # Maps tier names to Gemini model strings.
    # To swap a model, change it here — nowhere else in the codebase.
    MODELS = {
        "high":   "gemini-2.5-pro",    # slowest, most capable — critical agents
        "medium": "gemini-2.5-flash",  # fast, capable — structured tasks
        "low":    "gemini-2.5-flash",  # fast, cheap — classification and profiling
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
        "query_clarity": "low",     # classifies ambiguity + mode — runs before every task
        "analyzer":      "low",     # generates file profiling scripts — runs once per file
    }

    def __init__(self):
        """Initialises the Gemini client using the API key from environment variables."""
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def complete(self, agent: str, prompt: str) -> dict:
        """Routes a prompt to the appropriate model for the given agent.

        Looks up the agent's tier, selects the corresponding model,
        makes the API call, and returns the response with usage metadata.
        All response data is returned so the observability layer can log
        cost and latency without making a second API call.

        Args:
            agent: The DS-STAR agent making the call. Must be a key in
                AGENT_TIERS. Unknown agents default to medium tier.
            prompt: The full prompt string to send to the model.

        Returns:
            A dict containing the following keys:
                text: The model's response as a string.
                model: The actual model version used.
                input_tokens: Number of tokens in the prompt.
                output_tokens: Number of tokens in the response.
                duration_ms: Wall-clock API latency in milliseconds.
                agent: The agent name passed in.
                tier: The tier assigned to that agent.

        Raises:
            google.genai.errors.APIError: If the Gemini API call fails
                due to network issues, invalid credentials, or rate limits.

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
        model = self.MODELS[tier]

        # Record start time to measure API latency.
        start = time.time()

        try:
            # Make the API call to Gemini to generate content.
            response = self.client.models.generate_content(
                model=model,
                contents=prompt
            )
        except genai.errors.APIError as e:
            raise genai.errors.APIError(
                f"LLMRouter API call failed for agent '{agent}' with model '{model}': {str(e)}") from e
        
        duration_ms = int((time.time() - start) * 1000)

        return {
            "text":          response.text,
            "model":         response.model_version,
            "input_tokens":  response.usage_metadata.prompt_token_count,
            "output_tokens": response.usage_metadata.candidates_token_count,
            "duration_ms":   duration_ms,
            "agent":         agent,
            "tier":          tier,
        }


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