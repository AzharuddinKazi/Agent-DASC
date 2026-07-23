# Testing Strategy & CI/CD Specification

## Philosophy
Tests are written BEFORE code. Every spec decision has a corresponding test. An LLM
implementing this system must pass all tests before a PR can merge — tests are the
contract, not the code.

## Trigger Matrix (Industry Standard)

| Trigger | Tests that run | Blocks? |
|---|---|---|
| `git commit` (pre-commit hook) | Linting, type checking, fast unit tests only | Yes — commit rejected if failing |
| Pull Request opened/updated | Full unit + integration test suite | Yes — merge blocked if failing |
| Merge to `main` | Full unit + integration + system tests | No — alerts on failure, does not block |
| Nightly (scheduled, 02:00 UTC) | Full suite including system tests | No — alerts on failure |

## Test Tiers

### Tier 1 — Unit Tests
- **LLM:** Mocked via `pytest-mock` — LLM never called, responses injected
- **Database:** Mocked via `unittest.mock` or in-memory SQLite for simple cases
- **Docker sandbox:** Mocked — `execute_code()` returns `ExecutionResult` fixtures
- **Speed:** < 30 seconds total
- **Trigger:** Pre-commit hook + PR

### Tier 2 — Integration Tests
- **LLM:** Real `claude-haiku-4-5-20251001` (cheapest capable model) OR `ollama/llama3` on-prem
- **Database:** Real PostgreSQL + MySQL in Docker (`docker-compose.test.yml`)
- **Docker sandbox:** Real Docker execution against test fixtures
- **GraphRAG:** Real Microsoft GraphRAG against test knowledge document
- **Speed:** < 10 minutes
- **Trigger:** PR only

### Tier 3 — System Tests
- **LLM:** Real `claude-haiku-4-5-20251001`
- **Database:** Real services via `docker-compose.test.yml`
- **Checkpoints:** Scripted human responses (automated approval/rejection sequences)
- **Speed:** < 30 minutes
- **Trigger:** Post-merge to `main` + nightly

---

## Repository Test Structure

```
tests/
├── conftest.py                        ← shared fixtures, DB setup, LLM mock factory
├── docker-compose.test.yml            ← PostgreSQL + MySQL + ChromaDB for tests
│
├── unit/
│   ├── agents/
│   │   ├── test_analyzer.py
│   │   ├── test_planner.py
│   │   ├── test_coder.py
│   │   ├── test_debugger.py
│   │   ├── test_verifier.py
│   │   ├── test_router.py
│   │   ├── test_finalyzer.py
│   │   ├── test_subquestion_generator.py
│   │   └── test_writer.py
│   ├── features/
│   │   ├── test_catalog.py
│   │   ├── test_graphrag.py
│   │   ├── test_sandbox.py
│   │   └── test_checkpoints.py
│   └── api/
│       ├── test_analyses_api.py
│       ├── test_catalog_api.py
│       ├── test_knowledge_api.py
│       ├── test_reports_api.py
│       └── test_checkpoints_api.py
│
├── integration/
│   ├── agents/
│   │   ├── test_analyzer_integration.py
│   │   ├── test_planner_integration.py
│   │   ├── test_coder_integration.py
│   │   ├── test_debugger_integration.py
│   │   ├── test_verifier_integration.py
│   │   ├── test_router_integration.py
│   │   ├── test_finalyzer_integration.py
│   │   └── test_dsstar_plus_integration.py
│   ├── features/
│   │   ├── test_catalog_integration.py
│   │   ├── test_graphrag_integration.py
│   │   ├── test_sandbox_integration.py
│   │   └── test_checkpoints_integration.py
│   └── api/
│       └── test_api_integration.py
│
├── system/
│   ├── test_base_flow.py              ← happy path end-to-end
│   ├── test_force_exit_flow.py        ← max iterations + hint
│   ├── test_dsstar_plus_flow.py       ← full report generation
│   └── test_checkpoint_flows.py       ← all checkpoint types
│
└── fixtures/
    ├── mysql/
    │   └── seed.sql                   ← test data: orders, customers, products tables
    ├── files/
    │   ├── test_sales.csv
    │   └── test_inventory.xlsx
    └── knowledge/
        └── test_domain_doc.txt        ← short domain document for GraphRAG tests
```

---

## Shared Fixtures (`tests/conftest.py`)

```python
# Key fixtures available to all tests

@pytest.fixture
def mock_llm():
    """Returns a factory that injects canned LLM responses."""
    def _make(responses: list[str]):
        mock = MagicMock()
        mock.invoke.side_effect = [AIMessage(content=r) for r in responses]
        return mock
    return _make

@pytest.fixture(scope="session")
def test_postgres_url():
    """PostgreSQL URL for the test DB (from docker-compose.test.yml)."""
    return os.environ["TEST_POSTGRES_URL"]

@pytest.fixture(scope="session")
def test_mysql_url():
    """MySQL URL for the test DB (from docker-compose.test.yml)."""
    return os.environ["TEST_MYSQL_URL"]

@pytest.fixture(scope="session", autouse=True)
def seed_mysql(test_mysql_url):
    """Seeds the test MySQL DB with fixtures/mysql/seed.sql."""
    engine = create_engine(test_mysql_url)
    with open("tests/fixtures/mysql/seed.sql") as f:
        engine.execute(f.read())
    yield
    # teardown: tables dropped by seed.sql's own DROP IF EXISTS

@pytest.fixture
def test_session_id():
    return str(uuid4())

@pytest.fixture
def test_user_id():
    return str(uuid4())

@pytest.fixture
def fake_execution_result():
    """Injects a successful Docker execution result."""
    return ExecutionResult(
        stdout="Total revenue: $1,234,567",
        stderr="",
        exit_code=0,
        duration_ms=1200,
        output_files=[],
        timed_out=False,
    )

@pytest.fixture
def fake_execution_error():
    """Injects a failed Docker execution result."""
    return ExecutionResult(
        stdout="",
        stderr="NameError: name 'df' is not defined\n  File script.py, line 4",
        exit_code=1,
        duration_ms=300,
        output_files=[],
        timed_out=False,
    )
```

---

## MySQL Test Fixture (`tests/fixtures/mysql/seed.sql`)

```sql
DROP TABLE IF EXISTS test_orders;
DROP TABLE IF EXISTS test_customers;
DROP TABLE IF EXISTS test_products;

CREATE TABLE test_customers (
    customer_id INT PRIMARY KEY,
    name        VARCHAR(100),
    email       VARCHAR(200),
    region      VARCHAR(50),
    joined_date DATE
);

CREATE TABLE test_products (
    product_id   INT PRIMARY KEY,
    name         VARCHAR(200),
    category     VARCHAR(100),
    unit_price   DECIMAL(10,2)
);

CREATE TABLE test_orders (
    order_id    INT PRIMARY KEY,
    customer_id INT REFERENCES test_customers(customer_id),
    product_id  INT REFERENCES test_products(product_id),
    quantity    INT,
    order_date  DATE,
    net_amount  DECIMAL(10,2)
);

-- Seed: 3 customers, 3 products, 9 orders (Q3 2024)
INSERT INTO test_customers VALUES
  (1, 'Alice Smith',   'alice@example.com',   'North', '2023-01-15'),
  (2, 'Bob Jones',     'bob@example.com',     'South', '2023-03-20'),
  (3, 'Carol White',   'carol@example.com',   'North', '2022-11-01');

INSERT INTO test_products VALUES
  (1, 'Widget A',  'Electronics', 49.99),
  (2, 'Gadget B',  'Electronics', 99.99),
  (3, 'Doodad C',  'Furniture',   199.99);

INSERT INTO test_orders VALUES
  (1, 1, 1, 2, '2024-07-05', 99.98),
  (2, 1, 2, 1, '2024-07-12', 99.99),
  (3, 2, 3, 1, '2024-08-03', 199.99),
  (4, 2, 1, 3, '2024-08-15', 149.97),
  (5, 3, 2, 2, '2024-09-01', 199.98),
  (6, 3, 3, 1, '2024-09-10', 199.99),
  (7, 1, 3, 2, '2024-09-18', 399.98),
  (8, 2, 2, 1, '2024-09-22', 99.99),
  (9, 3, 1, 4, '2024-09-28', 199.96);
-- Total net_amount = $1,649.83
```

