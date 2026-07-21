# Feature Spec: Sandbox Code Execution

## Purpose
Provides an isolated, resource-limited environment for executing agent-generated Python
scripts. Abstracts over two execution backends: Cloud Run Jobs (cloud deployment) and
Docker subprocess (on-prem deployment). Selected via `config.yaml`.

## Execution Backends

### Cloud (Google Cloud Run Jobs)
Each code execution spawns a new Cloud Run Job:
- Isolated container per execution — no shared state between runs
- Billed per second of CPU/memory usage
- Automatic teardown after execution completes or times out
- No Docker-in-Docker required

### On-prem (Docker subprocess)
Each code execution spawns a Docker container via the Docker SDK:
- Isolated container with mounted volumes for data access
- Resource limits enforced via Docker API
- Container torn down after execution

## Environment Contract

All execution backends provide the same environment to generated code:

| Env var | Value | Purpose |
|---|---|---|
| `MYSQL_URL` | `mysql+pymysql://user:pass@host/db` | DB connection (read-only user) |
| `DATA_DIR` | `/data` | Base path for flat files (read-only mount) |
| `OUTPUT_DIR` | `/output` | Write charts and output files here |
| `PYTHONPATH` | `/app` | Consistent import resolution |

The generated code uses `os.environ["MYSQL_URL"]`, `os.environ["DATA_DIR"]`, and
`os.environ["OUTPUT_DIR"]` — never hardcoded paths or credentials.

## Docker Image (`docker/sandbox/Dockerfile`)
```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir \
    pandas==2.2.* \
    numpy==1.26.* \
    matplotlib==3.8.* \
    plotly==5.20.* \
    sqlalchemy==2.0.* \
    pymysql==1.1.* \
    scikit-learn==1.4.* \
    scipy==1.12.* \
    openpyxl==3.1.* \
    xlrd==2.0.* \
    python-dotenv==1.0.*

# No shell, no package managers, no network tools
RUN apt-get remove -y curl wget apt-get && apt-get autoremove -y

WORKDIR /app
```

No `CMD` — the script path is injected per execution.

## Resource Limits

| Resource | Limit | Rationale |
|---|---|---|
| CPU | 2 vCPU | Sufficient for pandas ops; prevents runaway computation |
| Memory | 4GB | Handles most analytical DataFrames |
| Execution timeout | 120 seconds | Long enough for complex queries; kills runaway loops |
| Network | MySQL host only (egress firewall rule) | Prevents data exfiltration |
| Filesystem writes | `OUTPUT_DIR` only | Prevents host filesystem pollution |
| Max output size | 10MB stdout | Prevents memory exhaustion from print loops |

## Execution Interface (`sandbox/executor.py`)

```python
class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    output_files: list[str]   # filenames written to OUTPUT_DIR
    timed_out: bool

async def execute_code(
    code: str,
    session_id: str,
    data_source_credentials: dict,
    timeout_seconds: int = 120,
) -> ExecutionResult:
    ...
```

### Cloud Run Jobs execution
```python
async def _execute_cloud_run(code, session_id, credentials, timeout):
    # 1. Write code to GCS as {session_id}/{step_n}.py
    # 2. Submit Cloud Run Job with:
    #    - image: dsstar-sandbox
    #    - env vars: MYSQL_URL, DATA_DIR (GCS mount), OUTPUT_DIR (GCS mount)
    #    - args: ["python", "/app/script.py"]
    #    - timeout: {timeout}s
    #    - resource limits: 2 CPU, 4Gi memory
    # 3. Poll job status until complete or timeout
    # 4. Fetch stdout/stderr from Cloud Logging
    # 5. List OUTPUT_DIR for generated files
    # 6. Return ExecutionResult
```

### On-prem Docker execution [LOCKED — fixes a spec contradiction]
The original spec set `network_mode="none"` while also claiming MySQL is reached via
`host.docker.internal` — those two are mutually exclusive; `network_mode: none` disables
all networking including host access. Fixed approach: a dedicated bridge network for
sandbox containers, with an egress firewall rule (iptables, or Docker's `internal` network
flag is not sufficient alone) restricting outbound traffic to the MySQL host/port only.

```python
async def _execute_docker(code, session_id, credentials, timeout):
    import docker
    client = docker.from_env()

    # Write code to temp file
    script_path = f"{TEMP_DIR}/{session_id}/script.py"
    write_script(code, script_path)

    container = client.containers.run(
        image="dsstar-sandbox:latest",
        command=["python", "/app/script.py"],
        volumes={
            script_path:       {"bind": "/app/script.py", "mode": "ro"},
            DATA_DIR:          {"bind": "/data",          "mode": "ro"},
            OUTPUT_DIR:        {"bind": "/output",        "mode": "rw"},
        },
        environment={
            "MYSQL_URL": credentials["mysql_url"],
        },
        mem_limit="4g",
        nano_cpus=2_000_000_000,
        network="dsstar-sandbox-net",  # pre-created bridge network, egress-restricted to
                                        # the MySQL host/port via iptables rule on the host
                                        # (setup documented in docker/sandbox/README.md)
        remove=True,
        detach=False,
        stdout=True,
        stderr=True,
        timeout=timeout,
    )
    ...
```

