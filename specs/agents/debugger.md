# Agent Spec: Debugger

## Role (paper-faithful)
Called when code execution fails. The paper defines THREE distinct prompts for the Debugger:
1. **Traceback summarizer** — cleans up raw error output before repair
2. **Analyzer repair** — fixes Analyzer-generated data inspection scripts
3. **Coder repair** — fixes Coder-generated solution scripts (includes summaries context)

No try/except in generated code — the Debugger handles all errors instead (paper rule).

## Position in Graph
```
Analyzer script → Docker error
    → [Debugger: summarize] → clean_bug
    → [Debugger: analyzer repair] → fixed_analyzer_script
    → Docker re-execution → summaries

Coder script → Docker error
    → [Debugger: summarize] → clean_bug
    → [Debugger: coder repair] → fixed_code
    → Docker re-execution → result
    → [Verifier]
```

## Paper Prompts (verbatim — Appendix L.7)

### Prompt 1: Traceback Summarizer
Called first on the raw stderr to clean it up before passing to repair prompts.
```
# Error report
{bug}
# Your task
- Remove all unnecessary parts of the above error report.
- We are now running {filename}.py. Do not remove where the error occurred.
```

### Prompt 2: Analyzer Script Repair
Used when an Analyzer-generated data inspection script fails.
```
# Code with an error:
```python
{code}
```
# Error:
{bug}
# Your task
- Please revise the code to fix the error.
- Provide the improved, self-contained Python script again.
- There should be no additional headings or text in your response.
- Do not include dummy contents since we will debug if error occurs.
- All files/documents are in `data/` directory.
```

### Prompt 3: Coder Solution Script Repair
Used when a Coder-generated analysis script fails. Includes data summaries for context.
```
# Given data: {filenames}
{filenames_and_summaries}
# Code with an error:
```python
{code}
```
# Error:
{bug}
# Your task
- Please revise the code to fix the error.
- Provide the improved, self-contained Python script again.
- Note that you only have {filenames} available.
- There should be no additional headings or text in your response.
- Do not include dummy contents since we will debug if error occurs.
- All files/documents are in `data/` directory.
```

## Template Variables

### Prompt 1 (summarizer)
| Variable | Value |
|---|---|
| `{bug}` | Raw stderr / traceback from Docker execution |
| `{filename}` | Name of the script that failed (e.g. `analyzer_source1.py`) |

### Prompt 2 (analyzer repair)
| Variable | Value |
|---|---|
| `{code}` | The failing Analyzer Python script |
| `{bug}` | Summarized error output (from Prompt 1) |

### Prompt 3 (coder repair)
| Variable | Value |
|---|---|
| `{filenames}` | Comma-separated list of available source identifiers |
| `{filenames_and_summaries}` | Per-file: `{filename #1}\n{summary #1}\n...` |
| `{code}` | The failing cumulative Coder Python script |
| `{bug}` | Summarized error output (from Prompt 1) |

## Execution Flow
```
Raw stderr
    → Prompt 1 (summarize) → clean_bug
    → Prompt 2 or 3 (repair, depending on which phase) → fixed_code
    → Docker re-execution
```
The Debugger is called at most ONCE per execution failure. No Debugger retry loop — if the fixed code still fails, Verifier sees it as "No" and Router handles it.

## Outputs
```python
class DebuggerOutput(BaseModel):
    code: str               # fixed, self-contained Python script
    was_modified: bool      # True if any changes were made
    clean_bug: str          # summarized error (output of Prompt 1)
```

## Behaviour Rules
- Returns the COMPLETE fixed script — not a diff or patch
- MUST NOT change the logical intent of the code — only fix the error
- MUST NOT add try/except blocks (paper rule)
- MUST NOT introduce new analysis steps
- If unfixable, return original code with `was_modified: false` — Verifier catches it
- Prompt 2 used ONLY for Analyzer scripts; Prompt 3 used for ALL Coder scripts
- "All files/documents are in `data/` directory" — maps to `os.environ["DATA_DIR"]` in our extension

## Extension: DATA_DIR mapping
The paper uses a `data/` directory convention. In our deployment:
- Cloud: `DATA_DIR` = mounted GCS path
- On-prem: `DATA_DIR` = local Docker volume mount

The Debugger prompt says `data/` directory; the sandbox injects `DATA_DIR` env var mapped to the actual path.

## Must NOT Do
- Add try/except blocks
- Change what the code computes
- Run the code itself
- Use Prompt 3 for Analyzer scripts (wrong context)
- Use Prompt 2 for Coder scripts (missing summaries context)

## Test Scenarios

### Unit (mocked LLM)
- Analyzer script failure → Prompt 2 used (no summaries in prompt)
- Coder script failure → Prompt 3 used (summaries in prompt)
- Raw stderr is always summarized via Prompt 1 first
- Fixed code is always a complete script, not a snippet
- Output does not contain try/except blocks
- `was_modified: false` when error is unfixable (e.g. missing file)

### Integration (real LLM + Docker sandbox)
- Debugger fixes a missing `import pandas as pd` → re-execution succeeds
- Debugger fixes wrong column name based on summaries context (Prompt 3)
- Debugger correctly passes through unfixable code → Verifier returns "No" → Router handles