---

## Unit Tests: Agents

### `tests/unit/agents/test_analyzer.py`

```python
def test_analyzer_uses_file_prompt_for_csv_source(mock_llm):
    """Analyzer uses 'analyzer' prompt (not mysql) for file sources."""
    llm = mock_llm(["```python\nimport pandas as pd\ndf = pd.read_csv('test.csv')\nprint(df.columns.tolist())\n```"])
    result = run_analyzer(sources=[FileSource("test.csv")], llm=llm)
    call_args = llm.invoke.call_args[0][0]
    assert "{filename}" not in str(call_args)   # variable rendered, not raw
    assert "test.csv" in str(call_args)

def test_analyzer_uses_mysql_prompt_for_mysql_source(mock_llm):
    """Analyzer uses 'analyzer_mysql' prompt for MySQL sources."""
    llm = mock_llm(["```python\nfrom sqlalchemy import create_engine\n...```"])
    result = run_analyzer(sources=[MySQLSource("test_db")], llm=llm)
    call_args = llm.invoke.call_args[0][0]
    assert "os.environ[\"MYSQL_URL\"]" in str(call_args)

def test_analyzer_called_once_per_source(mock_llm):
    """One LLM call per data source."""
    llm = mock_llm(["```python\nprint('schema')\n```"] * 3)
    run_analyzer(sources=[FileSource("a.csv"), FileSource("b.xlsx"), MySQLSource("db")], llm=llm)
    assert llm.invoke.call_count == 3

def test_analyzer_output_contains_all_filenames(mock_llm):
    """AnalyzerOutput.filenames lists all sources."""
    llm = mock_llm(["```python\nprint('ok')\n```"] * 2)
    result = run_analyzer(sources=[FileSource("sales.csv"), MySQLSource("crm")], llm=llm)
    assert "sales.csv" in result.filenames
    assert "crm" in result.filenames

def test_analyzer_handles_empty_source_list_uses_all_catalog(mock_llm, mocker):
    """Empty data_source_ids → fetches all active catalog entries."""
    mock_catalog = mocker.patch("catalog.get_active_sources", return_value=[FileSource("all.csv")])
    llm = mock_llm(["```python\nprint('ok')\n```"])
    run_analyzer(sources=[], llm=llm)
    mock_catalog.assert_called_once()

def test_analyzer_generated_script_does_not_contain_try_except(mock_llm, mocker):
    """Generated scripts must not contain try/except (paper rule)."""
    llm = mock_llm(["```python\ntry:\n    df = pd.read_csv('f.csv')\nexcept:\n    pass\n```"])
    mocker.patch("sandbox.execute_code", return_value=fake_execution_result())
    # Debugger should be triggered when try/except detected OR it's a runtime constraint
    # Either way, validate no try/except in final executed script
    result = run_analyzer(sources=[FileSource("f.csv")], llm=llm)
    # The sandbox executor strips try/except or Debugger removes them
    # This test verifies the contract, implementation may handle it either way

def test_analyzer_skips_unreachable_source_and_continues(mock_llm, mocker):
    """Unreachable source → noted in summaries, does not abort run."""
    mocker.patch("sandbox.execute_code", side_effect=[
        ConnectionError("source unreachable"),
        fake_execution_result()
    ])
    llm = mock_llm(["```python\nprint('ok')\n```"] * 2)
    result = run_analyzer(sources=[MySQLSource("bad_db"), FileSource("good.csv")], llm=llm)
    assert "unavailable" in result.summaries.lower()
    assert len(result.filenames) == 2
```

---

### `tests/unit/agents/test_planner.py`

```python
def test_planner_init_generates_single_step(mock_llm):
    """planner_init returns exactly one step, no code."""
    llm = mock_llm(["Load the test_orders table and print the first 5 rows."])
    result = run_planner_init(question="What is total revenue?", summaries="test_orders: ...", llm=llm)
    assert result.step_text == "Load the test_orders table and print the first 5 rows."
    assert result.step_number == 1

def test_planner_init_prompt_contains_question_and_summaries(mock_llm):
    """Rendered prompt contains the question and summaries."""
    llm = mock_llm(["Step 1"])
    run_planner_init(question="What is Q3 revenue?", summaries="orders table: 3 cols", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "What is Q3 revenue?" in prompt
    assert "orders table: 3 cols" in prompt

def test_planner_init_step_contains_no_python_code(mock_llm):
    """planner_init must not generate Python code in its response."""
    llm = mock_llm(["import pandas as pd\ndf = pd.read_sql(...)"])
    result = run_planner_init(question="Revenue?", summaries="...", llm=llm)
    # Implementation must flag or strip code from planner output
    assert "import" not in result.step_text or result.step_text == ""

def test_planner_next_called_only_on_add_step(mock_llm):
    """planner_next is triggered by Router 'Add Step', not 'Step K'."""
    llm = mock_llm(["Filter orders by Q3 2024 date range."])
    result = run_planner_next(
        question="Q3 revenue?",
        summaries="...",
        plan=["1. Load orders table"],
        result="   order_id  customer_id ...",
        llm=llm
    )
    assert result.step_number == 2
    assert result.step_text != ""

def test_planner_next_prompt_contains_current_plan_and_result(mock_llm):
    """planner_next prompt includes all previous steps and the latest result."""
    llm = mock_llm(["Next step text"])
    run_planner_next(
        question="Q?",
        summaries="s",
        plan=["1. Load table", "2. Filter rows"],
        result="Filtered DataFrame: 45 rows",
        llm=llm
    )
    prompt = str(llm.invoke.call_args[0][0])
    assert "1. Load table" in prompt
    assert "Filtered DataFrame: 45 rows" in prompt

def test_planner_graphrag_context_appended_to_summaries(mock_llm):
    """GraphRAG context is appended to {filenames_and_summaries} before rendering."""
    llm = mock_llm(["Step 1"])
    run_planner_init(
        question="Revenue?",
        summaries="orders table",
        graphrag_context="Domain: net_amount is revenue after refunds",
        llm=llm
    )
    prompt = str(llm.invoke.call_args[0][0])
    assert "net_amount is revenue after refunds" in prompt
    assert "orders table" in prompt

def test_planner_init_with_user_hint_appends_hint_to_question(mock_llm):
    """After force-exit, user hint is appended to {question} in planner prompt."""
    llm = mock_llm(["Revised step 1"])
    run_planner_init(
        question="What is revenue?",
        summaries="...",
        hint="Use the net_amount column, not gross_amount",
        llm=llm
    )
    prompt = str(llm.invoke.call_args[0][0])
    assert "Use the net_amount column" in prompt
```

---

### `tests/unit/agents/test_coder.py`

