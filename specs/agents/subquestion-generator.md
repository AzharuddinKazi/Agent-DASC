# Agent Spec: SubquestionGenerator (DS-STAR+ only)

## Role (paper-faithful — Appendix M.1)
Called at the start of DSSTAR+ mode and again iteratively to strengthen the report. Has two prompts:
- **Init** — generates the initial set of factoid sub-questions from scratch
- **Refine** — generates SUPPLEMENTARY sub-questions based on gaps in the current draft report

Both prompts output JSON: `list[{"question": str}]`

## Position in Graph (DSSTAR+ pipeline)
```
[CP2: DSSTAR+ mode detected]
    → [SubquestionGenerator_init]
    → sub_questions_round_1: list[str]   (max 8)
    → [DS-STAR pipeline × N] (one per sub-question, reusing summaries)
    → [Writer_init] → draft_report
    → [refine_round_review CP] → human: "Refine further" or "Finalize"
    → "Refine further":
        [SubquestionGenerator_refine] → sub_questions_round_k: list[str] (max 8)
        → [DS-STAR pipeline × M]
        → [Writer_refine] → updated draft_report
        → back to [refine_round_review CP]
    → "Finalize" → [CP3]
```

## Paper Prompts (verbatim — Appendix M.1)

### Init prompt
```
You are an expert data analysist.
Your task is to write a comprehensive data science report to the given question by using
the files/documents listed below.
In order to do this, you have to first suggest multiple data analysis questions that
should be answered to write the report.
# Given data: {filenames}
{filenames_and_summaries}
# Question
{question}
# Your task
- Suggest multiple factoid data analysis questions that are required to write the report
  really well.
- All the questions should be well-answered using the given data.
- All questions should be answered independently.
- Generate as much as you can.
- Return in valid JSON format:
  Questions = {'question': str}
  Return: list[Questions]
```

### Refine prompt
```
You are an expert data analysist.
Your task is to complement the given data science report of the given question.
In order to do this, you have to suggest supplementary multiple data analysis questions
that can strengthen the report.
# Given data: {filenames}
{filenames_and_summaries}
# Given data science report:
{report}
# Question
{question}
# Your task
- Suggest multiple factoid data analysis questions that are required to complement the
  report.
- All questions should contain new information that is not included in the report.
- All the questions should be well-answered using the given data.
- All questions should be answered independently.
- Return in valid JSON format:
  Questions = {'question': str}
  Return: list[Questions]
```

## Template Variables

### Init
| Variable | Value |
|---|---|
| `{filenames}` | Comma-separated list of source identifiers |
| `{filenames_and_summaries}` | Per-file: `{filename #1}\n{summary #1}\n...` |
| `{question}` | User's original open-ended query |

### Refine
| Variable | Value |
|---|---|
| `{filenames}` | Same as init |
| `{filenames_and_summaries}` | Same as init |
| `{report}` | Current draft report from Writer_init |
| `{question}` | User's original open-ended query |

## Outputs
```python
class SubquestionGeneratorOutput(BaseModel):
    sub_questions: list[str]        # parsed from JSON response
    raw_json: str                   # raw LLM response for logging
    round: Literal["init", "refine"]
```

## JSON Parsing
Response must be valid JSON matching `list[{"question": str}]`. If parsing fails, retry once. If still fails, log error and continue with empty list (Writer handles gracefully).

## Behaviour Rules [LOCKED]
- Paper says "generate as much as you can" — the paper sets no numeric limit. That's an
  open-ended instruction by design, which is exactly why we cap it: each sub-question is a
  full DS-STAR pipeline run (up to 11 iterations itself), so an uncapped round is an
  uncapped cost multiplier.
- Cap: **8 sub-questions per round** (init or refine)
- Refine sub-questions MUST be novel — "not included in the report" (paper rule)
- All sub-questions must be answerable independently using available data
- Each sub-question runs through the FULL base DS-STAR pipeline (Analyzer already ran — reuse summaries, start from Planner_init)
- No automatic refinement rounds. After `Writer_init` and after every `Writer_refine`, the
  `refine_round_review` checkpoint fires (see `specs/features/checkpoints-hitl.md`) showing
  the draft report with two actions: **Refine further** (runs another
  SubquestionGenerator_refine → DS-STAR × M → Writer_refine round) or **Finalize** (proceeds
  to CP3). This replaces the previous "3 automatic rounds" default — cost is spent only when
  a human asks for another round.

## Sub-question Execution
Each sub-question is solved by the base DS-STAR pipeline:
```python
class SubquestionAnswer(BaseModel):
    sub_question: str
    answer: str             # stdout from Finalyzer execution
    code: str               # final cumulative code
    chart_files: list[str]  # chart filenames in OUTPUT_DIR, if any
    round: Literal["init", "refine"]
```

## Must NOT Do
- Return questions that cannot be answered from the available data
- Return questions already answered in the current report (refine prompt)
- Return invalid JSON
- Run analyses itself — only generates questions

## Test Scenarios

### Unit (mocked LLM)
- Init returns valid JSON list of sub-questions
- Refine returns only questions NOT answered in the provided draft report
- JSON parse failure → retry once → empty list on second failure
- Sub-questions capped at 8 per round in implementation
- Each sub-question is independently answerable (no cross-references between questions)

### Integration (real LLM + test fixture)
- Init sub-questions collectively cover the main analytical dimensions of the query
- Refine sub-questions add genuinely new information not present in draft report
- All sub-questions are solvable by base DS-STAR on the test fixture without errors
