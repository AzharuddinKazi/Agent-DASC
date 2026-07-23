# Agent Spec: Coder

## Role (paper-faithful)
Translates a plan step into executable Python code. Called twice with different prompts:
- `coder_init` — implements the first step from scratch
- `coder_next` — extends the existing `base_code` to implement the next step

Code is CUMULATIVE — each call produces a single growing script that contains all previous steps plus the new one. Not isolated snippets.

## Position in Graph
```
[CP1 approved] → step_1
    → [Coder_init] → code_v1
    → [Debugger] → fixed_code_v1
    → Docker execution → result_1
    → [Verifier]
    ...
[Router: Add Step] → step_N
    → [Coder_next] (base_code = code_vN-1) → code_vN
    → [Debugger] → fixed_code_vN
    → Docker execution → result_N
    → [Verifier]

[Router: Step K] (truncate)
    → [Coder_next] (base_code = code_vK-1, regenerate step K)
```

## Paper Prompts (verbatim)

### coder_init
```
# Given data:
{summaries}
# Plan
{plan}
# Your task
Implement the plan with the given data.
Your response should be a single markdown Python code (wrapped in ```python ... ```).
There should be no additional headings or text in your response.
```

### coder_next
```
You are an expert data analyst.
Your task is to implement the next plan with the given data.
# Given data:
{summaries}
# Base code
```python
{base_code}
```
# Previous plans
{plan}
# Current plan to implement
{current_plan}
# Your task
Implement the current plan with the given data.
The implementation should be done based on the base code.
The base code is an implementation of the previous plans.
Your response should be a single markdown Python code (wrapped in ```python ... ```).
There should be no additional headings or text in your response.
```

## Template Variables

### coder_init
| Variable | Value |
|---|---|
| `{filenames}` | Comma-separated list of source identifiers |
| `{filenames_and_summaries}` | Per-file: `{filename #1}\n{summary #1}\n...\n{filename #N}\n{summary #N}` (+ GraphRAG context appended as extension) |
| `{plan}` | step_1 text from Planner_init |

### coder_next
| Variable | Value |
|---|---|
| `{filenames}` | Comma-separated list of source identifiers |
| `{filenames_and_summaries}` | Per-file pairs (same as init, + GraphRAG context appended as extension) |
| `{base_code}` | Full cumulative code from previous successful execution |
| `{plan}` | All steps so far: "1. {Step 1}\n...\nk. {Step k}" |
| `{current_plan}` | The single new step to implement (`{Step k+1}` text) |

## Outputs
```python
class CoderOutput(BaseModel):
    code: str           # complete cumulative Python script (all steps, not just new one)
    step_number: int    # which step was just added
```

## Cumulative Code Model
Each `coder_next` call produces a NEW complete script that includes all previous logic PLUS the new step. The script is self-contained and executable end-to-end. This means:
- Variables defined in step 1 are available in step 2's code
- DataFrames computed in step 2 are available in step 3
- No import needed between steps — one contiguous script

## Sandbox Constraints (enforced by sandbox, not LLM)
- MySQL connection: `os.environ["MYSQL_URL"]` via SQLAlchemy
- File paths: `os.environ["DATA_DIR"]` as base
- Output: `os.environ["OUTPUT_DIR"]` for charts and saved files
- Approved libraries: `pandas, numpy, matplotlib, plotly, sqlalchemy, pymysql, scikit-learn, scipy, openpyxl, xlrd`
- Forbidden: `os.system`, `subprocess`, `exec`, `eval`, `input()`, runtime `pip install`
- Charts: save to `OUTPUT_DIR` with `plt.savefig()` — NEVER `plt.show()`
- No external network calls except pre-configured MySQL host

## Audit Logging
Every `CoderOutput.code` is stored in `agent_steps.generated_code`. Handled by the graph executor — Coder does not control this.

## Must NOT Do
- Generate isolated snippets (must be full cumulative script)
- Hardcode credentials
- Call `plt.show()`
- Use forbidden libraries or shell execution
- Generate code that spans more than one plan step
- Generate SQL that modifies data — `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`/`TRUNCATE`
  [LOCKED]: same rule as Analyzer. Defense-in-depth alongside the catalog's enforced
  read-only DB user (`specs/features/catalog.md`) — the sandbox network/library
  restrictions don't otherwise stop a write statement from reaching MySQL.

## Test Scenarios

### Unit (mocked LLM)
- `coder_init` output does not contain hardcoded credentials
- `coder_next` output contains all code from `base_code` plus new logic
- Output does not call `plt.show()`
- Output does not use `subprocess` or `os.system`
- Output uses `os.environ["MYSQL_URL"]` for DB connections

### Integration (real LLM + Docker sandbox)
- coder_init successfully fetches data from test MySQL fixture
- coder_next correctly extends base_code — variables from step 1 accessible in step 2
- Chart saved to OUTPUT_DIR after plot step
- Cumulative script is executable end-to-end after N steps