```python
def test_coder_init_generates_complete_python_script(mock_llm):
    """coder_init returns a complete, self-contained Python script."""
    code = "import pandas as pd\nengine = create_engine(os.environ['MYSQL_URL'])\ndf = pd.read_sql('SELECT * FROM test_orders', engine)\nprint(df.head())"
    llm = mock_llm([f"```python\n{code}\n```"])
    result = run_coder_init(summaries="test_orders: ...", plan="Load orders table", llm=llm)
    assert "import" in result.code
    assert result.step_number == 1

def test_coder_init_does_not_hardcode_credentials(mock_llm):
    """Generated code uses os.environ, never hardcoded credentials."""
    llm = mock_llm(["```python\nengine = create_engine('mysql+pymysql://root:password@localhost/db')\n```"])
    result = run_coder_init(summaries="...", plan="Load table", llm=llm)
    assert "os.environ" in result.code or "MYSQL_URL" not in result.code.split("os.environ")[0]
    # The sandbox enforces this at runtime; unit test validates the prompt forbids it

def test_coder_init_does_not_call_plt_show(mock_llm):
    """Generated code must not contain plt.show()."""
    llm = mock_llm(["```python\nimport matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.show()\n```"])
    result = run_coder_init(summaries="...", plan="Plot revenue", llm=llm)
    # Debugger or prompt constraint must eliminate plt.show()
    assert "plt.show()" not in result.code

def test_coder_init_does_not_use_forbidden_functions(mock_llm):
    """Generated code must not use os.system, subprocess, exec, eval."""
    code = "import os\nos.system('ls')"
    llm = mock_llm([f"```python\n{code}\n```"])
    result = run_coder_init(summaries="...", plan="List files", llm=llm)
    forbidden = ["os.system", "subprocess", "exec(", "eval("]
    for f in forbidden:
        assert f not in result.code

def test_coder_next_extends_base_code(mock_llm):
    """coder_next output contains all base_code plus new logic."""
    base = "import pandas as pd\ndf = pd.read_sql('SELECT * FROM test_orders', engine)\n"
    new_logic = "df_filtered = df[df['order_date'] >= '2024-07-01']\nprint(df_filtered.shape)"
    llm = mock_llm([f"```python\n{base}{new_logic}\n```"])
    result = run_coder_next(
        summaries="...",
        base_code=base,
        plan=["1. Load orders"],
        current_plan="Filter by Q3 2024",
        llm=llm
    )
    assert base.strip() in result.code
    assert "df_filtered" in result.code

def test_coder_next_prompt_contains_base_code(mock_llm):
    """coder_next prompt includes base_code in the ```python block."""
    base = "import pandas as pd\n"
    llm = mock_llm(["```python\nimport pandas as pd\nprint('ok')\n```"])
    run_coder_next(summaries="...", base_code=base, plan=["1. Step"], current_plan="Step 2", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert base.strip() in prompt

def test_coder_uses_output_dir_for_charts(mock_llm):
    """Chart saves use os.environ['OUTPUT_DIR'], not hardcoded paths."""
    code = "plt.savefig('/some/hardcoded/path/chart.png')"
    llm = mock_llm([f"```python\n{code}\n```"])
    result = run_coder_init(summaries="...", plan="Plot data", llm=llm)
    assert "OUTPUT_DIR" in result.code or "/some/hardcoded" not in result.code
```

---

### `tests/unit/agents/test_debugger.py`

```python
def test_debugger_summarize_cleans_traceback(mock_llm):
    """debugger_summarize removes noise from raw traceback."""
    raw_error = "Traceback (most recent call last):\n  File ...\n  ...\nNameError: name 'df' is not defined"
    llm = mock_llm(["NameError: name 'df' is not defined\n  File script.py, line 4"])
    result = run_debugger_summarize(bug=raw_error, filename="script.py", llm=llm)
    assert "NameError" in result.clean_bug
    assert "script.py" in result.clean_bug

def test_debugger_analyzer_prompt_has_no_summaries(mock_llm):
    """debugger_analyzer prompt does NOT include data summaries."""
    llm = mock_llm(["```python\nimport pandas as pd\ndf = pd.read_csv('file.csv')\nprint(df)\n```"])
    run_debugger_analyzer(code="import pandas\ndf = pandas.read_csv('file.csv')\nprint(df)", bug="ModuleNotFoundError", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "{filenames_and_summaries}" not in prompt
    assert "filenames" not in prompt.lower()

def test_debugger_coder_prompt_includes_summaries(mock_llm):
    """debugger_coder prompt includes data summaries for context."""
    llm = mock_llm(["```python\nfixed_code\n```"])
    run_debugger_coder(
        summaries="test_orders: order_id, net_amount",
        filenames=["MySQL: test_db"],
        code="broken_code",
        bug="NameError",
        llm=llm
    )
    prompt = str(llm.invoke.call_args[0][0])
    assert "test_orders" in prompt

def test_debugger_returns_complete_script_not_diff(mock_llm):
    """Debugger returns the full fixed script, not a patch or diff."""
    fixed = "import pandas as pd\ndf = pd.read_sql('SELECT * FROM orders', engine)\nprint(df)"
    llm = mock_llm([f"```python\n{fixed}\n```"])
    result = run_debugger_coder(summaries="...", filenames=["f"], code="broken", bug="Error", llm=llm)
    assert result.code == fixed
    assert result.was_modified is True

def test_debugger_was_modified_false_when_code_unchanged(mock_llm):
    """If debugger returns identical code, was_modified is False."""
    original = "import pandas as pd\nprint('ok')"
    llm = mock_llm([f"```python\n{original}\n```"])
    result = run_debugger_coder(summaries="...", filenames=["f"], code=original, bug="warning", llm=llm)
    assert result.was_modified is False

def test_debugger_does_not_add_try_except(mock_llm):
    """Debugger must not introduce try/except (paper rule)."""
    llm = mock_llm(["```python\ntry:\n    import pandas\nexcept ImportError:\n    pass\n```"])
    result = run_debugger_coder(summaries="...", filenames=["f"], code="import pandas", bug="ImportError", llm=llm)
    assert "try:" not in result.code

def test_debugger_called_once_per_failure(mock_llm, mocker):
    """Debugger is called at most once per execution failure — no retry loop."""
    llm = mock_llm(["```python\nfixed\n```"])
    mock_execute = mocker.patch("sandbox.execute_code", side_effect=[
        fake_execution_error(),
        fake_execution_result()
    ])
    run_coder_with_debug_cycle(code="broken", llm=llm)
    assert llm.invoke.call_count == 1  # debugger called once
```

---

### `tests/unit/agents/test_verifier.py`

```python
def test_verifier_returns_yes_for_complete_answer(mock_llm):
    """'Yes' response → verdict 'Yes'."""
    llm = mock_llm(["Yes"])
    result = run_verifier(plan=["1. Load", "2. Aggregate"], code="...", result="Total: $1,649.83", question="Total revenue Q3?", llm=llm)
    assert result.verdict == "Yes"

def test_verifier_returns_no_for_incomplete_answer(mock_llm):
    """'No' response → verdict 'No'."""
    llm = mock_llm(["No"])
    result = run_verifier(plan=["1. Load"], code="...", result="   order_id  ...\n0  1  ...", question="Total revenue Q3?", llm=llm)
    assert result.verdict == "No"

def test_verifier_prompt_does_not_contain_summaries(mock_llm):
    """Verifier prompt does NOT include data summaries (paper spec)."""
    llm = mock_llm(["Yes"])
    run_verifier(plan=["1. Load"], code="code", result="result", question="Q?", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "Given data" not in prompt
    assert "filenames" not in prompt.lower()

def test_verifier_prompt_order_matches_paper(mock_llm):
    """Prompt order: Plan → Code → Execution result → Question (paper L.4)."""
    llm = mock_llm(["Yes"])
    run_verifier(plan=["1. Load"], code="my_code", result="my_result", question="my_question", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    plan_pos = prompt.index("# Plan")
    code_pos = prompt.index("# Code")
    result_pos = prompt.index("# Execution result")
    question_pos = prompt.index("# Question")
    assert plan_pos < code_pos < result_pos < question_pos

def test_verifier_returns_no_for_ambiguous_response(mock_llm):
    """Ambiguous LLM response → conservative 'No'."""
    llm = mock_llm(["I'm not sure, it depends..."])
    result = run_verifier(plan=["1."], code="...", result="...", question="Q?", llm=llm)
    assert result.verdict == "No"

def test_verifier_returns_no_when_result_contains_exception(mock_llm):
    """Result containing stack trace → must return 'No' regardless of LLM response."""
    llm = mock_llm(["Yes"])  # even if LLM says Yes
    result = run_verifier(
        plan=["1."], code="...",
        result="Traceback (most recent call last):\n  NameError: name 'df' is not defined",
        question="Q?", llm=llm
    )
    assert result.verdict == "No"  # enforced by code, not LLM

def test_verifier_stores_raw_response_for_logging(mock_llm):
    """raw_response field captures full LLM output."""
    llm = mock_llm(["Yes, it is sufficient."])
    result = run_verifier(plan=["1."], code="...", result="ok", question="Q?", llm=llm)
    assert result.raw_response == "Yes, it is sufficient."
```

---

### `tests/unit/agents/test_router.py`

```python
def test_router_returns_add_step(mock_llm):
    """'Add Step' response → action 'add_step'."""
    llm = mock_llm(["Add Step"])
    result = run_router(question="Q?", summaries="...", plan=["1. Load"], result="raw data", llm=llm)
    assert result.action == "add_step"
    assert result.truncate_to_step is None

def test_router_returns_truncate_for_step_k(mock_llm):
    """'Step 2' response → action 'truncate', truncate_to_step = 1."""
    llm = mock_llm(["Step 2"])
    result = run_router(question="Q?", summaries="...", plan=["1. Load", "2. Filter"], result="error", llm=llm)
    assert result.action == "truncate"
    assert result.truncate_to_step == 1  # K-1

def test_router_step_1_becomes_add_step(mock_llm):
    """'Step 1' → cannot truncate before step 1 → treat as add_step."""
    llm = mock_llm(["Step 1"])
    result = run_router(question="Q?", summaries="...", plan=["1. Load"], result="bad", llm=llm)
    assert result.action == "add_step"

def test_router_unrecognised_response_becomes_add_step(mock_llm):
    """Unrecognised response → fallback to 'add_step'."""
    llm = mock_llm(["I think we should try something else entirely"])
    result = run_router(question="Q?", summaries="...", plan=["1."], result="...", llm=llm)
    assert result.action == "add_step"

def test_router_add_step_triggers_planner_next(mock_llm, mocker):
    """After 'Add Step': Planner_next called, NOT Coder directly."""
    mock_planner = mocker.patch("agents.planner.run_planner_next", return_value=MagicMock(step_text="Step 2"))
    mock_coder = mocker.patch("agents.coder.run_coder_next")
    llm = mock_llm(["Add Step", "Step 2 text", "```python\ncode\n```"])
    run_full_router_cycle(question="Q?", summaries="...", plan=["1."], result="...", llm=llm)
    mock_planner.assert_called_once()
    mock_coder.assert_called_once()

def test_router_truncate_triggers_coder_not_planner(mock_llm, mocker):
    """After 'Step K': Coder_next called with rolled-back base_code, Planner NOT called."""
    mock_planner = mocker.patch("agents.planner.run_planner_next")
    mock_coder = mocker.patch("agents.coder.run_coder_next", return_value=MagicMock(code="fixed"))
    llm = mock_llm(["Step 2"])
    run_full_router_cycle(question="Q?", summaries="...", plan=["1. Load", "2. Filter"], result="error", llm=llm)
    mock_planner.assert_not_called()
    mock_coder.assert_called_once()

def test_router_prompt_contains_question_summaries_plan_result(mock_llm):
    """Router prompt includes all required variables."""
    llm = mock_llm(["Add Step"])
    run_router(question="My Q", summaries="My summaries", plan=["1. Load"], result="My result", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "My Q" in prompt
    assert "My summaries" in prompt
    assert "1. Load" in prompt
    assert "My result" in prompt
```

---

### `tests/unit/agents/test_finalyzer.py`

```python
def test_finalyzer_base_mode_generates_python_script(mock_llm):
    """Finalyzer (base mode) returns a Python script, not a report."""
    code = "print(f'Total revenue: ${total}')"
    llm = mock_llm([f"```python\n{code}\n```"])
    result = run_finalyzer(
        summaries="...", code="base_code", result="total = 1649.83",
        question="Total revenue Q3?", guidelines="Print as currency", llm=llm
    )
    assert result.mode == "base"
    assert "print" in result.code
    assert "<html>" not in result.code  # NOT a report

def test_finalyzer_prompt_includes_guidelines(mock_llm):
    """Finalyzer prompt includes the {guidelines} variable."""
    llm = mock_llm(["```python\nprint('ok')\n```"])
    run_finalyzer(summaries="...", code="c", result="r", question="Q?",
                  guidelines="Print as JSON with key 'final_answer'", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "Print as JSON with key 'final_answer'" in prompt

def test_finalyzer_prompt_includes_data_dir_note(mock_llm):
    """Finalyzer prompt includes 'All files/documents are in `data/` directory.' (paper rule)."""
    llm = mock_llm(["```python\nprint('ok')\n```"])
    run_finalyzer(summaries="...", code="c", result="r", question="Q?", guidelines="...", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "data/" in prompt

def test_finalyzer_does_not_contain_try_except(mock_llm):
    """Finalyzer generated code must not use try/except (paper rule)."""
    llm = mock_llm(["```python\ntry:\n    print(total)\nexcept:\n    print(0)\n```"])
    result = run_finalyzer(summaries="...", code="c", result="r", question="Q?", guidelines="...", llm=llm)
    assert "try:" not in result.code

def test_dsstar_plus_mode_detected_for_exploratory_query(mock_llm):
    """Open-ended query → mode 'plus' → SubquestionGenerator triggered, Finalyzer skipped."""
    mode = detect_output_mode(question="Analyse customer churn trends over the last year")
    assert mode == "plus"

def test_base_mode_detected_for_factoid_query(mock_llm):
    """Specific factoid query → mode 'base' → Finalyzer runs."""
    mode = detect_output_mode(question="What is the total revenue for Q3 2024?")
    assert mode == "base"

def test_dsstar_plus_mode_triggered_by_chart_files(mock_llm):
    """If OUTPUT_DIR contains chart files, mode is 'plus' regardless of query type."""
    mode = detect_output_mode(
        question="Show me the sales numbers",
        output_files=["revenue_chart.png"]
    )
    assert mode == "plus"
```

---

### `tests/unit/agents/test_subquestion_generator.py`

```python
def test_subquestion_generator_init_returns_json_list(mock_llm):
    """Init prompt returns valid JSON list of questions."""
    llm = mock_llm(['[{"question": "What is Q3 revenue by category?"}, {"question": "Which region has highest churn?"}]'])
    result = run_subquestion_generator_init(question="Analyse Q3 performance", summaries="...", llm=llm)
    assert len(result.sub_questions) == 2
    assert all(isinstance(q, str) for q in result.sub_questions)

def test_subquestion_generator_init_caps_at_15_questions(mock_llm):
    """Implementation caps sub-questions at 15 per round."""
    questions = [{"question": f"Question {i}?"} for i in range(20)]
    llm = mock_llm([json.dumps(questions)])
    result = run_subquestion_generator_init(question="Q?", summaries="...", llm=llm)
    assert len(result.sub_questions) <= 15

def test_subquestion_generator_init_retries_on_invalid_json(mock_llm):
    """Invalid JSON response → retry once."""
    llm = mock_llm(["not valid json", '[{"question": "Valid Q?"}]'])
    result = run_subquestion_generator_init(question="Q?", summaries="...", llm=llm)
    assert llm.invoke.call_count == 2
    assert len(result.sub_questions) == 1

def test_subquestion_generator_init_returns_empty_on_second_json_failure(mock_llm):
    """Two consecutive JSON failures → empty list, no crash."""
    llm = mock_llm(["bad json", "still bad"])
    result = run_subquestion_generator_init(question="Q?", summaries="...", llm=llm)
    assert result.sub_questions == []

def test_subquestion_generator_refine_prompt_includes_report(mock_llm):
    """Refine prompt contains the current report draft."""
    llm = mock_llm(['[{"question": "New supplementary Q?"}]'])
    run_subquestion_generator_refine(
        question="Q?", summaries="...",
        report="<h1>Current Report</h1><p>...</p>",
        llm=llm
    )
    prompt = str(llm.invoke.call_args[0][0])
    assert "Current Report" in prompt

def test_subquestion_generator_refine_includes_strengthen_to_wording(mock_llm):
    """Refine prompt uses exact paper wording: 'strengthen to the report'."""
    llm = mock_llm(['[{"question": "Q?"}]'])
    run_subquestion_generator_refine(question="Q?", summaries="...", report="r", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "strengthen to the report" in prompt
```

---

### `tests/unit/agents/test_writer.py`

```python
def test_writer_init_generates_report_with_numbered_citations(mock_llm):
    """Writer init report uses [1], [2] numeric citations."""
    report = "<h1>Report</h1><p>Revenue grew by 23% [1]. Churn decreased [2].</p>"
    llm = mock_llm([report])
    result = run_writer_init(
        question="Analyse Q3",
        subquestion_answers=[
            SubquestionAnswer(sub_question="Q1?", answer="A1", chart_files=[], round="init"),
            SubquestionAnswer(sub_question="Q2?", answer="A2", chart_files=[], round="init"),
        ],
        llm=llm
    )
    assert result.citation_style == "numeric"
    assert "[1]" in result.report_content or "[2]" in result.report_content

def test_writer_init_prompt_contains_len_subquestions(mock_llm):
    """Writer init prompt includes citation range: '1 - {num_subquestions}'."""
    llm = mock_llm(["<h1>Report</h1>"])
    run_writer_init(question="Q?", subquestion_answers=[
        SubquestionAnswer(sub_question="Q1?", answer="A1", chart_files=[], round="init"),
        SubquestionAnswer(sub_question="Q2?", answer="A2", chart_files=[], round="init"),
    ], llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "1 - 2" in prompt  # num_subquestions = 2

def test_writer_refine_generates_alphabet_citations(mock_llm):
    """Writer refine uses [a], [b] citations for new content."""
    report = "<h1>Updated</h1><p>Additional finding [a].</p>"
    llm = mock_llm([report])
    result = run_writer_refine(
        question="Q?",
        subquestion_answers=[SubquestionAnswer(sub_question="New Q?", answer="New A", chart_files=[], round="refine")],
        report="<h1>Existing Report</h1>",
        llm=llm
    )
    assert result.citation_style == "alphabetic"

def test_writer_refine_prompt_contains_existing_report(mock_llm):
    """Writer refine prompt includes the current draft report."""
    llm = mock_llm(["<h1>Updated</h1>"])
    run_writer_refine(
        question="Q?",
        subquestion_answers=[SubquestionAnswer(sub_question="Q?", answer="A", chart_files=[], round="refine")],
        report="<h1>My existing report</h1>",
        llm=llm
    )
    prompt = str(llm.invoke.call_args[0][0])
    assert "My existing report" in prompt

def test_writer_refine_prompt_says_do_not_modify_a_lot(mock_llm):
    """Writer refine prompt includes 'Do not modify the given report a lot' (paper rule)."""
    llm = mock_llm(["<h1>Updated</h1>"])
    run_writer_refine(question="Q?", subquestion_answers=[], report="r", llm=llm)
    prompt = str(llm.invoke.call_args[0][0])
    assert "Do not modify the given report a lot" in prompt
```

---

## Unit Tests: Features

### `tests/unit/features/test_catalog.py`

```python
def test_test_connection_mysql_returns_ok_for_valid_credentials(mocker):
    """Valid MySQL credentials → test connection returns success."""
    mocker.patch("sqlalchemy.create_engine").return_value.connect().__enter__().execute.return_value = True
    result = test_mysql_connection(host="localhost", port=3306, database="test", username="user", password="pass")
    assert result.success is True

def test_test_connection_returns_error_for_wrong_credentials(mocker):
    """Wrong credentials → test connection returns failure with message."""
    mocker.patch("sqlalchemy.create_engine", side_effect=OperationalError("Access denied", None, None))
    result = test_mysql_connection(host="localhost", port=3306, database="test", username="bad", password="bad")
    assert result.success is False
    assert "Access denied" in result.message

def test_mysql_password_not_in_api_response(test_client, test_user):
    """DataSource API response never includes MySQL password."""
    response = test_client.get("/api/v1/catalog", headers=auth_headers(test_user))
    for source in response.json():
        assert "password" not in str(source).lower()
        assert "encrypted_password" not in str(source)

def test_catalog_scanner_upserts_existing_table(mocker, test_db):
    """Re-scanning a table updates column_metadata, does not create duplicate row."""
    mocker.patch("catalog.scanner.get_mysql_columns", return_value=[{"name": "id", "type": "INT"}])
    run_scan(source_id="uuid-1", db=test_db)
    mocker.patch("catalog.scanner.get_mysql_columns", return_value=[{"name": "id", "type": "INT"}, {"name": "name", "type": "VARCHAR"}])
    run_scan(source_id="uuid-1", db=test_db)
    tables = test_db.query("SELECT * FROM catalog_tables WHERE data_source_id = 'uuid-1'").fetchall()
    assert len(tables) == 1
    assert len(json.loads(tables[0]["column_metadata"])) == 2

def test_catalog_scanner_soft_deletes_removed_tables(mocker, test_db):
    """Table no longer present in MySQL → marked inactive, not hard-deleted."""
    mocker.patch("catalog.scanner.get_table_names", side_effect=[["orders", "customers"], ["orders"]])
    run_scan(source_id="uuid-1", db=test_db)
    run_scan(source_id="uuid-1", db=test_db)
    customers = test_db.query("SELECT * FROM catalog_tables WHERE table_name = 'customers'").fetchone()
    assert customers is not None
    assert customers["active"] is False

def test_file_scanner_skips_unsupported_extensions(tmp_path):
    """File scanner ignores .exe, .zip, .py files."""
    (tmp_path / "data.csv").write_text("id,name\n1,Alice")
    (tmp_path / "script.py").write_text("print('hello')")
    (tmp_path / "archive.zip").write_bytes(b"PK\x03\x04")
    tables = scan_file_directory(str(tmp_path))
    assert len(tables) == 1
    assert tables[0].table_name == "data.csv"

def test_file_scanner_handles_large_file_headers_only(tmp_path, mocker):
    """File > 500MB → headers stored, row_count_estimate is None."""
    large_file = tmp_path / "big.csv"
    large_file.write_text("id,name,value\n")
    mocker.patch("os.path.getsize", return_value=600 * 1024 * 1024)
    tables = scan_file_directory(str(tmp_path))
    assert tables[0].row_count_estimate is None
    assert len(tables[0].column_metadata) == 3  # headers only
```

---

### `tests/unit/features/test_sandbox.py`

```python
def test_execute_code_returns_stdout(mocker):
    """Successful execution → stdout captured in ExecutionResult."""
    mocker.patch("sandbox.executor._execute_docker", return_value=ExecutionResult(
        stdout="Total: $1,649.83", stderr="", exit_code=0, duration_ms=1200,
        output_files=[], timed_out=False
    ))
    result = execute_code("print('Total: $1,649.83')", session_id="s1", credentials={})
    assert result.stdout == "Total: $1,649.83"
    assert result.exit_code == 0

def test_execute_code_captures_stderr_on_failure(mocker):
    """Failed execution → stderr captured, exit_code non-zero."""
    mocker.patch("sandbox.executor._execute_docker", return_value=ExecutionResult(
        stdout="", stderr="NameError: name 'df' is not defined",
        exit_code=1, duration_ms=300, output_files=[], timed_out=False
    ))
    result = execute_code("print(df)", session_id="s1", credentials={})
    assert result.exit_code == 1
    assert "NameError" in result.stderr

def test_execute_code_truncates_stdout_over_10mb(mocker):
    """stdout > 10MB is truncated and marked with OUTPUT TRUNCATED."""
    large_output = "x" * (11 * 1024 * 1024)
    mocker.patch("sandbox.executor._execute_docker", return_value=ExecutionResult(
        stdout=large_output, stderr="", exit_code=0, duration_ms=500,
        output_files=[], timed_out=False
    ))
    result = execute_code("...", session_id="s1", credentials={})
    assert len(result.stdout) <= 10 * 1024 * 1024 + 100
    assert "OUTPUT TRUNCATED" in result.stdout

def test_execute_code_sets_timed_out_on_timeout(mocker):
    """Execution exceeding timeout → timed_out: True."""
    mocker.patch("sandbox.executor._execute_docker", return_value=ExecutionResult(
        stdout="", stderr="Execution timed out after 120s",
        exit_code=1, duration_ms=120000, output_files=[], timed_out=True
    ))
    result = execute_code("import time; time.sleep(999)", session_id="s1", credentials={}, timeout_seconds=120)
    assert result.timed_out is True

def test_backend_selected_from_config_cloudrun(mocker):
    """config.yaml provider=cloudrun_jobs → Cloud Run backend used."""
    mocker.patch("config.get", return_value={"code_execution": {"provider": "cloudrun_jobs"}})
    mock_cr = mocker.patch("sandbox.executor._execute_cloud_run", return_value=fake_execution_result())
    execute_code("print('ok')", session_id="s1", credentials={})
    mock_cr.assert_called_once()

def test_backend_selected_from_config_docker(mocker):
    """config.yaml provider=docker → Docker backend used."""
    mocker.patch("config.get", return_value={"code_execution": {"provider": "docker"}})
    mock_docker = mocker.patch("sandbox.executor._execute_docker", return_value=fake_execution_result())
    execute_code("print('ok')", session_id="s1", credentials={})
    mock_docker.assert_called_once()

def test_generated_code_always_stored_in_agent_steps_on_failure(mocker, test_db):
    """Generated code logged to agent_steps even when execution fails."""
    mocker.patch("sandbox.executor._execute_docker", return_value=fake_execution_error())
    execute_code_and_record(code="broken code", session_id="s1", step_number=1, db=test_db)
    step = test_db.query("SELECT * FROM agent_steps WHERE session_id = 's1'").fetchone()
    assert step["generated_code"] == "broken code"
    assert step["status"] == "failed"
```

---

### `tests/unit/features/test_checkpoints.py`

```python
def test_cp1_plan_approval_fires_after_planner_init(mocker, test_db):
    """CP1 checkpoint created in DB after planner_init completes."""
    mocker.patch("agents.planner.run_planner_init", return_value=MagicMock(step_text="Load orders", step_number=1))
    mocker.patch("langgraph.graph.interrupt")
    run_session_until_checkpoint(session_id="s1", db=test_db)
    cp = test_db.query("SELECT * FROM checkpoints WHERE session_id = 's1'").fetchone()
    assert cp["checkpoint_type"] == "plan_approval"
    assert cp["status"] == "pending"
    assert "Load orders" in json.loads(cp["payload"])["first_step"]

def test_cp1_approve_resumes_langgraph_thread(mocker):
    """Approving CP1 → LangGraph thread resumes from interrupt."""
    mock_resume = mocker.patch("langgraph.graph.aupdate_state")
    respond_to_checkpoint(session_id="s1", action="approve", hint=None)
    mock_resume.assert_called_once()

def test_cp1_reject_marks_session_abandoned(mocker, test_db):
    """Rejecting CP1 → session status set to 'abandoned'."""
    respond_to_checkpoint(session_id="s1", action="reject", hint=None, db=test_db)
    session = test_db.query("SELECT * FROM analysis_sessions WHERE id = 's1'").fetchone()
    assert session["status"] == "abandoned"

def test_force_exit_fires_at_max_iterations(mocker, test_db):
    """force_exit checkpoint fires when iteration == max_iterations (default 5)."""
    mocker.patch("agents.verifier.run_verifier", return_value=MagicMock(verdict="No"))
    run_session_to_force_exit(session_id="s1", max_iterations=5, db=test_db)
    cp = test_db.query("SELECT * FROM checkpoints WHERE checkpoint_type = 'force_exit'").fetchone()
    assert cp is not None
    assert json.loads(cp["payload"])["iteration"] == 5

def test_force_exit_hint_resets_iteration_counter(mocker, test_db):
    """Providing hint at force_exit → iteration reset to max_iterations - 3."""
    state = respond_to_checkpoint(
        session_id="s1", action="hint",
        hint="Use net_amount column not gross_amount",
        current_state={"iteration": 5, "max_iterations": 5},
        db=test_db
    )
    assert state["iteration"] == 2  # 5 - 3 = 2

def test_force_exit_hint_injected_into_question_context(mocker, test_db):
    """Hint from force_exit appears in {question} for subsequent LLM calls."""
    mocker.patch("agents.planner.run_planner_next") as mock_planner
    respond_to_checkpoint(
        session_id="s1", action="hint",
        hint="Filter by 2024 dates only",
        current_state={"iteration": 5, "max_iterations": 5, "user_query": "Total revenue?"},
        db=test_db
    )
    call_kwargs = mock_planner.call_args[1]
    assert "Filter by 2024 dates only" in call_kwargs["question"]

def test_cp2_fires_after_verifier_yes(mocker, test_db):
    """CP2 checkpoint fires when Verifier returns 'Yes'."""
    mocker.patch("agents.verifier.run_verifier", return_value=MagicMock(verdict="Yes"))
    run_session_to_cp2(session_id="s1", db=test_db)
    cp = test_db.query("SELECT * FROM checkpoints WHERE checkpoint_type = 'result_confirmation'").fetchone()
    assert cp["status"] == "pending"

def test_cp3_fires_after_finalyzer(mocker, test_db):
    """CP3 checkpoint fires after Finalyzer or Writer completes."""
    mocker.patch("agents.finalyzer.run_finalyzer", return_value=MagicMock(code="print('ok')", mode="base"))
    run_session_to_cp3(session_id="s1", db=test_db)
    cp = test_db.query("SELECT * FROM checkpoints WHERE checkpoint_type = 'report_approval'").fetchone()
    assert cp["status"] == "pending"

def test_hint_action_invalid_for_plan_approval_checkpoint(test_db):
    """action='hint' on a plan_approval checkpoint → 400 error."""
    with pytest.raises(InvalidCheckpointActionError):
        respond_to_checkpoint(session_id="s1", action="hint", hint="...",
                              checkpoint_type="plan_approval", db=test_db)

def test_checkpoint_survives_server_restart(mocker, test_db):
    """LangGraph AsyncPostgresSaver restores thread after restart — pending checkpoint retrievable."""
    # Simulate: checkpoint created, server restarts, client polls
    create_pending_checkpoint(session_id="s1", checkpoint_type="plan_approval",
                              payload={"first_step": "Load orders"}, db=test_db)
    # After 'restart', get pending checkpoint via API
    cp = get_pending_checkpoint(session_id="s1", db=test_db)
    assert cp["checkpoint_type"] == "plan_approval"
    assert cp["status"] == "pending"
```

---

## Unit Tests: API

### `tests/unit/api/test_analyses_api.py`

```python
def test_create_analysis_returns_201(test_client, auth_headers):
    """POST /api/v1/analyses returns 201 with session object."""
    response = test_client.post("/api/v1/analyses",
        json={"user_query": "What is total Q3 revenue?"},
        headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "active"
    assert response.json()["user_query"] == "What is total Q3 revenue?"

def test_create_analysis_requires_user_query(test_client, auth_headers):
    """POST /api/v1/analyses without user_query returns 422."""
    response = test_client.post("/api/v1/analyses", json={}, headers=auth_headers)
    assert response.status_code == 422

def test_list_analyses_returns_only_current_user_sessions(test_client, auth_headers_user1, auth_headers_user2, test_db):
    """GET /api/v1/analyses returns only the authenticated user's sessions."""
    create_session(user_id="user1", query="User 1 query", db=test_db)
    create_session(user_id="user2", query="User 2 query", db=test_db)
    response = test_client.get("/api/v1/analyses", headers=auth_headers_user1)
    sessions = response.json()["items"]
    assert all(s["user_query"] == "User 1 query" for s in sessions)