Note: MySQL access on on-prem uses `host.docker.internal` as the MySQL host (added via
Docker's `extra_hosts` on the container), injected via the `MYSQL_URL` environment
variable. The egress rule on the `dsstar-sandbox-net` bridge is what actually prevents
reaching anything else — `network_mode: none` alone would have blocked MySQL too, and
omitting a network restriction entirely would have allowed unrestricted egress.

## Execution Flow per Agent Call

```
Coder produces code (str)
    → Debugger reviews/fixes code
    → sandbox/executor.py: execute_code(code, session_id, credentials)
        → write script to temp location
        → spawn container (Cloud Run Job or Docker)
        → capture stdout (max 10MB), stderr, exit_code
        → collect OUTPUT_DIR file list
        → return ExecutionResult
    → if stderr non-empty AND exit_code != 0:
        → Debugger called: summarize_traceback + repair_code
        → execute_code again (once)
    → pass ExecutionResult to Verifier
```

## Output File Handling

Files written to `OUTPUT_DIR` during execution are:
1. Listed in `ExecutionResult.output_files`
2. Copied to persistent storage (`GCS bucket` on cloud, `DATA_DIR/outputs/` on-prem)
3. Paths stored in `agent_steps.output_state` as metadata
4. Charts referenced in reports are loaded from persistent storage, not the container

## Audit Trail

Every execution is recorded in `agent_steps`:
```
agent_name: "coder"
generated_code: <the script that ran>
execution_result: <stdout, truncated to 50KB>
duration_ms: <actual wall time>
status: "completed" | "failed"
error_message: <stderr if exit_code != 0>
```

Generated code is ALWAYS stored — even if execution failed — for audit and debugging.

## Security Rules
- Generated code MUST run as a non-root user inside the container (`USER 1000:1000` in Dockerfile)
- Network access MUST be restricted to MySQL host only
- Filesystem writes MUST be restricted to `OUTPUT_DIR`
- `OUTPUT_DIR` contents MUST be scanned for executable files before serving to UI
  (prevent storing malicious executables as "chart outputs")
- Credentials MUST be injected as environment variables — never written to disk inside the container
- Container MUST be torn down after execution regardless of success/failure

## Backend Selection (config.yaml)
```yaml
code_execution:
  provider: cloudrun_jobs   # or: docker
  timeout_seconds: 120
  memory_limit_gb: 4
  cpu_limit: 2

  # Cloud Run Jobs specific
  cloudrun_region: us-central1
  cloudrun_job_name: dsstar-sandbox

  # Docker specific
  docker_image: dsstar-sandbox:latest
```

## Error Handling
| Error | Behaviour |
|---|---|
| Execution timeout | `ExecutionResult.timed_out: true`, stderr = "Execution timed out after 120s" |
| Container OOM | Exit code 137, stderr captured, Debugger called |
| Code syntax error | Non-zero exit, stderr has traceback, Debugger called |
| OUTPUT_DIR write permission error | Treated as execution error, Debugger called |
| Cloud Run Job quota exceeded | Retry after 30s backoff (up to 3 times), then fail session |
| Docker daemon unavailable (on-prem) | 503 on session start with "execution service unavailable" |
| stdout > 10MB | Truncated to 10MB with appended notice "OUTPUT TRUNCATED" |

## Test Scenarios

### Unit
- `execute_code` with clean Python → exit_code 0, stdout captured
- `execute_code` with syntax error → exit_code 1, stderr captured, Debugger called
- `execute_code` timeout → timed_out: true
- Stdout > 10MB → truncated to 10MB
- Generated code always stored in agent_steps regardless of outcome
- Backend selected from config (cloudrun vs docker)

### Integration (real Docker sandbox)
- pandas DataFrame operations execute correctly and stdout captured
- SQLAlchemy MySQL query executes via MYSQL_URL env var
- matplotlib chart saved to OUTPUT_DIR and listed in output_files
- Script writing to path outside OUTPUT_DIR fails (permission denied)
- Script attempting network request to a non-MySQL host fails (blocked by the
  `dsstar-sandbox-net` egress rule); a request to the configured MySQL host succeeds
- Container torn down after execution (verified via `docker ps`)
