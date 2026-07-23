# Agent Spec: Finalyzer

## Role (paper-faithful)
Applies formatting guidelines to the final code and result, producing a clean, submission-ready Python script that prints the answer in the required format. This is the BASE DS-STAR finalizer — it formats code output, NOT an HTML report generator.

Report generation is handled by the DSSTAR+ pipeline (SubquestionGenerator + Writer agents).

## Position in Graph
```
[CP2: human confirms result]
    → [Finalyzer]  (base mode: direct factoid answer)
    → FinalizerOutput: formatted Python code
    → Docker execution → final printed answer
    → [CP3: approve / save]

OR (DSSTAR+ mode, detected by auto-detection):
    → [SubquestionGenerator] → [Writer]
    → [CP3: approve / save HTML report]
```

## Paper Prompt (verbatim)
```
You are an expert data analyst.
You will answer factoid question by loading and referencing the files/documents listed
below.
You also have a reference code.
Your task is to make solution code to print out the answer of the question following the
given guideline.
# Given data:
{summaries}
# Reference code
```python
{code}
```
# Execution result of reference code
{result}
# Question
{question}
# Guidelines
{guidelines}
# Your task
Modify the solution code to print out answer to follow the given guidelines.
If the answer can be obtained from the execution result of the reference code, just
generate a Python code that prints out the desired answer.
The code should be a single-file Python program that is self-contained and can be
executed as-is.
Your response should only contain a single code block.
Do not use try: and except: to prevent error. I will debug it later.
```

## Template Variables
| Variable | Value |
|---|---|
| `{summaries}` | AnalyzerOutput.summaries |
| `{code}` | Final cumulative code from last Coder step |
| `{result}` | Printed stdout from last Docker execution |
| `{question}` | User's original natural language query |
| `{guidelines}` | Output format instructions (see below) |

## Guidelines (Extension — not in paper)
The paper used task-specific guidelines for benchmark evaluation. For our tool:

```
Base mode guidelines:
- Print the answer clearly and concisely
- If the answer is numeric, include units where applicable
- If the answer is tabular, print as a formatted table
- If charts were generated, confirm their location in OUTPUT_DIR
```

## Outputs
```python
class FinalizerOutput(BaseModel):
    mode: Literal["base", "plus"]   # determined before Finalyzer is called
    code: str                        # formatted Python script (base mode)
    final_result: str                # stdout after executing the formatted code
```

## DSSTAR+ Mode Auto-Detection (Extension) [LOCKED: auto-detect with human override]
The system guesses a mode BEFORE the pipeline commits to it, using keyword heuristics
(below). The guess is NOT final — it's shown to the human at **CP1** (same checkpoint
where they already review the first plan step), with a control to flip it before
Coder_init runs. This avoids both silent misclassification and adding a separate
checkpoint just for mode selection.

**Base mode** (Finalyzer runs):
- Query is specific and factoid: "What is the total revenue for Q3 2024?"
- Indicators: "what is", "how many", "give me the value", "show me the number"
- Result fits in a single printed answer or small table

**DSSTAR+ mode** (SubquestionGenerator + Writer run instead):
- Query is open-ended or exploratory: "Analyse customer churn trends over the last year"
- Indicators: "analyse", "investigate", "explain", "what are the trends", "deep dive", "report"
- OR: chart files exist in OUTPUT_DIR (implies multi-faceted visual output)

The guess and any override travel on `CP1Payload.detected_mode` / `CP1Payload.mode_override`
— see `specs/agents/planner.md` for the full payload definition.

## Must NOT Do
- Generate HTML reports (that is Writer's job)
- Change the analysis logic (only format the output)
- Add try/except blocks (paper rule)
- Generate code that re-queries data if the answer is already in {result}

## Extension: CP3 Checkpoint
After Finalyzer executes the final code:
```python
class CP3Payload(BaseModel):
    mode: Literal["base", "plus"]
    question: str
    final_result: str               # base: printed answer; plus: HTML report preview
    available_actions: list[str]    # ["save", "export_pdf", "share", "discard"]
```

## Test Scenarios

### Unit (mocked LLM)
- Factoid query → mode: "base", Finalyzer called
- Exploratory query → mode: "plus", SubquestionGenerator called instead
- Finalyzer output is a complete Python script, not a snippet
- Generated script does not contain try/except
- Guidelines are present in rendered prompt

### Integration (real LLM + Docker sandbox)
- Finalyzer correctly reformats answer to match guidelines
- Final executed code prints a clean, human-readable answer
- If result already contains the answer, code is minimal (just a print statement)