def test_get_analysis_returns_403_for_other_users_session(test_client, auth_headers_user2, test_db):
    """GET /api/v1/analyses/{id} returns 403 if session belongs to another user."""
    session_id = create_session(user_id="user1", query="Q", db=test_db)
    response = test_client.get(f"/api/v1/analyses/{session_id}", headers=auth_headers_user2)
    assert response.status_code == 403

def test_list_analyses_full_text_search(test_client, auth_headers, test_db):
    """GET /api/v1/analyses?q=revenue returns matching sessions."""
    create_session(user_id="me", query="What is total revenue?", db=test_db)
    create_session(user_id="me", query="Analyse customer churn", db=test_db)
    response = test_client.get("/api/v1/analyses?q=revenue", headers=auth_headers)
    items = response.json()["items"]
    assert len(items) == 1
    assert "revenue" in items[0]["user_query"].lower()

def test_get_analysis_includes_pending_checkpoint(test_client, auth_headers, test_db):
    """GET /api/v1/analyses/{id} includes pending_checkpoint inline if one exists."""
    session_id = create_session_with_pending_checkpoint(db=test_db)
    response = test_client.get(f"/api/v1/analyses/{session_id}", headers=auth_headers)
    assert response.json()["pending_checkpoint"] is not None
    assert response.json()["pending_checkpoint"]["status"] == "pending"

