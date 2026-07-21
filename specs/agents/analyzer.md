# Agent Spec: Analyzer

## Role (paper-faithful)
Generates and executes Python code that inspects data sources and produces printed summaries. The printed stdout becomes the `summaries` context passed to all subsequent agents. Purely data-aware — does not interpret, plan, or analyse.

## Position in Graph
```
data_source_ids (from catalog)
    → [Analyzer]  generates Python → executes in Docker sandbox
    → printed stdout = data_summary
    → [Planner_init]
```

## Paper Prompt (verbatim — file sources)
```
You are an expert data analyst.
Generate a Python code that loads and describes the content of {filename}.
# Requirement
The file can be both unstructured or structured data.
If there are too many structured data, print out just few examples.
Print out essential informations. For example, print out all the column names.
The Python code should print out the content of {filename}.
The code should be a single-file Python program that is self-contained and can be
executed as-is.
Your response should only contain a single code block.
Important: You should not include dummy contents since we will debug if error occurs.
Do not use try: and except: to prevent error. I will debug it later.
```

## Extension Prompt (MySQL sources — not in paper)
```
You are an expert data analyst.
Generate a Python code that connects to a MySQL database and describes its schema.
Use SQLAlchemy with the connection string from os.environ["MYSQL_URL"].
Print out: all table names, column names and types for each table, row count estimates,
and 3 sample rows per table.
...
```
See `specs/prompts.yaml` → `analyzer_mysql` for full text.

## Template Variables
| Variable | Value |
|---|---|
| `{filename}` | File path from catalog (local filesystem) OR `"MySQL database"` (MySQL sources) |

## How It Works (paper mechanism)

1. For each data source in `data_source_ids`, the Analyzer generates a Python script via LLM call
2. Each script is executed in the Docker sandbox
3. The printed stdout from each execution is collected
4. All outputs are concatenated into a single `summaries` string
5. `summaries` is passed unchanged to all downstream agents

## Inputs
| Field | Type | Description |
|---|---|---|
| `data_source_ids` | `list[UUID]` | Sources to analyse. If empty, use all active catalog entries. |
| `catalog_entries` | `list[CatalogTable]` | Pre-fetched metadata (filenames, connection types) |

## Outputs
```python
class AnalyzerOutput(BaseModel):
    summaries: list[str]    # printed stdout per source, aligned by index with filenames
    filenames: list[str]    # list of source identifiers (file paths or "MySQL:{db_name}")
```
`summaries[i]` corresponds to `filenames[i]`. Kept as a list, not concatenated, because
downstream prompts render `{filenames_and_summaries}` as per-file pairs (paper-faithful —
see `specs/prompts.yaml`).

## Behaviour Rules [LOCKED]
- One LLM call + one Docker execution per data source
- Scripts MUST print to stdout — return values are ignored
- If a source execution fails: summarize the error (Debugger Prompt 1) → repair the script
  (Debugger Prompt 2) → re-execute once. This is paper-faithful (Appendix L.7, Prompt 2 is
  defined specifically for Analyzer script repair) — do not skip straight to "unavailable"
  without attempting one repair.
- If source is still unreachable after the single Debugger repair attempt, skip it and note
  in its summary: "Source {name}: unavailable"
- MUST NOT generate analysis logic — only description/inspection code
- Generated scripts MUST NOT modify data (no INSERT/UPDATE/DELETE/DROP)
- MySQL scripts MUST use `os.environ["MYSQL_URL"]` — never hardcode credentials

## Must NOT Do
- Interpret what the data means
- Suggest analysis approaches
- Generate code that modifies data
- Hardcode file paths or connection strings
- Use try/except in generated code (paper rule — Debugger handles errors)

## Test Scenarios

### Unit (mocked LLM + mocked Docker execution)
- Given 1 file source → 1 LLM call, 1 execution, stdout captured as summaries
- Given 1 MySQL source → uses `analyzer_mysql` prompt, not file prompt
- Failed execution → Debugger called on analysis script before skipping
- Empty data_source_ids → analyses all active catalog entries

### Integration (real LLM + Docker sandbox + test fixtures)
- Analysis script for CSV file correctly prints column names and sample rows
- Analysis script for MySQL correctly prints table names, columns, and row counts via SQLAlchemy
- Summaries string is non-empty and contains table/column names from test fixture
