# Agent Spec: Planner

## Role (paper-faithful)
Generates ONE step at a time. Called twice with different prompts:
- `planner_init` — generates the very first step as a simple starting point
- `planner_next` — generates the next step given current results (called after Router says "Add Step")

The plan is built incrementally as execution proceeds — there is no full upfront plan.

## Position in Graph
```
[Analyzer] → summaries
    → [Planner_init] → step_1
    → [CP1: human approves step_1]  ← EXTENSION (not in paper)
    → [Coder_init]
    → ... loop ...
    → Router says "Add Step"
    → [Planner_next] → step_N
    → [Coder_next]
```

## Paper Prompts (verbatim)

### planner_init
```
You are an expert data analyst.
In order to answer factoid questions based on the given data, you have to first plan
effectively.
# Question
{question}
# Given data:
{summaries}
# Your task
Suggest your very first step to answer the question above.
Your first step does not need to be sufficient to answer the question.
Just propose a very simple initial step, which can act as a good starting point to
answer the question.
Your response should only contain an initial step.
```

### planner_next
```
You are an expert data analyst.
In order to answer factoid questions based on the given data, you have to first plan
effectively.
Your task is to suggest next plan to do to answer the question.
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
Suggest your next step to answer the question above.
Your next step does not need to be sufficient to answer the question, but if it
requires only final simple last step you may suggest it.
Just propose a very simple next step, which can act as a good intermediate point to
answer the question.
Of course your response can be a plan which could directly answer the question.
Your response should only contain a next step without any explanation.
```

## Template Variables

### planner_init
| Variable | Value |
|---|---|
| `{question}` | User's natural language query |
| `{filenames}` | Comma-separated list of all source identifiers |
| `{filenames_and_summaries}` | Per-file pairs: `{filename #1}\n{summary #1}\n...\n{filename #N}\n{summary #N}` |

### planner_next
| Variable | Value |
|---|---|
| `{question}` | User's natural language query |
| `{filenames}` | Comma-separated list of all source identifiers |
| `{filenames_and_summaries}` | Per-file pairs (same as init) |
| `{plan}` | All steps so far: "1. {Step 1}\n...\nk. {Step k}" |
| `{result}` | Printed stdout from most recent code execution |

Note: `planner_next` does NOT receive `{current_step}` separately — the current step is the last entry in `{plan}`.

## Extension: GraphRAG Context Injection
The paper does not include GraphRAG. As an extension, domain knowledge from GraphRAG is appended to the `{summaries}` variable before the prompt is rendered:

```
{summaries}

# Domain Knowledge
{graphrag_context}
```

This keeps the paper's prompt structure intact while injecting domain context.

## Extension: CP1 Checkpoint
The paper has no human-in-the-loop. Our extension adds CP1 after `planner_init`:
- The first generated step is shown to the human
- Human approves → Coder_init runs
- Human rejects with hint → Planner_init reruns with hint appended to question

CP1 payload:
```python
class CP1Payload(BaseModel):
    first_step: str             # the generated step_1 text
    summaries_preview: str      # first 500 chars of summaries for context
    detected_mode: Literal["base", "plus"]           # system's mode guess [LOCKED]
    mode_override: Literal["base", "plus"] | None = None  # set if human flips it
```
[LOCKED] CP1 is also where DSSTAR+ mode selection is confirmed — see
`specs/agents/finalyzer.md` for the auto-detection heuristic. The human sees the system's
guess alongside the first step and can override it before Coder_init runs, instead of the
system silently committing to a mode from keyword matching alone.

## Outputs
```python
class PlannerOutput(BaseModel):
    step_text: str              # the generated step (plain text, one step only)
    step_number: int            # 1 for planner_init, N for planner_next
```

## Behaviour Rules
- Each call generates EXACTLY ONE step — not a full plan
- Step text must be a clear, human-readable instruction (no code)
- `planner_next` is ONLY called when Router outputs "Add Step"
- When Router outputs "Step N" (truncate), Planner is NOT called — Coder regenerates from Step N directly
- The accumulated plan (all steps so far) is maintained in graph state, not regenerated

## Must NOT Do
- Generate more than one step per call
- Generate Python code
- Reference tables or columns not present in summaries

## Test Scenarios

### Unit (mocked LLM)
- `planner_init` returns a single plain-text step, no code
- `planner_next` is only called when Router says "Add Step" — not on "Step N"
- GraphRAG context appears in rendered prompt when available
- CP1 payload contains step_text and summaries_preview

### Integration (real LLM + test fixture)
- planner_init generates a sensible first step for a "total revenue by month" query
- planner_next generates a coherent next step that builds on the current result
- Generated steps are implementable by Coder without clarification