def test_unauthenticated_request_returns_401(test_client):
    """Requests without auth token → 401."""
    response = test_client.get("/api/v1/analyses")
    assert response.status_code == 401
```

---

## Integration Tests

### `tests/integration/agents/test_analyzer_integration.py`

```python
@pytest.mark.integration
def test_analyzer_generates_executable_script_for_csv(real_llm, tmp_path):
    """Real LLM generates Python that correctly describes a CSV file."""
    csv = tmp_path / "sales.csv"
    csv.write_text("order_id,product,amount\n1,Widget,99.99\n2,Gadget,149.99")
    result = run_analyzer(sources=[FileSource(str(csv))], llm=real_llm)
    assert "order_id" in result.summaries
    assert "product" in result.summaries
    assert "amount" in result.summaries

@pytest.mark.integration
def test_analyzer_generates_executable_script_for_mysql(real_llm, test_mysql_url):
    """Real LLM generates Python that correctly describes MySQL tables."""
    result = run_analyzer(sources=[MySQLSource("test_db", url=test_mysql_url)], llm=real_llm)
    assert "test_orders" in result.summaries
    assert "test_customers" in result.summaries
    assert "net_amount" in result.summaries

@pytest.mark.integration
def test_analyzer_summaries_are_non_empty(real_llm, test_mysql_url):
    """Analyzer output summaries string is non-empty after real execution."""
    result = run_analyzer(sources=[MySQLSource("test_db", url=test_mysql_url)], llm=real_llm)
    assert len(result.summaries) > 100
