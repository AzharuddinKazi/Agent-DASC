# Agent Spec: Verifier

## Role (paper-faithful)
Binary LLM judge. Evaluates whether the current cumulative plan and its code implementation is sufficient to answer the user's original question. Returns exactly "Yes" or "No".

## Position in Graph
```
Docker execution → result (stdout)
    → [Verifier]
    → "Yes" → [CP2: human confirms]
    → "No"  → [Router]
```

## Paper Prompt (verbatim — Appendix L.4)
```
You are an expert data analysist.
Your task is to check whether the current plan and its code implementation is enough to
answer the question.
# Plan
1. {Step 1}
...
k. {Step k}
# Code
```python
{code}
```
# Execution result of code
{result}
# Question
{question}
# Your task
- Verify whether the current plan and its code implementation is enough to answer the
  question.
- Your response should be one of 'Yes' or 'No'.
- If it is enough to answer the question, please answer 'Yes'.
- Otherwise, please answer 'No'.
```

## IMPORTANT: No {summaries} in Verifier
The paper does NOT pass data summaries to the Verifier. The Verifier judges sufficiency from plan + code + result + question only. This is intentional.

## Template Variables
| Variable | Value |
|---|---|
| `{plan}` | All steps so far as numbered list: "1. {Step 1}\n...\nk. {Step k}" |
| `{code}` | Current cumulative Python script |
| `{result}` | Printed stdout from most recent Docker execution |
| `{question}` | User's original natural language query |

## Outputs
```python
class VerifierOutput(BaseModel):
    verdict: Literal["Yes", "No"]   # paper uses Yes/No exactly
    raw_response: str               # full LLM response for logging
```

## Response Parsing
Take the first occurrence of "Yes" or "No" (case-insensitive) in the response. If neither is found, treat as "No" (conservative default).

## Behaviour Rules
- MUST return "No" if `result` contains an unhandled exception / stack trace
- MUST return "No" if execution result is empty and the question expects data output
- Evaluates against the ORIGINAL question, not just whether code ran without errors
- Does NOT explain its reasoning — binary only (paper design)

## Force-Exit (graph executor responsibility, not Verifier)
When `iteration >= max_iterations` (default: 5), the graph executor triggers force-exit checkpoint BEFORE calling Verifier. Verifier still runs; its verdict is included in the force-exit payload shown to the human.

## Extension: CP2 Checkpoint
When Verifier returns "Yes", graph triggers CP2 before Finalyzer:
```python
class CP2Payload(BaseModel):
    question: str
    plan: list[str]         # all steps
    result: str             # final execution stdout
    code: str               # final cumulative code
    verifier_verdict: str   # "Yes"
```
Human approves → Finalyzer (base) or SubquestionGenerator (DSSTAR+) runs.
Human rejects → [LOCKED] same choice as force-exit: **Abandon** or **Give a hint and
continue**. A hint routes back through the Router (as if Verifier had returned "No") and
counts against the same shared hint-round budget as force-exit — see
`specs/features/checkpoints-hitl.md` for the exact iteration mechanics.

## Must NOT Do
- Return anything other than "Yes" or "No"
- Use {summaries} / data descriptions in the prompt
- Suggest fixes or next steps
- Modify any state

## Test Scenarios

### Unit (mocked LLM)
- Response "Yes" → verdict: "Yes"
- Response "No" → verdict: "No"
- Ambiguous response → parsed as "No" (conservative)
- Prompt does NOT contain {summaries} variable
- Empty execution result for numeric question → verdict: "No"

### Integration (real LLM + real execution results)
- Verifier returns "Yes" when result clearly and completely answers the question
- Verifier returns "No" when result is intermediate (raw DataFrame, question asks for chart)
- Verifier returns "No" when stdout contains "Error:" or "Traceback"
