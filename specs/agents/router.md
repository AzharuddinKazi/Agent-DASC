# Agent Spec: Router

## Role (paper-faithful)
Called when Verifier returns "No". Decides between two options:
- **"Add Step"** — the plan so far is fine but incomplete; add a new step via Planner_next
- **"Step K"** — step K is wrong; truncate the plan back to step K-1 and regenerate step K via Coder_next

## Position in Graph
```
[Verifier] → "No"
    → [Router]
    → "Add Step" → [Planner_next] → new_step → [Coder_next]
    → "Step K"   → truncate plan to K-1 → [Coder_next] (regenerate step K)
```

## Paper Prompt (verbatim)
```
You are an expert data analyst.
Since current plan is insufficient to answer the question, your task is to decide how to
refine the plan to answer the question.
# Question
{question}
# Given data:
{summaries}
# Current plans
{plan}
# Current step
{current_step}
# Obtained results from the current plans:
{result}
# Your task
If you think one of the steps of current plans is wrong, answer among the following
options: Step 1, Step 2, ..., Step K.
If you think we should perform new NEXT step, answer as 'Add Step'.
Your response should only be Step 1 ... Step K or Add Step.
```

## Template Variables
| Variable | Value |
|---|---|
| `{question}` | User's original natural language query |
| `{summaries}` | AnalyzerOutput.summaries |
| `{plan}` | All steps generated so far (numbered list) |
| `{current_step}` | The step most recently executed |
| `{result}` | Printed stdout from most recent Docker execution |

## Outputs
```python
class RouterOutput(BaseModel):
    action: Literal["add_step", "truncate"]
    truncate_to_step: int | None    # K-1 (plan is truncated here); None if action == "add_step"
    raw_response: str               # full LLM response for logging
```

## Response Parsing
- "Add Step" (case-insensitive) → `action: "add_step"`
- "Step N" (case-insensitive, N is integer) → `action: "truncate"`, `truncate_to_step: N - 1`
- If N == 1 (truncate to step 0) → treat as `action: "add_step"` (can't truncate before step 1)
- Unrecognised response → default to `action: "add_step"` (conservative)

## What Happens After Router

### "Add Step"
1. `Planner_next` is called with current plan + current results
2. `Planner_next` generates the next step text
3. `Coder_next` is called with `base_code` = current code, `current_plan` = new step
4. Debugger → Docker execution → Verifier

### "Step K" (truncate)
1. Plan is truncated: steps K, K+1, ... are removed from state
2. Code is rolled back: `base_code` = code at completion of step K-1
3. `Coder_next` is called with `base_code` = code at step K-1, `current_plan` = step K text (regenerate)
4. Debugger → Docker execution → Verifier
5. Planner is NOT called — the step text stays the same, only the code changes

## Extension: Force-Exit Checkpoint [LOCKED]
When `iteration >= max_iterations` (default: 5), the graph executor does NOT call Router. Instead:
1. Force-exit checkpoint fires (round 1, shown to human)
2. Human chooses: **Abandon**, or provide a hint to continue
3. If hint given: it's appended to the `{question}` variable in all subsequent prompts;
   iteration counter resets to `max_iterations - 3` (3 more tries)
4. Router is called again with enriched question
5. If iteration reaches `max_iterations + 3` again with still no "Yes" verdict (round 2),
   force-exit fires ONE more time — but this time the hint-and-continue-in-place option is
   gone. Only **Abandon** or **Start a Fresh Session** (pre-filled with the accumulated
   hints and original question) are offered.

This caps the guided-retry mechanism at 2 hint rounds (11 iterations total: 5 + 3 + 3)
before forcing a decision — bounded but still lets a human steer the system toward a
correct answer. See `specs/features/checkpoints-hitl.md` for the full iteration table.

## Must NOT Do
- Return anything other than "Add Step" or "Step N"
- Generate code or plan steps
- Explain its reasoning in the response (paper design — terse output only)

## Test Scenarios

### Unit (mocked LLM)
- Response "Add Step" → action: "add_step"
- Response "Step 2" → action: "truncate", truncate_to_step: 1
- Response "Step 1" → action: "add_step" (can't truncate before step 1)
- Unrecognised response → action: "add_step" (fallback)
- After "Add Step": Planner_next is called (not Coder_next directly)
- After "Step K": Coder_next is called with base_code from step K-1 (not Planner_next)

### Integration (real LLM)
- Router returns "Add Step" when result is intermediate (needs another step)
- Router returns "Step 2" when step 2's output was wrong and caused downstream errors
- After truncation to step K-1, Coder_next regenerates step K with corrected logic