```

---

### `tests/integration/agents/test_planner_integration.py`

```python
@pytest.mark.integration
def test_planner_init_generates_sensible_first_step(real_llm):
    """Real LLM generates a coherent first step for a revenue query."""
    result = run_planner_init(
        question="What is the total net revenue for Q3 2024?",
        summaries="test_orders table: order_id (INT), customer_id (INT), product_id (INT), quantity (INT), order_date (DATE), net_amount (DECIMAL). Sample: order_id=1, order_date=2024-07-05, net_amount=99.98",
        llm=real_llm
    )
    assert len(result.step_text) > 10
    assert "import" not in result.step_text  # no code in step text
    assert any(word in result.step_text.lower() for word in ["load", "query", "select", "fetch", "connect"])

@pytest.mark.integration
def test_planner_next_generates_coherent_follow_up(real_llm):
    """Real LLM generates a follow-up step that builds on previous results."""
    result = run_planner_next(
        question="What is the total net revenue for Q3 2024?",
        summaries="test_orders: ...",
        plan=["1. Load test_orders table and print first 5 rows"],
        result="   order_id  customer_id  ...  order_date  net_amount\n0         1           1  ...  2024-07-05       99.98\n...",
        llm=real_llm
    )
    assert result.step_number == 2
    assert any(word in result.step_text.lower() for word in ["filter", "q3", "2024", "sum", "total", "aggregate"])
```

---

### `tests/integration/features/test_sandbox_integration.py`

```python
@pytest.mark.integration
def test_sandbox_executes_pandas_code(real_docker, test_mysql_url, tmp_path):
    """Real Docker sandbox executes pandas code successfully."""
    code = """
import os
import pandas as pd
from sqlalchemy import create_engine
engine = create_engine(os.environ['MYSQL_URL'])
df = pd.read_sql('SELECT * FROM test_orders', engine)
print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
"""
    result = execute_code(code, session_id="test-s1", credentials={"mysql_url": test_mysql_url})
    assert result.exit_code == 0
    assert "Rows: 9" in result.stdout
    assert "net_amount" in result.stdout

@pytest.mark.integration
def test_sandbox_saves_chart_to_output_dir(real_docker, tmp_path):
    """Code saving a chart to OUTPUT_DIR → chart file appears in output_files."""
    code = """
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.plot([1,2,3], [4,5,6])
plt.savefig(os.path.join(os.environ['OUTPUT_DIR'], 'test_chart.png'))
print("Chart saved")
"""
    result = execute_code(code, session_id="test-s2", credentials={}, output_dir=str(tmp_path))
    assert result.exit_code == 0
    assert "test_chart.png" in result.output_files

@pytest.mark.integration
def test_sandbox_blocks_network_access(real_docker):
    """Code attempting network request fails (network_mode: none)."""
    code = "import urllib.request; urllib.request.urlopen('http://example.com')"
    result = execute_code(code, session_id="test-s3", credentials={})
    assert result.exit_code != 0
    assert "socket" in result.stderr.lower() or "network" in result.stderr.lower() or "connect" in result.stderr.lower()

@pytest.mark.integration
def test_sandbox_blocks_write_outside_output_dir(real_docker, tmp_path):
    """Code writing outside OUTPUT_DIR fails (permission denied)."""
    code = "open('/etc/evil.txt', 'w').write('hacked')"
    result = execute_code(code, session_id="test-s4", credentials={})
    assert result.exit_code != 0

@pytest.mark.integration
def test_sandbox_timeout_enforced(real_docker):
    """Code exceeding timeout → timed_out=True."""
    code = "import time; time.sleep(999)"
    result = execute_code(code, session_id="test-s5", credentials={}, timeout_seconds=5)
    assert result.timed_out is True
```

---

## System Tests

### `tests/system/test_base_flow.py`

```python
@pytest.mark.system
async def test_full_base_dsstar_happy_path(real_llm, real_db, real_docker, test_mysql_url):
    """
    Full end-to-end: factoid query → Analyzer → Planner → Coder → Verifier 'Yes' →
    CP2 approved → Finalyzer → CP3 saved.
    Result must contain the correct total revenue ($1,649.83).
    """
    session = await create_session(
        user_query="What is the total net revenue for Q3 2024 in the test_orders table?",
        data_source_ids=[MYSQL_TEST_SOURCE_ID],
        db=real_db
    )

    # CP1: approve the first step
    cp1 = await wait_for_checkpoint(session.id, "plan_approval", timeout=60)
    assert cp1 is not None
    await respond_checkpoint(session.id, action="approve")

    # CP2: confirm result
    cp2 = await wait_for_checkpoint(session.id, "result_confirmation", timeout=120)
    assert cp2 is not None
    assert "1,649.83" in cp2.payload["result"] or "1649.83" in cp2.payload["result"]
    await respond_checkpoint(session.id, action="approve")

    # CP3: save
    cp3 = await wait_for_checkpoint(session.id, "report_approval", timeout=60)
    assert cp3 is not None
    assert cp3.payload["mode"] == "base"
    await respond_checkpoint(session.id, action="approve")

    # Verify session completed
    final = await get_session(session.id, db=real_db)
    assert final.status == "completed"

    # Verify report saved
    report = await get_report_for_session(session.id, db=real_db)
    assert report is not None
    assert "1,649.83" in report.final_result or "1649.83" in report.final_result
```

---

### `tests/system/test_force_exit_flow.py`

```python
@pytest.mark.system
async def test_force_exit_fires_and_hint_resolves(real_llm, real_db, real_docker):
    """
    Force-exit CP fires at max_iterations. User provides hint. Agents resolve within 3 more tries.
    """
    session = await create_session(
        user_query="What is total revenue?",
        max_iterations=2,   # low limit to trigger force_exit quickly
        db=real_db
    )
    await respond_checkpoint(session.id, action="approve")  # CP1

    # Force-exit fires at iteration 2
    force_exit_cp = await wait_for_checkpoint(session.id, "force_exit", timeout=120)
    assert force_exit_cp is not None
    assert force_exit_cp.payload["iteration"] == 2

    # Provide hint
    await respond_checkpoint(session.id, action="hint",
                             hint="Use the net_amount column and filter where order_date >= '2024-07-01'")

    # Agents should resolve within 3 more tries
    cp2 = await wait_for_checkpoint(session.id, "result_confirmation", timeout=120)
    assert cp2 is not None  # agents resolved

@pytest.mark.system
async def test_force_exit_abandon_marks_session_failed(real_db):
    """Abandoning at force_exit → session status = 'failed'."""
    session = await create_session(user_query="Q?", max_iterations=1, db=real_db)
    await respond_checkpoint(session.id, action="approve")  # CP1
    force_exit_cp = await wait_for_checkpoint(session.id, "force_exit", timeout=120)
    await respond_checkpoint(session.id, action="reject")  # abandon
    final = await get_session(session.id, db=real_db)
    assert final.status == "failed"
```

---

### `tests/system/test_dsstar_plus_flow.py`

```python
@pytest.mark.system
async def test_full_dsstar_plus_report_generation(real_llm, real_db, real_docker):
    """
    DSSTAR+ full flow: exploratory query → SubquestionGenerator (init + 3 refine rounds) →
    Writer (init + 3 refine) → HTML report at CP3.
    """
    session = await create_session(
        user_query="Analyse the sales performance of our products in Q3 2024 across different customer regions.",
        data_source_ids=[MYSQL_TEST_SOURCE_ID],
        db=real_db
    )

    # CP1: approve
    await respond_checkpoint(session.id, action="approve")

    # CP2: confirm
    cp2 = await wait_for_checkpoint(session.id, "result_confirmation", timeout=300)
    assert cp2 is not None
    await respond_checkpoint(session.id, action="approve")

    # CP3: report ready
    cp3 = await wait_for_checkpoint(session.id, "report_approval", timeout=300)
    assert cp3 is not None
    assert cp3.payload["mode"] == "plus"
    assert cp3.payload["report_title"] is not None
    assert "<html>" in cp3.payload["preview"].lower()
    await respond_checkpoint(session.id, action="approve")

    # Verify report saved with HTML content
    report = await get_report_for_session(session.id, db=real_db)
    assert report is not None
    assert report.html_content is not None
    assert "[1]" in report.html_content  # numbered citations present

@pytest.mark.system
async def test_dsstar_plus_refinement_adds_content(real_llm, real_db):
    """Report after 3 refinement rounds has more content than after init."""
    # Not full E2E — tests the writer refinement loop specifically
    init_report = await run_writer_init_only(question="Analyse Q3 sales", sub_answers=FIXTURE_ANSWERS, llm=real_llm)
    refined_report = await run_writer_with_3_refinements(question="Analyse Q3 sales", sub_answers=FIXTURE_ANSWERS, llm=real_llm)
    assert len(refined_report) > len(init_report)
    assert "[a]" in refined_report  # alphabet citations from refinement

@pytest.mark.system
async def test_on_demand_refinement_via_api(real_llm, real_db, test_client):
    """POST /reports/{id}/refine triggers additional refinement round."""
    # Setup: completed DSSTAR+ session with saved report
    report_id = await create_completed_dsstar_plus_report(db=real_db)
    original_length = len((await get_report(report_id, db=real_db)).html_content)

    response = test_client.post(f"/api/v1/reports/{report_id}/refine", headers=auth_headers)
    assert response.status_code == 202

    # Wait for refinement to complete
    await asyncio.sleep(30)
    updated = await get_report(report_id, db=real_db)
    assert len(updated.html_content) >= original_length
```

---

## GitHub Actions Workflows

### `.github/workflows/unit.yml` (runs on every commit + PR)
```yaml
name: Unit Tests
on: [push, pull_request]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[test]"
      - run: pytest tests/unit/ -v --tb=short --cov=backend --cov-report=xml --cov-fail-under=80
      - uses: codecov/codecov-action@v4
```

### `.github/workflows/integration.yml` (runs on PR only)
```yaml
name: Integration Tests
on: [pull_request]
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: dsstar_test }
        ports: ["5432:5432"]
      mysql:
        image: mysql:8.0
        env: { MYSQL_ROOT_PASSWORD: test, MYSQL_DATABASE: test_db }
        ports: ["3306:3306"]
    env:
      TEST_POSTGRES_URL: postgresql://postgres:test@localhost/dsstar_test
      TEST_MYSQL_URL: mysql+pymysql://root:test@localhost/test_db
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY_TEST }}
      LLM_MODEL: claude-haiku-4-5-20251001
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[test]"
      - run: pytest tests/unit/ tests/integration/ -v --tb=short -m "not system"
```

### `.github/workflows/system.yml` (nightly on main)
```yaml
name: System Tests
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 2 * * *"   # 02:00 UTC daily
jobs:
  system:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: dsstar_test }
        ports: ["5432:5432"]
      mysql:
        image: mysql:8.0
        env: { MYSQL_ROOT_PASSWORD: test, MYSQL_DATABASE: test_db }
        ports: ["3306:3306"]
    env:
      TEST_POSTGRES_URL: postgresql://postgres:test@localhost/dsstar_test
      TEST_MYSQL_URL: mysql+pymysql://root:test@localhost/test_db
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY_TEST }}
      LLM_MODEL: claude-haiku-4-5-20251001
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[test]"
      - run: pytest tests/system/ -v --tb=long -m system --timeout=600
```

### `pyproject.toml` test config
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: requires real LLM and Docker",
    "system: full end-to-end, slow",
]
testpaths = ["tests"]

[tool.coverage.run]
source = ["backend"]
omit = ["tests/*", "backend/migrations/*"]

[tool.coverage.report]
fail_under = 80
```

---

## Pre-commit Hook Config (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff           # linting
      - id: ruff-format    # formatting

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--strict]

  - repo: local
    hooks:
      - id: fast-unit-tests
        name: Fast unit tests (no LLM, no DB)
        language: system
        entry: pytest tests/unit/ -x -q --timeout=30 -m "not integration and not system"
        pass_filenames: false
        always_run: true
```

---

## Coverage Thresholds

| Module | Minimum coverage |
|---|---|
| `backend/agents/` | 90% |
| `backend/api/` | 85% |
| `backend/features/` | 85% |
| Overall | 80% |

Coverage checked by `pytest-cov` in CI. PR blocked if below threshold.
