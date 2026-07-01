# Technical Design Document
## CBUAE Financial Intelligence Platform (FIP) — V1

**Stage:** TDD — Stage 3  
**Branch:** `docs/product-lifecycle`  
**Date:** 2026-07-01  
**Author:** Engineering, Agent-DASC  
**Status:** Draft — In Progress  
**PRD Reference:** `01-prd/01-prd-cbuae-fip.md` (v0.2)

**Prerequisite documents:**
- `00-discovery/01-paper-analysis.md` — DS-STAR paper deep-dive (arXiv:2509.21825)
- `00-discovery/04-architecture-decisions.md` — 18 architecture decisions with paper references (Q1–Q18)
- `00-discovery/03-architecture-v2.html` — Architecture diagram v3.3
- `00-discovery/05-feature-discussion.md` — Feature decisions (Topics 1–10)
- `01-prd/01-prd-cbuae-fip.md` — Full PRD with functional requirements and acceptance criteria

**Pending inputs (blocks TDD sections marked `[PENDING]`):**
- **OQ-1** — Authentication system (Active Directory / CBUAE SSO / standalone) — blocks §10 Auth design
- **OQ-7** — On-premise GPU hardware specs — blocks §15 Inference & Deployment

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-07-01 | Engineering, Agent-DASC | Initial draft — architecture overview, pipeline, agents, infra, API, database schema |

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Topology](#2-architecture-topology)
3. [Technology Stack](#3-technology-stack)
4. [LangGraph Pipeline — DS-STAR Implementation](#4-langgraph-pipeline--ds-star-implementation)
5. [Agent Specifications](#5-agent-specifications)
6. [Docker Sandbox](#6-docker-sandbox)
7. [LLM Provider Adapter](#7-llm-provider-adapter)
8. [Database Schema](#8-database-schema)
9. [File Storage](#9-file-storage)
10. [Task Queue](#10-task-queue)
11. [REST API](#11-rest-api)
12. [WebSocket](#12-websocket)
13. [Frontend Architecture](#13-frontend-architecture)
14. [Report Generation](#14-report-generation)
15. [Authentication & RBAC](#15-authentication--rbac)
16. [Audit Log](#16-audit-log)
17. [Data Versioning & Snapshots](#17-data-versioning--snapshots)
18. [Deployment Architecture](#18-deployment-architecture)
19. [Performance Considerations](#19-performance-considerations)
20. [Security Implementation](#20-security-implementation)
21. [Open Questions Tracker](#21-open-questions-tracker)

---

## 1. System Overview

The Financial Intelligence Platform (FIP) is an internal CBUAE analytics system that accepts natural language queries from non-technical supervisory analysts and returns data-backed answers and reports — with full traceability from question to code to result.

It is built on the **DS-STAR multi-agent architecture** (arXiv:2509.21825, Google Cloud, Sept 2025), adapted for the CBUAE Financial Crime & Market Conduct vertical. The system operates in two modes:

- **FIP-Insight** (DS-STAR mode): Specific, factoid, and multi-step analytical questions. Returns a chat-style answer: executive summary + tables + charts.
- **FIP-Research** (DS-STAR+ mode): Open-ended research and thematic analysis. Returns a structured, cited report document.

**Deployment constraints that shape every technical decision:**
- On-premise only. Fully air-gapped. Zero outbound network.
- LLM inference runs locally (Ollama or vLLM) on CBUAE-owned GPU hardware.
- All data stays within CBUAE infrastructure. No cloud storage, no cloud APIs in production.
- Analyst data access is governed by department-level RBAC enforced at the API layer.

---

## 2. Architecture Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ANALYST BROWSER                                                         │
│  React SPA — /login · /chat · /dashboard · /admin                       │
│  ┌──────────┐   HTTPS + JWT    ┌─────────────────────────────────────┐  │
│  │  React   │ ────────────────►│         Nginx (reverse proxy)       │  │
│  │  + WS    │ ◄────────────────│         TLS termination             │  │
│  └──────────┘   WS + JWT       └──────────────┬──────────────────────┘  │
└──────────────────────────────────────────────-│──────────────────────────┘
                                                │ mTLS
                       ┌───────────────────────▼──────────────────────────┐
                       │   API SERVER (FastAPI)                            │
                       │   POST /api/v1/query    GET /api/v1/tasks/{id}   │
                       │   GET  /api/v1/files    POST /api/v1/files        │
                       │   WS   /ws/tasks/{id}   POST /api/v1/admin/…     │
                       │                                                   │
                       │   ┌─────────────────────────────────────────┐    │
                       │   │   Query Clarity Agent (pre-routing)     │    │
                       │   └────────────────┬────────────────────────┘    │
                       └────────────────────│─────────────────────────────┘
                                            │ mTLS
                       ┌────────────────────▼─────────────────────────────┐
                       │   TASK QUEUE (Celery + Redis Sentinel)           │
                       │   Priority queue: Insight (P1) · Research (P2)  │
                       │   DLQ for failed tasks                           │
                       └────────────────────┬─────────────────────────────┘
                                            │
                       ┌────────────────────▼─────────────────────────────┐
                       │   WORKER POOL (Celery workers)                   │
                       │   ┌─────────────────────────────────────────┐   │
                       │   │  LangGraph Runtime                       │   │
                       │   │  DS-STAR graph / DS-STAR+ graph          │   │
                       │   │  Checkpoints → PostgreSQL                │   │
                       │   └─────────────┬───────────────────────────┘   │
                       │                 │                                 │
                       │   ┌─────────────▼───────────────────────────┐   │
                       │   │  Docker Sandbox Manager                  │   │
                       │   │  1 container per task (per sub-q in +)  │   │
                       │   │  docker exec per round                   │   │
                       │   └─────────────────────────────────────────┘   │
                       └──────────────────────────────────────────────────┘
                                            │ mTLS (all)
            ┌───────────────────────────────┼────────────────────────────┐
            │                               │                            │
   ┌────────▼──────┐            ┌───────────▼──────┐          ┌─────────▼──────┐
   │  PostgreSQL   │            │  MinIO           │          │  Ollama /      │
   │  • Tasks      │            │  • Uploaded files│          │  vLLM          │
   │  • Checkpoints│            │  • Data snapshots│          │  (local GPU)   │
   │  • Audit log  │            │  • Script archive│          │  LLM inference │
   │  • User/RBAC  │            │  • Report files  │          │                │
   │  • File meta  │            │  • Temp outputs  │          └────────────────┘
   └───────────────┘            └──────────────────┘
                                            │
                                   ┌────────▼────────┐
                                   │  HashiCorp Vault │
                                   │  Secrets only    │
                                   └─────────────────┘
```

**Network zones:**
- Zone A (Browser → Nginx): HTTPS/WSS with JWT in `Authorization: Bearer` header
- Zone B (Nginx → API Server → Workers): mTLS, internal service mesh
- Zone C (Workers → PostgreSQL / MinIO / Ollama): mTLS, internal only
- Zone D (Vault): mTLS, AppRole auth; all secrets fetched at service startup; no env-var secrets

**What is NOT present in this topology:**
- No internet gateway. No external DNS resolution. No cloud endpoints.
- No email relay (V1 has no email notifications — FR-AH-03).
- No CI/CD runner (deployments handled via offline artifact delivery by IT).

---

## 3. Technology Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Frontend framework | React | 18.x | |
| Frontend styling | Tailwind CSS | 4.x | |
| Frontend components | shadcn/ui | latest | Built on Radix UI primitives |
| Charts (primary) | Recharts | 2.x | For standard bar, line, area, pie |
| Charts (fallback) | Plotly.js | 5.x | For advanced chart types Recharts can't handle |
| WebSocket client | Native browser WebSocket API | — | No library needed |
| API server | FastAPI | 0.111+ | Python 3.11+ |
| Agent orchestration | LangGraph | 0.2+ | LangGraph Server for checkpoint management |
| Checkpoint store | PostgreSQL | 16 | Via `langgraph-checkpoint-postgres` |
| Task queue | Celery | 5.x | |
| Queue broker | Redis Sentinel | 7.x | HA mode with 3 Sentinel nodes |
| Result backend | Redis | 7.x | Same Sentinel cluster |
| LLM inference | Ollama (prod) / Gemini API (dev) | — | Behind provider adapter |
| Object storage | MinIO | latest stable | S3-compatible, on-premise |
| Relational database | PostgreSQL | 16 | Single instance + streaming replica |
| Secret management | HashiCorp Vault | 1.17+ | AppRole auth |
| Reverse proxy | Nginx | 1.25+ | TLS termination, static asset serving |
| Sandbox runtime | Docker | 26+ | Rootless mode on worker hosts |
| Report: Word | python-docx-template | 0.17+ | Jinja2 template engine for .docx |
| Report: PDF | LibreOffice headless | 24.x | Converts .docx → .pdf server-side |
| Report: Excel | openpyxl | 3.x | |
| Auth | PyJWT + bcrypt | — | HS256 tokens; 8-hour expiry |
| Internal comms | mTLS (mutual TLS) | — | All service-to-service |
| Containerisation | Docker Compose (dev) / Kubernetes (prod) | — | |

**Python version:** 3.11 throughout (backend, workers, sandbox). Type hints required on all public functions.

---

## 4. LangGraph Pipeline — DS-STAR Implementation

### 4.1 Graph Overview

Two separate LangGraph `StateGraph` definitions:

1. **`dsstar_graph`** — FIP-Insight (DS-STAR mode)
2. **`dsstar_plus_graph`** — FIP-Research (DS-STAR+ mode); internally calls `dsstar_graph` per sub-question

Both graphs checkpoint to PostgreSQL after every node execution. The checkpoint key is `(thread_id=task_id, checkpoint_id=round_number)`.

### 4.2 DS-STAR State Schema

```python
from typing import Annotated
from langgraph.graph import add_messages
from pydantic import BaseModel

class PlanStep(BaseModel):
    index: int
    text: str
    status: str  # "pending" | "complete" | "failed" | "truncated"

class RoundResult(BaseModel):
    round_number: int
    plan_step: PlanStep
    script_id: str          # MinIO object key for sₖ
    stdout: str             # Capped at 10 KB
    stderr: str             # Capped at 2 KB
    exit_code: int
    verifier_verdict: str   # "Yes" | "No"
    router_decision: str    # "add_step" | int (backtrack index)
    debug_attempts: int

class DSStarState(BaseModel):
    # Immutable task context
    task_id: str
    query: str
    formatting_instruction: str
    data_descriptions: str          # D — Analyzer output
    file_paths: list[str]           # Absolute paths inside container
    steering_hints: list[str]       # Accumulated mid-analysis hints
    
    # Mutable execution state
    plan: list[PlanStep]            # Grows each round; may be truncated by Router
    rounds: list[RoundResult]       # Full history of all rounds
    current_round: int              # 0-indexed
    max_rounds: int                 # Default 6; extended by analyst in +5 increments
    hard_cap: int                   # Always 40; never changeable
    status: str                     # "running" | "paused" | "complete" | "failed" | "stopped"
    
    # Output
    final_result: str | None        # Finalizer output (narrative + chart JSON + table JSON)
    result_complete: bool           # True only if Verifier returned "Yes" before cap
```

### 4.3 DS-STAR Graph Definition

```
Nodes:
  analyzer      → Profiles files, produces D
  planner       → Generates plan step pₖ
  coder         → Generates complete script sₖ
  executor      → Runs sₖ via docker exec; captures stdout/stderr/exit_code
  debugger      → Activated only on exit_code != 0; max 3 attempts
  verifier      → LLM judge: "Yes" / "No"
  router        → "add_step" or backtrack index l
  finalizer     → Formats final result; runs formatting script in sandbox

Edges (conditional):
  START         → analyzer
  analyzer      → planner
  planner       → coder
  coder         → executor
  executor      → debugger          (if exit_code != 0)
  executor      → verifier          (if exit_code == 0)
  debugger      → executor          (if debug_attempts < 3)
  debugger      → verifier          (if debug_attempts == 3, best-effort)
  verifier      → finalizer         (if verdict == "Yes" OR current_round == hard_cap)
  verifier      → router            (if verdict == "No" AND current_round < hard_cap)
  verifier      → PAUSE_NODE        (if status == "paused")
  router        → planner           (if decision == "add_step")
  router        → planner           (if decision == int l; plan truncated to p₀..pₗ₋₁)
  finalizer     → END
```

### 4.4 Round Budget Logic

```python
def should_continue(state: DSStarState) -> str:
    if state.status == "paused":
        return "pause"
    if state.status == "stopped":
        return "end"
    if state.current_round >= state.hard_cap:
        return "finalizer"          # best-effort, incomplete result
    if state.current_round >= state.max_rounds:
        # Emit WS event: "round_cap_reached"
        # Analyst must click "Extend" to bump max_rounds += 5
        return "await_extension"    # suspends graph at LangGraph interrupt
    return "continue"
```

**Round extension mechanism:** LangGraph's `interrupt()` primitive suspends the graph. The API server's `POST /api/v1/tasks/{id}/extend` increments `state.max_rounds += 5` and calls `graph.update_state()`, resuming execution. This avoids spinning up a new graph instance.

### 4.5 DS-STAR+ Graph Definition

```
Nodes:
  analyzer              → Same as DS-STAR; D shared across all sub-questions
  subquestion_generator → Decomposes query into {sq₁..sqₙ}; refinement mode receives current R
  inner_dsstar          → Runs dsstar_graph for each sqᵢ sequentially; yields (sqᵢ, aᵢ, sᵢ)
  report_writer         → Synthesises cited report R from evidence set
  generator_refinement  → Generator re-runs with (q, D, R); identifies gaps; returns new sub-questions or []
  finalizer             → Formats and packages final report

Edges:
  START                 → analyzer
  analyzer              → subquestion_generator
  subquestion_generator → inner_dsstar
  inner_dsstar          → report_writer         (after all sqᵢ complete)
  report_writer         → generator_refinement
  generator_refinement  → inner_dsstar          (if new sub-questions exist AND k < K_max)
  generator_refinement  → finalizer             (if no new sub-questions OR k == K_max)
  finalizer             → END
```

**K_max (refinement rounds):** Default K=1 per paper experiments. Exposed as admin-configurable parameter. Early stop: if Generator returns empty list, refinement terminates.

### 4.6 Checkpoint Recovery

LangGraph checkpoints after every node. On worker crash:

1. Celery's task retry mechanism detects the dead worker (heartbeat timeout: 60 s).
2. Task is re-queued at **high priority** (ahead of new submissions).
3. New worker picks up the task; calls `graph.get_state(thread_id=task_id)` to find last checkpoint.
4. Graph resumes from the last completed node — no rounds are replayed.
5. WS event `checkpoint_recovery` is emitted to the frontend: "Recovered from checkpoint at Round N."

---

## 5. Agent Specifications

All agents share a common interface:

```python
class AgentResponse(BaseModel):
    content: str
    tokens_used: int
    latency_ms: int
    model_id: str

class BaseAgent:
    def __init__(self, llm_adapter: LLMAdapter, system_prompt: str): ...
    async def invoke(self, user_message: str) -> AgentResponse: ...
```

All prompts are stored in `backend/agents/prompts/` as `.jinja2` template files — **never hardcoded in agent logic**. This allows prompt iteration without code changes.

---

### 5.1 Analyzer

**Purpose:** Profile every data file and produce `D` — a natural language description per file that is passed as fixed context to all subsequent agents.

**Trigger:** Once per DS-STAR task (before any planning). In DS-STAR+, `D` is shared across all sub-questions.

**Mechanism:** The Analyzer generates a Python profiling script, runs it in the Docker sandbox, and parses the output. It does not call the LLM to describe the data — it runs code.

**Profiling script covers:**

| File type | Extracted metadata |
|-----------|-------------------|
| CSV | Delimiter detected, shape (rows × cols), column names, dtypes, null rates, min/max/mean for numerics, sample 3 rows |
| Excel | All sheet names and shapes, column names per sheet, sample rows per sheet |
| JSON | Root structure (array / object / nested), key paths, value types, sample values |
| PDF | Page count, extracted text (first 2000 chars), detected tables |
| Word (.docx) | Paragraph count, extracted text (first 2000 chars), table count and structure |

**CBUAE schema recognition:** After generic profiling, the Analyzer checks for known CBUAE schema signatures:

```python
CBUAE_SCHEMAS = {
    "fraud_loss_report": {
        "required_columns": ["lfi_id", "fraud_type", "channel", "amount_aed"],
        "description": "LFI fraud loss return. Contains reported fraud losses by institution, fraud typology, and delivery channel."
    },
    "sar_str_records": {
        "required_columns": ["lfi_id", "typology", "filing_date", "amount"],
        "description": "SAR/STR filing records. Contains suspicious activity reports filed by LFIs."
    },
    "kyc_cdd_data": {
        "required_columns": ["customer_id", "risk_band", "review_date"],
        "description": "KYC/CDD records. Contains customer risk classification and review status."
    },
    "consumer_complaints": {
        "required_columns": ["lfi_id", "complaint_category", "product_type", "resolution_status"],
        "description": "Consumer complaint register. Contains complaints filed against LFIs by category and product."
    }
}
```

If a file matches a known schema, `D` includes the enriched description. Unrecognised files receive generic profiling only.

**Output format (`D`):**

```
FILE 1: fraud_q1_2025.csv
Type: CSV | Schema: fraud_loss_report
Shape: 12,847 rows × 9 columns
Columns: lfi_id (str), fraud_type (str, values: card_fraud/APP_fraud/social_engineering/identity_theft),
         channel (str, values: online/ATM/branch/mobile), reporting_quarter (str),
         total_loss_aed (float), recovered_amount_aed (float), detection_method (str),
         report_date (date), lfi_name (str)
Null rates: recovered_amount_aed: 12.3%, detection_method: 4.1%; all others: 0%
Sample rows: [row 1], [row 2], [row 3]
Description: LFI fraud loss return covering Q1 2025. Contains 47 distinct LFIs.
             Total reported loss AED 892M. Dominant fraud type: card_fraud (38%).

FILE 2: ...
```

**Stored in PostgreSQL** (`file_metadata.analyzer_description`) at upload time (not just at query time), enabling dataset semantic search (FR-QI-06).

---

### 5.2 Query Clarity Agent

**Purpose:** CBUAE addition. Runs before the Planner. Validates the query, maps business terms to data terms, classifies mode (A vs B), and flags ambiguity.

**Input:** `(query, D, department)`

**Output:**
```python
class ClarityResult(BaseModel):
    mode: str                   # "insight" | "research" | "ambiguous"
    mapped_query: str           # Query with domain terms resolved
    domain_mappings: list[str]  # e.g. ["'high-risk customers' → risk_band = 'High'"]
    ambiguity_reason: str | None
    answerable: bool
    not_answerable_reason: str | None
```

**Routing rules:**
- Single specific question with named entities → `"insight"`
- Open-ended, thematic, "generate a report", "analyse across" → `"research"`
- Both interpretations plausible → `"ambiguous"` (triggers modal on frontend)
- Query references data not present in `D` → `answerable = False` (inline warning shown)

**Domain term mappings (V1 — Fraud Prevention focus):**

| Business term | Mapped to |
|--------------|-----------|
| "high-risk LFIs" | LFIs in top quartile by fraud_loss_rate |
| "peer median" | Median of same LFI category (bank / exchange house / finance company) |
| "fraud rate" / "fraud loss rate" | total_loss_aed / total_transaction_volume_aed |
| "detection rate" | (fraud_cases_detected / total_fraud_cases) × 100 |
| "APP fraud" | fraud_type = 'APP_fraud' |
| "card fraud" | fraud_type = 'card_fraud' |
| "social engineering" | fraud_type = 'social_engineering' |
| "this quarter" | reporting_quarter matching current calendar quarter |

---

### 5.3 Planner

**Purpose:** Generates exactly one new plan step `pₖ` per round.

**Input (round 0):** `(q_mapped, D, steering_hints)`  
**Input (round k):** `(q_mapped, D, p₀..pₖ₋₁, rₖ₋₁, steering_hints)`

**Constraint:** One step only. The step must be concrete and unambiguous enough for the Coder to translate directly into Python without further clarification.

**System prompt principles (from prompt template):**
- Start with the simplest possible step (e.g., "Load the fraud loss CSV and confirm the column names match what the Analyzer described")
- Each step builds on the confirmed result of the previous step — do not assume prior steps succeeded unless `rₖ₋₁` confirms it
- Steps are analytical, not coding instructions — the Coder decides how to implement them
- Steering hints override plan direction — if a hint says "focus on card fraud only", all subsequent steps should scope to card fraud

**Output:** Plain English, 1–3 sentences. Example:
> "Compute the fraud loss rate (total_loss_aed / total_transaction_volume_aed) for each LFI and identify the top 5 by this metric. Confirm that the result aligns with the channel breakdown from round 2."

---

### 5.4 Coder

**Purpose:** Translates the cumulative plan `{p₀..pₖ}` into a single executable Python script `sₖ`.

**Input (round 0):** `(q_mapped, D, p₀)`  
**Input (round k):** `(q_mapped, D, p₀..pₖ, sₖ₋₁)` — receives prior script as base

**Key implementation detail (from Q3/Q14):** The Coder extends `sₖ₋₁` with the new step — it does not rewrite from scratch. The output `sₖ` is still a complete, executable script (the entire prior script plus the new step's code appended). After a Router backtrack, `sₖ₋₁` is NOT passed — Coder works from the truncated plan only.

**System prompt constraints (enforced via template):**
```
- Use absolute file paths from the data_descriptions (never relative paths)
- Use pandas for structured data; always use chunksize for files > 100 MB
- Always print summaries, not full DataFrames (head(20) maximum)
- For large outputs (> 100 rows), write to /tmp/<descriptive_filename>.<ext> and print a confirmation
- Never use pip install — all libraries are pre-installed
- Try multiple CSV delimiters if the first parse fails (comma → semicolon → tab → pipe)
- For charts: output a JSON object with keys: type, title, x_label, y_label, data
  (the frontend's Recharts renders from this JSON — never use matplotlib or plotly)
- For Excel output: use openpyxl; write to /tmp/<filename>.xlsx
- Wrap all code in try/except; print informative error messages before raising
```

**Pre-installed libraries in sandbox:** `pandas`, `numpy`, `openpyxl`, `python-docx`, `PyPDF2`, `pdfplumber`, `beautifulsoup4`, `scipy`, `scikit-learn` (inference only, no training), `tabulate`, `jinja2`

**Script archive:** Every `sₖ` is stored in MinIO at `scripts/{task_id}/round_{k}.py`. Referenced by the audit log via `script_id`. The analyst can download any version from the result panel.

---

### 5.5 Executor

**Purpose:** Runs `sₖ` inside the task's Docker container. Captures stdout, stderr, and exit code.

**Mechanism:**
```python
async def execute_round(task_id: str, script: str, round_number: int) -> ExecutionResult:
    container = container_registry.get(task_id)  # Pre-started container
    
    # Write script to container filesystem
    script_path = f"/workspace/round_{round_number}.py"
    await container.put_archive("/workspace", tar_with(script, script_path))
    
    # Execute with timeout
    result = await container.exec_run(
        cmd=["python", script_path],
        timeout=EXECUTION_TIMEOUT_SECONDS,   # Default: 120s; configurable
        user="sandbox",
        workdir="/workspace"
    )
    
    # Cap outputs
    stdout = result.output[:10_240]   # 10 KB hard cap
    stderr = result.stderr[:2_048]    # 2 KB cap
    
    return ExecutionResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr,
        files_written=await list_tmp_files(container)  # Discover /tmp output files
    )
```

**File output handling:** After each round, the Executor scans `/tmp` for new files and copies them to MinIO at `outputs/{task_id}/round_{k}/`. The Finalizer retrieves these for report assembly.

---

### 5.6 Debugger

**Purpose:** Activated when `exit_code != 0`. Repairs `sₖ` without creating a new plan step. Maximum 3 attempts per round.

**Two-step design (confirmed from Q15, paper Listings 55+56/57):**

**Step 1 — Traceback Summariser (separate LLM call):**
```
Input:  (raw_stderr, raw_traceback)
Output: summarised_traceback (structured: error type, failing line, likely cause)
Purpose: Raw tracebacks can be thousands of lines (e.g., pandas stack traces).
         Summarising before the fixer prevents context overflow.
```

**Step 2 — Code Fixer (separate LLM call):**
```
Input:  (sₖ, summarised_traceback, D)
Output: sₖ_fixed
Constraint: Only fix what's broken. Do not change correct logic above the failing line.
            Use D to resolve semantic errors (wrong column names, wrong sheet names, etc.)
```

**Circuit breaker (from Q7):** If the same script fails with identical error type for 2 consecutive rounds (even after Router backtracking), the task is marked `FAILED` and sent to DLQ. This prevents infinite loop on structurally unanswerable queries.

---

### 5.7 Verifier

**Purpose:** LLM-as-judge. Determines whether `rₖ` sufficiently answers `q`.

**Input:** `(q_mapped, p₀..pₖ, sₖ, rₖ)` — full 4-tuple per paper (Q9)

**Output:** `"Yes"` or `"No"` — parsed exactly as strings (from Q18, paper Listing 52)

**System prompt framing (key instruction):**
> "You are evaluating whether the execution result answers the analyst's question. Output only 'Yes' or 'No'. Output 'Yes' only if the result DIRECTLY answers the question with specific data. Output 'No' if the result is an error, is a progress step (not a final answer), or leaves the core question unanswered."

**Routing on verdict:**
- `"Yes"` → Finalizer
- `"No"` AND `current_round < hard_cap` → Router
- `"No"` AND `current_round == hard_cap` → Finalizer (incomplete result)

---

### 5.8 Router

**Purpose:** Decides whether to add a step or backtrack to a prior step.

**Input:** `(q_mapped, D, p₀..pₖ, rₖ)`

**Output:** Either `"add_step"` or an integer `l ∈ {1,...,k}` (backtrack index)

**Decision semantics:**
- `"add_step"`: The plan direction is correct but incomplete — continue forward
- Integer `l`: Step `pₗ` was erroneous — truncate plan to `{p₀..pₗ₋₁}` and have Planner regenerate `pₗ`

**On backtrack:** `state.plan` is sliced to `plan[:l]`. All truncated steps are marked `"truncated"` in the audit log (not deleted). The Planner regenerates from the truncated plan. The Coder does NOT receive `sₖ₋₁` after a backtrack — it works from the truncated plan only (from Q6).

---

### 5.9 Finalizer

**Purpose:** Formats the final result. Generates and runs a formatting script in the Docker sandbox (from Q16 — not text-only).

**Input:** `(sₖ, rₖ, formatting_instruction, files_written)`

**Output:** Structured JSON:
```json
{
  "narrative": "ABC Bank has the highest card fraud loss rate...",
  "charts": [
    {
      "type": "bar",
      "title": "Card Fraud Loss Rate by LFI (Q1 2025)",
      "x_label": "LFI",
      "y_label": "Loss Rate (%)",
      "data": [{"name": "ABC Bank", "value": 0.18}, ...]
    }
  ],
  "tables": [
    {
      "title": "Top 5 LFIs by Card Fraud Loss Rate",
      "headers": ["LFI", "Loss Rate", "vs Peer Median", "Primary Fraud Type"],
      "rows": [["ABC Bank", "0.18%", "+3.2×", "Social Engineering"], ...]
    }
  ],
  "files": ["fraud_analysis_abc.xlsx"],
  "is_complete": true,
  "incomplete_summary": null
}
```

**Explainer layer (CBUAE addition):** After the Finalizer, a separate Explainer agent converts technical output into plain English for non-technical analysts. Example:
> "ABC Bank's card fraud loss rate is 0.18% of transaction volume — 3.2× the peer median of 0.056%. The dominant fraud type is social engineering (61%), concentrated in the mobile banking channel (78% of losses)."

The Explainer output is displayed as the first paragraph of the result. The full Finalizer output (tables, charts) follows.

---

### 5.10 Sub-Question Generator (DS-STAR+ only)

**Purpose:** Decomposes open-ended query into focused, answerable sub-questions. Also runs in refinement mode to identify gaps.

**Initial mode input:** `(q_open, D)`  
**Refinement mode input:** `(q_open, D, R_current)` — receives current report

**Output:**
```python
class SubQuestionSet(BaseModel):
    sub_questions: list[str]    # Specific, answerable, non-overlapping
    rationale: str              # Why these sub-questions cover the open query
    mode: str                   # "initial" | "refinement"
```

**Refinement termination:** If `len(sub_questions) == 0` in refinement mode, the Generator signals early stop. This takes precedence over `K_max`.

---

### 5.11 Report Writer (DS-STAR+ only)

**Purpose:** Synthesises a cited, structured report from the evidence set `{(sqᵢ, aᵢ, sᵢ)}`.

**Input:** `(q_open, evidence_set, R_prior)` — `R_prior` is `None` on first pass; the partial report on refinement passes

**Output:** Markdown document with fixed structure (from Q13):
```
# [Report Title]
**Date:** | **Analyst:** | **Classification:** INTERNAL

## Executive Summary
...inline citations: (Sub-question 2: Card fraud by LFI)...

## Query & Scope
...

## Methodology
...

## [Dynamic Findings Sections — Writer decides]
...inline citations throughout...

## Recommendations
...
```

**Citation format:** `(Source: Sub-question N — [sub-question text])`. The frontend renders these as expandable links that show the sub-question, the script `sᵢ`, and the raw output `aᵢ`.

**LLM used:** The highest-quality available model in the provider adapter (configured separately from the Flash-tier agents). In development: Gemini 2.5 Pro. In production: largest available local model.

---

## 6. Docker Sandbox

### 6.1 Container Lifecycle

```
Task submitted → Container created → Rounds execute via docker exec → Task ends → Container destroyed

Per-task: 1 container
Per-round: docker exec (no container restart)
DS-STAR+: 1 container per sub-question (sub-questions don't share state)
```

### 6.2 Container Specification

```dockerfile
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 sandbox
USER sandbox
WORKDIR /workspace

# Pre-install all permitted libraries (no pip at runtime)
RUN pip install --no-cache-dir \
    pandas==2.2.* numpy==1.26.* openpyxl==3.1.* \
    python-docx==1.1.* PyPDF2==3.* pdfplumber==0.11.* \
    scipy==1.13.* scikit-learn==1.5.* tabulate==0.9.* \
    jinja2==3.1.*

# No network tools, no curl, no wget, no git
```

### 6.3 Security Constraints

```python
CONTAINER_CONFIG = {
    "network_mode": "none",               # No network access
    "mem_limit": "2g",                    # 2 GB RAM cap
    "memswap_limit": "2g",               # No swap
    "cpu_quota": 50000,                   # 50% of 1 CPU core max
    "read_only": False,                   # Needs /tmp for output files
    "volumes": {
        DATA_MOUNT_PATH: {
            "bind": "/data",
            "mode": "ro"                  # Data is read-only
        }
    },
    "security_opt": ["no-new-privileges", "seccomp=/etc/docker/sandbox-seccomp.json"],
    "cap_drop": ["ALL"],                  # Drop all Linux capabilities
    "user": "1000:1000",                  # Non-root (sandbox user)
    "pids_limit": 50,                     # Prevent fork bombs
}
```

**Seccomp profile:** Custom allowlist blocking `socket`, `connect`, `bind`, `listen`, `ptrace`, `mount`, `clone` with `CLONE_NEWNET`. See `backend/sandbox/seccomp.json`.

### 6.4 Execution Timeout

Per-round execution timeout: **120 seconds** (configurable via `SANDBOX_EXEC_TIMEOUT_SECONDS`). If exceeded: process killed, `exit_code = 124` (timeout), stderr set to `"Execution timed out after 120 seconds."`. This round is treated identically to any other non-zero exit code — Debugger attempts to fix the script (likely by adding chunked reading or reducing data size).

### 6.5 Container Manager

```python
class SandboxManager:
    """Manages per-task Docker containers. Thread-safe."""
    
    async def start(self, task_id: str, data_paths: list[str]) -> str:
        """Start container for task. Returns container_id."""
    
    async def execute(self, task_id: str, script: str, timeout: int) -> ExecutionResult:
        """Run script via docker exec. Returns stdout, stderr, exit_code."""
    
    async def copy_outputs(self, task_id: str, round_number: int) -> list[str]:
        """Copy /tmp/* from container to MinIO. Returns MinIO keys."""
    
    async def stop(self, task_id: str) -> None:
        """Stop and remove container. Called on task complete/failed/stopped."""
    
    async def cleanup_orphans(self) -> None:
        """Called on worker startup. Removes containers from crashed prior workers."""
```

---

## 7. LLM Provider Adapter

### 7.1 Interface

```python
from abc import ABC, abstractmethod

class LLMAdapter(ABC):
    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse: ...

class LLMResponse(BaseModel):
    content: str
    model_id: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
```

### 7.2 Implementations

**OllamaAdapter (production — air-gapped):**
```python
class OllamaAdapter(LLMAdapter):
    base_url: str   # e.g. "http://ollama-server:11434"
    model: str      # e.g. "llama3.2:70b" or "llama3.1:8b"
    # Calls POST /api/chat; handles streaming internally; returns complete response
```

**GeminiAdapter (development only — requires network):**
```python
class GeminiAdapter(LLMAdapter):
    api_key: str    # From Vault; never env variable
    model: str      # e.g. "gemini-2.5-flash"
    # Uses google-generativeai SDK
```

**AzureOpenAIAdapter (fallback if local GPU insufficient — OQ-7 dependent):**
```python
class AzureOpenAIAdapter(LLMAdapter):
    endpoint: str   # Azure OpenAI UAE North endpoint
    api_key: str    # From Vault
    deployment: str # e.g. "gpt-4o"
```

### 7.3 Configuration

`backend/config/llm.yaml` (loaded at startup; values fetched from Vault):
```yaml
provider: ollama                # "ollama" | "gemini" | "azure_openai"

models:
  flash: llama3.2:11b           # 7 of 8 agents: fast, sufficient
  pro: llama3.1:70b             # Report Writer: highest quality available
  # For gemini provider: "gemini-2.5-flash" and "gemini-2.5-pro"

ollama:
  base_url: "http://ollama-01:11434"
  request_timeout: 300

# Agent → model tier mapping (all others use "flash")
model_assignments:
  report_writer: pro
  # All other agents use flash tier
```

**Zero agent code changes required** when switching `provider`. The adapter is injected via dependency injection; agents receive an `LLMAdapter` instance.

---

## 8. Database Schema

**Engine:** PostgreSQL 16. All tables use `UUID` primary keys. Timestamps are `TIMESTAMPTZ` (UTC). No soft-deletes — records are immutable once created (append-only audit design).

### 8.1 Schema: Users & RBAC

```sql
CREATE TABLE departments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,  -- 'fraud_prevention' | 'aml_cft' | 'market_conduct' | 'enforcement' | 'policy_research'
    display_name TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    department_id   UUID NOT NULL REFERENCES departments(id),
    role            TEXT NOT NULL CHECK (role IN ('analyst', 'admin')),
    password_hash   TEXT NOT NULL,       -- bcrypt; [PENDING OQ-1: replace with SSO token if AD/SSO]
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_department ON users(department_id);
```

### 8.2 Schema: Files & Datasets

```sql
CREATE TABLE datasets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id       UUID REFERENCES users(id),      -- NULL for institutional datasets
    file_name           TEXT NOT NULL,
    file_size_bytes     BIGINT NOT NULL,
    file_type           TEXT NOT NULL,                  -- 'csv' | 'xlsx' | 'json' | 'pdf' | 'docx'
    storage_key         TEXT NOT NULL UNIQUE,           -- MinIO object key
    analyzer_description TEXT,                          -- D for this file; set after profiling
    schema_type         TEXT,                           -- CBUAE schema name if recognised
    is_institutional    BOOLEAN NOT NULL DEFAULT FALSE,
    status              TEXT NOT NULL DEFAULT 'uploading',  -- 'uploading' | 'profiling' | 'ready' | 'archived' | 'deleted'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ,                    -- NULL for institutional; 90 days for personal
    CONSTRAINT chk_owner CHECK (
        (is_institutional = TRUE AND owner_user_id IS NULL) OR
        (is_institutional = FALSE AND owner_user_id IS NOT NULL)
    )
);

CREATE TABLE dataset_department_access (
    dataset_id      UUID NOT NULL REFERENCES datasets(id),
    department_id   UUID NOT NULL REFERENCES departments(id),
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by      UUID NOT NULL REFERENCES users(id),
    PRIMARY KEY (dataset_id, department_id)
);

-- Full-text search index for dataset suggestion (FR-QI-06)
CREATE INDEX idx_datasets_fts ON datasets USING gin(to_tsvector('english', coalesce(analyzer_description, '') || ' ' || file_name));
```

### 8.3 Schema: Tasks

```sql
CREATE TABLE tasks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id),
    department_id       UUID NOT NULL REFERENCES departments(id),
    query               TEXT NOT NULL,
    mapped_query        TEXT,                           -- After Query Clarity Agent
    formatting_instruction TEXT,
    mode                TEXT NOT NULL CHECK (mode IN ('insight', 'research')),
    status              TEXT NOT NULL DEFAULT 'queued', -- 'queued' | 'running' | 'paused' | 'complete' | 'failed' | 'stopped' | 'incomplete'
    current_round       INT NOT NULL DEFAULT 0,
    max_rounds          INT NOT NULL DEFAULT 6,
    hard_cap            INT NOT NULL DEFAULT 40,
    is_result_complete  BOOLEAN,                        -- NULL until Verifier decides
    result_storage_key  TEXT,                           -- MinIO key for final result JSON
    celery_task_id      TEXT,                           -- For cancellation
    error_summary       TEXT,                           -- For failed tasks
    queued_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    paused_at           TIMESTAMPTZ,
    checkpoint_expires_at TIMESTAMPTZ                   -- 7 days after pause
);

CREATE TABLE task_datasets (
    task_id     UUID NOT NULL REFERENCES tasks(id),
    dataset_id  UUID NOT NULL REFERENCES datasets(id),
    snapshot_id UUID NOT NULL REFERENCES data_snapshots(id),
    PRIMARY KEY (task_id, dataset_id)
);

CREATE TABLE task_steering_hints (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID NOT NULL REFERENCES tasks(id),
    hint_text   TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_from_round INT             -- NULL until hint is consumed
);

CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_queued_at ON tasks(queued_at);
```

### 8.4 Schema: Audit Log

```sql
-- Append-only. Application DB user has INSERT only on this table.
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,   -- Sequential for chain integrity
    entry_hash      TEXT NOT NULL,           -- SHA-256(prev_hash || entry_data)
    prev_hash       TEXT NOT NULL,           -- Hash of prior record; genesis record uses '0'×64
    event_type      TEXT NOT NULL,           -- See event type registry below
    task_id         UUID REFERENCES tasks(id),
    user_id         UUID REFERENCES users(id),
    department_id   UUID REFERENCES departments(id),
    payload         JSONB NOT NULL,          -- Event-specific data
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- No UPDATE, no DELETE granted to application role:
-- GRANT INSERT, SELECT ON audit_log TO fip_app;
-- (enforced at PostgreSQL role level, not just application level)

CREATE INDEX idx_audit_log_task ON audit_log(task_id);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_event ON audit_log(event_type);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);
```

**Audit event type registry:**

| Event type | Trigger | Key payload fields |
|-----------|---------|-------------------|
| `task.created` | Query submitted | task_id, query, mode, dataset_ids |
| `task.mode_selected` | Analyst picks from ambiguity modal | task_id, mode, was_ambiguous |
| `task.started` | Worker picks up task | task_id, celery_task_id |
| `round.completed` | Each round finishes | task_id, round_number, plan_step, script_id, verifier_verdict, router_decision |
| `round.debug_attempt` | Debugger runs | task_id, round_number, attempt_number, error_type |
| `task.paused` | Analyst pauses | task_id, round_number |
| `task.resumed` | Analyst resumes | task_id, resumed_from_round |
| `task.extended` | Analyst extends rounds | task_id, new_max_rounds |
| `hint.submitted` | Steering hint submitted | task_id, hint_text |
| `task.stopped` | Analyst stops | task_id, round_number |
| `task.completed` | Final result delivered | task_id, is_complete, snapshot_ids |
| `task.failed` | Unrecoverable failure | task_id, error_summary |
| `result.exported` | Export downloaded | task_id, format, user_id |
| `result.reformatted` | Reformat triggered | task_id, new_instruction |
| `result.feedback` | Thumbs up/down | task_id, rating, comment |
| `result.flagged` | Flag as incorrect | task_id, description |
| `audit.queried` | Admin queries audit log | querying_user_id, filters_applied |
| `file.uploaded` | File upload completes | dataset_id, file_name, file_size |
| `file.profiled` | Analyzer completes profiling | dataset_id, schema_type_detected |
| `session.login` | Successful login | user_id |
| `session.logout` | Logout or token expiry | user_id |

### 8.5 Schema: Data Snapshots

```sql
CREATE TABLE data_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      UUID NOT NULL REFERENCES datasets(id),
    snapshot_key    TEXT NOT NULL UNIQUE,   -- MinIO key for snapshot copy
    row_count       BIGINT,
    file_hash       TEXT NOT NULL,          -- SHA-256 of file content
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 8.6 Schema: Admin & Config

```sql
CREATE TABLE query_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    template_text   TEXT NOT NULL,
    department_id   UUID REFERENCES departments(id),  -- NULL = visible to all
    created_by      UUID NOT NULL REFERENCES users(id),
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE report_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    storage_key     TEXT NOT NULL,   -- MinIO key for .docx template
    created_by      UUID NOT NULL REFERENCES users(id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE report_template_departments (
    template_id     UUID NOT NULL REFERENCES report_templates(id),
    department_id   UUID NOT NULL REFERENCES departments(id),
    PRIMARY KEY (template_id, department_id)
);

CREATE TABLE system_config (
    key     TEXT PRIMARY KEY,   -- e.g. 'file_upload_enabled', 'max_concurrent_insight_tasks'
    value   TEXT NOT NULL,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed default config
INSERT INTO system_config VALUES 
    ('file_upload_enabled', 'true', NULL, now()),
    ('max_concurrent_insight_tasks', '5', NULL, now()),
    ('max_concurrent_research_tasks', '3', NULL, now()),
    ('max_concurrent_containers', '8', NULL, now());
```

---

## 9. File Storage

**Engine:** MinIO (S3-compatible, on-premise). All objects are encrypted at rest (AES-256, MinIO SSE-S3).

**Bucket layout:**

```
fip-uploads/
  {user_id}/{dataset_id}/{filename}                    — Uploaded files (original)

fip-snapshots/
  {dataset_id}/{snapshot_id}/{filename}                — Point-in-time data snapshots

fip-scripts/
  {task_id}/round_{k}.py                               — All code versions per task

fip-outputs/
  {task_id}/round_{k}/{filename}                       — Files written to /tmp by Coder
  {task_id}/final/{filename}                           — Finalizer output files

fip-reports/
  {task_id}/FIP_{date}_{slug}.docx                     — Generated Word reports
  {task_id}/FIP_{date}_{slug}.pdf                      — Generated PDF reports
  {task_id}/FIP_{date}_{slug}.xlsx                     — Generated Excel reports

fip-templates/
  report-templates/{template_id}.docx                  — Admin-uploaded report templates
```

**Access pattern:** All MinIO access goes through the backend API. No pre-signed URLs exposed to the browser. The browser downloads files via `GET /api/v1/tasks/{id}/export/{format}` which streams from MinIO through the API server.

---

## 10. Task Queue

### 10.1 Celery Configuration

```python
CELERY_CONFIG = {
    "broker_url": "redis+sentinel://sentinel1:26379,sentinel2:26379,sentinel3:26379/0?master_name=fip-master",
    "result_backend": "redis+sentinel://...",
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "task_track_started": True,
    "task_acks_late": True,           # Task only ACKed after completion — survives worker crash
    "task_reject_on_worker_lost": True,
    "worker_prefetch_multiplier": 1,  # One task per worker at a time
    "task_soft_time_limit": 3900,     # 65 min soft limit (WS notification)
    "task_time_limit": 4200,          # 70 min hard limit (SIGKILL)
}
```

### 10.2 Priority Queue

```python
# Two queues: high priority for Insight, lower for Research
CELERY_TASK_ROUTES = {
    "workers.tasks.run_insight_task": {"queue": "insight"},
    "workers.tasks.run_research_task": {"queue": "research"},
}

# Worker startup: drain insight queue preferentially
# celery -A backend.celery worker -Q insight,research --concurrency=8
```

### 10.3 Concurrency Budget Enforcement

```python
class ConcurrencyBudget:
    """Redis-backed semaphore enforcing global task limits."""
    
    MAX_INSIGHT = 5
    MAX_RESEARCH = 3
    MAX_CONTAINERS = 8
    
    async def acquire(self, mode: str) -> bool:
        """Attempt to reserve a slot. Returns False if at capacity."""
    
    async def release(self, mode: str) -> None:
        """Release slot on task completion."""
    
    async def get_queue_position(self, task_id: str) -> int:
        """FIFO position in the waiting queue."""
```

When at capacity, tasks are queued (not rejected). Queue position and estimated wait are pushed to the analyst via WebSocket.

### 10.4 Dead-Letter Queue

```python
# DLQ Celery queue for permanently failed tasks
@celery.task(bind=True, max_retries=2, default_retry_delay=30)
def run_insight_task(self, task_id: str):
    try:
        run_dsstar(task_id)
    except Exception as exc:
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            move_to_dlq(task_id, str(exc))
            notify_admin_dlq(task_id)
```

DLQ items appear in the admin health dashboard (FR-ADMIN-05) with task ID, error summary, and timestamp. Admin can trigger manual retry.

---

## 11. REST API

**Base URL:** `/api/v1`  
**Auth:** All endpoints except `/auth/*` require `Authorization: Bearer <JWT>`.  
**Content-Type:** `application/json` unless noted.

### 11.1 Authentication

```
POST   /api/v1/auth/login
       Body: { "email": str, "password": str }
       Returns: { "access_token": str, "expires_in": 28800, "user": UserDTO }

POST   /api/v1/auth/logout
       Invalidates token (server-side token blocklist in Redis)

GET    /api/v1/auth/me
       Returns current user profile and department
```

### 11.2 Tasks (Core)

```
POST   /api/v1/tasks
       Body: {
         "query": str,                    # max 5000 chars
         "formatting_instruction": str,   # optional, max 500 chars
         "dataset_ids": [str],            # UUIDs confirmed by analyst
         "mode_override": str | null      # optional; normally set by Query Clarity Agent
       }
       Returns: { "task_id": str, "status": "queued", "queue_position": int }

GET    /api/v1/tasks/{id}
       Returns: TaskDetailDTO (full state: rounds, plan, status, result if complete)

GET    /api/v1/tasks
       Query params: status, mode, page, page_size (default 20)
       Returns: paginated list of analyst's own tasks

POST   /api/v1/tasks/{id}/pause
       Suspends at end of current round.
       Returns: { "status": "pause_requested" }

POST   /api/v1/tasks/{id}/resume
       Resumes from checkpoint.
       Returns: { "status": "queued", "resume_from_round": int }

POST   /api/v1/tasks/{id}/stop
       Immediate cancellation.
       Returns: { "status": "stopped" }

POST   /api/v1/tasks/{id}/extend
       Adds 5 rounds to max_rounds.
       Returns: { "new_max_rounds": int }

POST   /api/v1/tasks/{id}/hints
       Body: { "hint_text": str }
       Returns: { "hint_id": str, "applies_from_round": int }

POST   /api/v1/tasks/{id}/reformat
       Body: { "formatting_instruction": str }
       Returns: { "task_id": str, "status": "reformatting" }
       (Only re-runs Finalizer; other agents do not re-run)
```

### 11.3 Datasets

```
POST   /api/v1/datasets
       Content-Type: multipart/form-data
       Body: file(s) + optional { "keep_after_task": bool }
       Returns: [{ "dataset_id": str, "status": "profiling" }]
       (Analyzer profiling runs async; status → "ready" when complete)

GET    /api/v1/datasets
       Query params: status (default "ready"), search (keyword for FTS)
       Returns: paginated list of analyst's accessible datasets (personal + department institutional)

GET    /api/v1/datasets/suggest
       Query params: query (the analyst's query text)
       Returns: top 5–8 datasets ranked by relevance (PostgreSQL FTS)

DELETE /api/v1/datasets/{id}
       Soft-delete (status = "deleted"); physical deletion async.
       Returns: 204

GET    /api/v1/datasets/{id}/metadata
       Returns dataset detail including analyzer_description
```

### 11.4 Exports

```
GET    /api/v1/tasks/{id}/export/docx
GET    /api/v1/tasks/{id}/export/pdf
GET    /api/v1/tasks/{id}/export/xlsx
       Content-Type: application/octet-stream
       Content-Disposition: attachment; filename="FIP_{date}_{slug}.{ext}"
       Streams file from MinIO through API server.
       Audit log event: result.exported
```

### 11.5 Admin

```
GET    /api/v1/admin/users
POST   /api/v1/admin/users
PATCH  /api/v1/admin/users/{id}          # deactivate, change dept
GET    /api/v1/admin/audit-log           # Query params: user_id, dept, date_from, date_to, event_type, query_text, page
GET    /api/v1/admin/audit-log/export    # Returns CSV
GET    /api/v1/admin/health              # Real-time: queue depth, active tasks, GPU util, error rate, DLQ count
GET    /api/v1/admin/dlq                 # List DLQ items
POST   /api/v1/admin/dlq/{id}/retry     # Manual retry
GET    /api/v1/admin/templates           # Query templates list
POST   /api/v1/admin/templates
PATCH  /api/v1/admin/templates/{id}
DELETE /api/v1/admin/templates/{id}
GET    /api/v1/admin/config
PATCH  /api/v1/admin/config             # Body: { "key": str, "value": str }
```

### 11.6 Error Response Format

All errors follow:
```json
{
  "error": {
    "code": "FILE_TOO_LARGE",           // Machine-readable
    "message": "This file is too large (623 MB). Maximum file size is 500 MB per file.",
    "detail": null                      // Optional technical detail (only for 5xx, admin only)
  }
}
```

Raw stack traces are **never** included in error responses to analysts. Logged server-side only.

---

## 12. WebSocket

**Endpoint:** `WSS /ws/tasks/{task_id}`  
**Auth:** JWT passed as query parameter `?token=<JWT>` on connection (standard WS limitation — no custom headers).  
**Protocol:** JSON messages only.

### 12.1 Server → Client Events

```typescript
type WSEvent =
  | { type: "task_queued";       data: { queue_position: number; estimated_wait_minutes: number } }
  | { type: "task_started";      data: { started_at: string } }
  | { type: "analyzer_complete"; data: { files_profiled: number; descriptions: FileDescription[] } }
  | { type: "round_started";     data: { round: number; max_rounds: number; plan_step: string } }
  | { type: "round_complete";    data: { round: number; verifier_verdict: "Yes"|"No"; router_decision: string; stdout_preview: string } }
  | { type: "debug_attempt";     data: { round: number; attempt: number; error_type: string } }
  | { type: "task_paused";       data: { paused_at_round: number; checkpoint_expires_at: string } }
  | { type: "round_cap_reached"; data: { round: number; hard_cap: number } }
  | { type: "task_complete";     data: { result: FIPResult; is_complete: boolean } }
  | { type: "task_failed";       data: { error_summary: string } }
  | { type: "task_stopped";      data: {} }
  | { type: "checkpoint_recovery"; data: { recovered_from_round: number } }
  | { type: "queue_position_update"; data: { position: number; estimated_wait_minutes: number } }
  // DS-STAR+ only:
  | { type: "subquestions_generated"; data: { sub_questions: string[]; count: number } }
  | { type: "subquestion_started";    data: { index: number; total: number; question: string } }
  | { type: "subquestion_complete";   data: { index: number; answer_preview: string } }
  | { type: "report_writing_started"; data: {} }
  | { type: "refinement_round";       data: { k: number; new_subquestions: string[] } }
  | { type: "report_complete";        data: { result: FIPResearchResult } }
```

### 12.2 Client → Server Events

```typescript
// Sent over the same WS connection
type WSClientEvent =
  | { type: "hint";   data: { hint_text: string } }
  | { type: "pause";  data: {} }
  | { type: "stop";   data: {} }
  | { type: "extend"; data: {} }
```

### 12.3 Connection Management

- Connection is kept alive for the duration of the task.
- Server sends a `ping` frame every 30 seconds; client must respond with `pong`.
- On disconnect (JWT expired, browser tab closed), the task continues running. The analyst reconnects and receives the current state via `GET /api/v1/tasks/{id}` on reconnect; WS reconnects and resumes streaming.
- Max 2 concurrent WS connections per task (allows analyst to open on two browser tabs).

---

## 13. Frontend Architecture

### 13.1 Application Structure

```
src/
  components/
    ui/           — shadcn/ui base components (Button, Input, Modal, Badge, etc.)
    chat/         — QueryInput, StarterTemplates, DatasetSelector, FormattingControl
    dashboard/    — ProgressPanel, ResultPanel, HistorySidebar, SteeringInput
    result/       — NarrativeSection, ChartRenderer, TableRenderer, ExportBar, FeedbackBar
    research/     — SubQuestionList, ReportViewer, CitationExpandable
    admin/        — UserTable, AuditLogViewer, HealthDashboard, TemplateEditor
    shared/       — ErrorToast, LoadingSpinner, InlineNotification, ModeBadge
  pages/
    Login.tsx
    Chat.tsx
    Dashboard.tsx
    Admin.tsx
  hooks/
    useTask.ts        — Task state, WS connection management
    useDatasets.ts    — Dataset list, upload, suggestion
    useAuth.ts        — JWT, user profile, logout
  stores/
    taskStore.ts      — Zustand store: active task state
    authStore.ts      — Zustand store: auth state
  lib/
    api.ts            — Typed API client (fetch wrapper with JWT injection)
    ws.ts             — WebSocket client with auto-reconnect
    chartAdapter.ts   — Converts Coder JSON → Recharts props
```

### 13.2 Key Component Behaviours

**`QueryInput`**
- Max 5,000 characters; character counter appears at 4,000 (red at 4,800)
- Enter = submit; Shift+Enter = newline
- Submit disabled when empty
- File upload: drag-and-drop zone + click-to-browse; progress per file

**`DatasetSelector`** (shown after submit, before task starts)
- Fetches `/api/v1/datasets/suggest?query={q}` on mount
- Lists top 5–8 suggestions with file name, type icon, date, one-line description
- Analyst can add/remove; "Confirm and Start Analysis" is the only proceed path
- Cold start path: if 0 datasets available, shows inline upload prompt instead

**`ProgressPanel`**
- Default (summary): animated progress bar + current phase label
- Expanded (full trace): current agent, round counter `N / max`, last stdout preview (truncated 500 chars), steering hints list
- DS-STAR+ (research mode): sub-question list with status icons; active sub-question shows its own round budget

**`SteeringInput`**
- Always visible while task running
- Submits via WS `{ type: "hint" }` or `POST /api/v1/tasks/{id}/hints`
- Displays all prior hints with timestamps below the input

**`ChartRenderer`**
- Receives Coder's chart JSON; maps `type` → Recharts component
- Supported natively: `bar`, `line`, `area`, `pie`, `composed`
- Falls back to Plotly.js for: `heatmap`, `scatter_matrix`, `treemap`, `funnel`
- On render error: shows "Chart could not be rendered — raw data below" + table fallback

**`CitationExpandable`** (research mode only)
- Inline `(Source: Sub-question N)` text is clickable
- Expands to: sub-question text, code `sᵢ`, raw output `aᵢ`

### 13.3 State Management

Zustand for global state (no Redux). Task state is primarily driven by the WS event stream:

```typescript
// taskStore.ts
interface TaskState {
  task: Task | null;
  rounds: RoundResult[];
  subquestions: SubQuestion[];     // DS-STAR+ only
  wsBus: EventEmitter;             // WS events dispatched here
  
  setTask: (task: Task) => void;
  handleWSEvent: (event: WSEvent) => void;
  reset: () => void;
}
```

### 13.4 Routing

```typescript
// React Router v6
/login            → <Login />              (public)
/chat             → <Chat />               (auth required)
/dashboard        → <Dashboard />          (auth required)
/dashboard?task=X → <Dashboard /> with task pre-loaded
/admin            → <Admin />              (admin role required; 403 page for analysts)
```

---

## 14. Report Generation

### 14.1 Pipeline

```
FIP Result JSON
      │
      ▼
Report Writer (LangGraph node)
      │ Produces: Markdown document + chart references + table data
      ▼
Jinja2 Template Engine (python-docx-template)
      │ Merges content into .docx template
      ▼
.docx file → MinIO (fip-reports/)
      │
      ├──────────────────────────────────────► .docx download
      │
      ▼
LibreOffice headless (subprocess call)
      │ libreoffice --headless --convert-to pdf
      ▼
.pdf file → MinIO (fip-reports/)
      │
      ▼
Excel export (separate path):
      openpyxl → one sheet per table → charts as embedded images
      .xlsx file → MinIO (fip-reports/)
```

### 14.2 Word Template System

System default template (`fip-templates/default.docx`) contains:
- CBUAE letterhead and classification banner
- Jinja2 placeholders: `{{ title }}`, `{{ date }}`, `{{ analyst_name }}`, `{{ department }}`, `{{ executive_summary }}`, `{{ methodology }}`, `{{ findings_sections }}`, `{{ recommendations }}`
- Footer: classification, page numbers, "Generated by FIP — AI-assisted analysis. Verify before use."

Analyst custom templates (FR-OUT-07) follow the same placeholder schema. Validation: on upload, check that at least one recognised placeholder is present; reject with error if none found.

### 14.3 Chart Rendering for Exports

Browser charts (Recharts/Plotly.js) are interactive — not directly usable in Word/PDF. For exports:

1. Frontend renders the chart to an off-screen `<canvas>` element
2. Canvas is exported as base64 PNG at 300 DPI via `canvas.toDataURL('image/png')`
3. PNG is sent to `POST /api/v1/tasks/{id}/export/charts` alongside the export request
4. Backend embeds the PNG into the .docx via `python-docx-template`

**Alternative (server-side rendering, no frontend dependency):** Use `matplotlib` in the sandbox to render charts as PNG files alongside the Recharts JSON. Preferred for headless export reliability. Both approaches are acceptable for V1.

---

## 15. Authentication & RBAC

> **`[PENDING OQ-1]`** — The auth mechanism depends on whether CBUAE has Active Directory / SSO. The design below covers the standalone JWT approach. If OQ-1 confirms AD/SSO, §15.1 is replaced with OIDC/SAML integration; §15.2–15.4 remain unchanged.

### 15.1 JWT Authentication (Standalone — current design)

```python
TOKEN_ALGORITHM = "HS256"
TOKEN_EXPIRY_SECONDS = 28800        # 8 hours (one working day)
TOKEN_SIGNING_KEY = vault.get("fip/jwt-signing-key")   # Fetched from Vault at startup

# Token payload
{
  "sub": user_id,
  "email": email,
  "role": "analyst" | "admin",
  "department_id": department_id,
  "iat": issued_at,
  "exp": expires_at
}
```

**Login endpoint:** `POST /api/v1/auth/login` — bcrypt compare `password` against `users.password_hash`. On success, issue JWT. Rate-limited: 10 attempts per 15 minutes per IP.

**Session invalidation:** Redis blocklist keyed by `jti` (JWT ID). `POST /api/v1/auth/logout` adds `jti` to blocklist with TTL = remaining token lifetime. All protected endpoints check blocklist.

**Session persistence on task running:** If JWT expires while a task is running, the task continues uninterrupted (runs in worker process, not browser session). The analyst is shown: "Your session has expired. Your analysis is still running. Log in again to view results." On re-login, the task is accessible via history.

### 15.2 RBAC Enforcement

RBAC is enforced at the **API layer** — never UI-only. FastAPI dependency:

```python
async def require_analyst(token: str = Depends(oauth2_scheme)) -> UserContext:
    payload = decode_jwt(token)
    if not payload or payload["role"] not in ["analyst", "admin"]:
        raise HTTPException(403)
    return UserContext(**payload)

async def require_admin(token: str = Depends(oauth2_scheme)) -> UserContext:
    payload = decode_jwt(token)
    if not payload or payload["role"] != "admin":
        raise HTTPException(403)
    return UserContext(**payload)
```

**Data access scoping (every dataset query):**
```python
def scope_to_department(query: Query, user: UserContext) -> Query:
    """Every dataset query is filtered to user's department. Applied in every service method."""
    return query.join(DatasetDepartmentAccess).filter(
        DatasetDepartmentAccess.department_id == user.department_id
    )
```

**Analyst cross-access prevention:** Task ownership check on every task endpoint:
```python
if task.user_id != current_user.id and current_user.role != "admin":
    raise HTTPException(403)
```

### 15.3 Admin vs Analyst Separation

Admin page is served at a separate path (`/admin`). A non-admin JWT hitting any `/api/v1/admin/*` endpoint receives `403` — no redirect to login. Admin accounts are created by other admins; they cannot self-register. Admin and analyst roles are mutually exclusive in `users.role`.

### 15.4 Password Policy (Standalone auth only)

- Minimum 12 characters; at least one uppercase, one lowercase, one number, one symbol
- Stored as bcrypt hash (cost factor 12)
- Forced password change on first login
- No password reset via email in V1 (no email system) — admin resets via `PATCH /api/v1/admin/users/{id}`

---

## 16. Audit Log

### 16.1 Write Path

The audit log is written in a dedicated database connection using a **restricted PostgreSQL role** (`fip_audit_writer`) that has only `INSERT` and `SELECT` permissions on `audit_log`. No `UPDATE` or `DELETE` granted at the database level — not just the application level.

```python
class AuditLogger:
    """All audit writes go through this class. Never write to audit_log directly."""
    
    async def log(self, event_type: str, task_id: UUID | None, user_id: UUID | None,
                  department_id: UUID | None, payload: dict) -> None:
        prev_record = await self._get_last_record()
        prev_hash = prev_record.entry_hash if prev_record else "0" * 64
        
        entry_data = json.dumps({
            "event_type": event_type,
            "task_id": str(task_id),
            "user_id": str(user_id),
            "payload": payload,
            "created_at": now_utc().isoformat()
        }, sort_keys=True)
        
        entry_hash = sha256(f"{prev_hash}{entry_data}".encode()).hexdigest()
        
        await self._insert(
            entry_hash=entry_hash,
            prev_hash=prev_hash,
            event_type=event_type,
            task_id=task_id,
            user_id=user_id,
            department_id=department_id,
            payload=payload
        )
```

### 16.2 Tamper Detection

```python
async def verify_chain_integrity() -> IntegrityReport:
    """Admin-runnable. Verifies every hash in the chain sequentially."""
    records = await fetch_all_ordered_by_id()
    broken_at = None
    prev_hash = "0" * 64
    
    for record in records:
        expected_entry_data = reconstruct_entry_data(record)
        expected_hash = sha256(f"{prev_hash}{expected_entry_data}".encode()).hexdigest()
        
        if expected_hash != record.entry_hash:
            broken_at = record.id
            break
        
        prev_hash = record.entry_hash
    
    return IntegrityReport(
        is_intact=broken_at is None,
        total_records=len(records),
        broken_at_record_id=broken_at
    )
```

**Exposed as:** `POST /api/v1/admin/audit-log/verify-integrity` — returns `IntegrityReport`. The action of running this check is itself logged to the audit log.

---

## 17. Data Versioning & Snapshots

Every time an analyst confirms dataset selection and starts a task, the system creates a point-in-time snapshot of each selected file. This ensures that even if the underlying file is updated or deleted, the result of the analysis remains verifiable against the exact data that produced it.

### 17.1 Snapshot Creation

```python
async def create_snapshot(dataset_id: UUID, task_id: UUID) -> DataSnapshot:
    # 1. Read original file from MinIO
    file_bytes = await minio.get_object(dataset.storage_key)
    
    # 2. Compute file hash
    file_hash = sha256(file_bytes).hexdigest()
    
    # 3. Check if identical snapshot already exists (hash deduplication)
    existing = await db.query(DataSnapshot).filter_by(dataset_id=dataset_id, file_hash=file_hash).first()
    if existing:
        return existing   # Reuse snapshot — no redundant copy in MinIO
    
    # 4. Copy file to snapshot storage
    snapshot_key = f"snapshots/{dataset_id}/{uuid4()}/{dataset.file_name}"
    await minio.copy_object(source=dataset.storage_key, dest=snapshot_key)
    
    # 5. Create snapshot record
    return await db.create(DataSnapshot(
        dataset_id=dataset_id,
        snapshot_key=snapshot_key,
        file_hash=file_hash,
        row_count=await count_rows(file_bytes, dataset.file_type)
    ))
```

### 17.2 Snapshot Access Control

- **Analysts:** Can view snapshot metadata (file name, snapshot ID, timestamp, row count) for their own tasks via the "Data sources used" panel. Cannot download snapshot files directly. Cannot access other analysts' snapshots.
- **Admin:** Full access to any snapshot by task ID. `GET /api/v1/admin/tasks/{id}/snapshots/{snapshot_id}/download` streams the snapshot file. Logged in audit log.
- **No deletion:** Snapshots are never deleted. No retention policy in V1. Storage growth monitored in admin health dashboard.

---

## 18. Deployment Architecture

> **`[PENDING OQ-7]`** — GPU hardware specs (model, VRAM, count) unknown. The deployment topology below assumes a minimum viable on-premise server cluster. Actual node counts, GPU allocation, and inference throughput must be validated against OQ-7 before the TDD is finalised.

### 18.1 Assumed Server Topology (to be confirmed)

```
Node 1 — Web / API server
  - Nginx (TLS termination, reverse proxy)
  - FastAPI application server (Gunicorn + Uvicorn workers: 4)
  - Redis Sentinel node 1

Node 2 — Worker server A
  - Celery worker (concurrency: 4)
  - Docker daemon (rootless)
  - Redis Sentinel node 2

Node 3 — Worker server B  
  - Celery worker (concurrency: 4)
  - Docker daemon (rootless)
  - Redis Sentinel node 3

Node 4 — GPU server (1–N, spec PENDING OQ-7)
  - Ollama or vLLM
  - GPU inference service
  - [OQ-7: determines VRAM, model size, throughput]

Node 5 — Data server
  - PostgreSQL 16 (primary)
  - MinIO (on-premise object storage)
  - PostgreSQL streaming replica (same node or dedicated)

Node 6 — Security
  - HashiCorp Vault
  - Dedicated, no other services
```

### 18.2 Container Orchestration

**V1 target:** Kubernetes (K8s) on bare metal. Docker Compose provided for development only.

Kubernetes resources:
- `Deployment`: api-server, celery-worker, nginx
- `StatefulSet`: postgresql, redis-sentinel (3 replicas), minio
- `DaemonSet`: Not used (GPU node is managed separately by Ollama)
- `ConfigMap`: Non-secret config
- `Secret`: References to Vault paths (Vault Agent Injector pattern — secrets mounted as files, not env vars)
- `PersistentVolumeClaim`: PostgreSQL data, MinIO data, sandbox data mount

**No Helm chart in V1.** Plain Kubernetes YAML manifests in `infrastructure/k8s/`. This keeps the deployment understandable by CBUAE IT without Helm expertise.

### 18.3 Air-Gap Verification

Before launch, the following must pass (from FR Launch Criteria §11):
```bash
# From every node: all outbound connections must fail
curl --max-time 5 https://api.anthropic.com  # Must fail
curl --max-time 5 https://generativelanguage.googleapis.com  # Must fail
curl --max-time 5 https://registry.npmjs.org  # Must fail
# ... etc. for all external endpoints
```

All container images must be pre-pulled into a private on-premise container registry (e.g., Harbor) during an internet-connected build phase, then the network connection is severed before production deployment.

---

## 19. Performance Considerations

### 19.1 LLM Inference Latency

The dominant factor in task duration is LLM inference. Each round invokes 2–5 LLM calls (Planner, Coder, Verifier, and optionally Debugger + Router). At a local Flash model doing ~500 tokens/second, a round with ~1000 token output takes ~2 seconds per call → 4–10 seconds per round for agent calls alone.

**P95 targets (from PRD §9.1):**

| Scenario | Target | Key assumption |
|----------|--------|---------------|
| Insight, easy (≤3 rounds) | < 3 min | Flash inference at 500 tok/s |
| Insight, hard (≤10 rounds) | < 20 min | Flash inference at 500 tok/s |
| Research (7 sub-questions, K=1) | < 60 min | Sequential; Flash for agents, Pro for Writer |
| Reformat only | < 30 sec | Finalizer only; no pipeline re-run |

**[PENDING OQ-7]:** If local GPU inference is materially slower than assumed, these targets may not be achievable. Must benchmark actual inference throughput against real hardware before committing to targets.

### 19.2 Database Indexing

Critical indexes already defined in §8. Additional query-time index:

```sql
-- Audit log chain integrity check (sequential scan of all records)
-- No index needed — full table scan is intentional for integrity verification
-- For admin search queries (partial text match on payload):
CREATE INDEX idx_audit_log_payload ON audit_log USING gin(payload);
```

### 19.3 MinIO Storage Estimates

Conservative estimate per active analyst per month:
- Uploaded data: 500 MB average × 20 uploads = 10 GB
- Snapshots: ~10 GB (deduplication reduces this)
- Scripts: ~50 KB per task × 100 tasks = 5 MB
- Reports: ~2 MB per report × 50 reports = 100 MB

**Total per analyst per month:** ~20 GB. With 50 analysts: ~1 TB/month raw growth (before deduplication). MinIO cluster must be provisioned with at least 12 months of projected storage from day one.

---

## 20. Security Implementation

### 20.1 Secrets Management

All secrets fetched from HashiCorp Vault at service startup. Zero secrets in:
- Environment variables
- Kubernetes `Secret` objects (Vault Agent Injector pattern)
- Config files committed to source control
- Container images

```python
# Secrets fetched at startup via Vault AppRole
SECRETS = vault.read("fip/production")
# Returns: { "db_password", "jwt_signing_key", "minio_access_key", "minio_secret_key", ... }
```

### 20.2 mTLS Configuration

All service-to-service communication uses mutual TLS with certificates issued by an internal CA (managed by Vault PKI secrets engine). Certificate rotation: 30-day validity, auto-renewed 5 days before expiry.

```
Nginx → FastAPI:   mTLS, cert CN=api-server
FastAPI → Postgres: mTLS, cert CN=api-server, verified against DB CA
FastAPI → MinIO:   mTLS, cert CN=api-server
FastAPI → Redis:   TLS (Redis does not support mTLS natively)
Worker → Postgres:  mTLS, cert CN=celery-worker
Worker → MinIO:    mTLS, cert CN=celery-worker
Worker → Ollama:   mTLS, cert CN=celery-worker
All → Vault:       mTLS + AppRole token
```

### 20.3 Input Sanitisation

**File upload:** Content-type validation at the API layer (reject if MIME type doesn't match extension). File content is never injected directly into LLM prompts — only the Analyzer's structured description `D` is passed. This prevents prompt injection via file content (Risk R4 in PRD §14).

**Query text:** Maximum 5,000 characters. HTML stripped server-side before storage. The query is not executed as code — it is passed to the LLM as plain text within a structured system prompt. Prompt injection risk is mitigated by the agent system prompts explicitly instructing agents to treat user input as data, not instruction.

**Sandbox:** See §6.3. The sandbox security profile is the primary mitigation for Risk R5.

### 20.4 Pen Test Scope (Pre-Launch Requirement)

Per PRD §11 Launch Criteria, the following must be covered by IT Security's penetration test:
- Sandbox escape via crafted Python script
- Prompt injection via uploaded PDF, Excel, or CSV content
- JWT tampering (algorithm confusion, signature bypass)
- RBAC bypass (cross-department dataset access, cross-analyst task access)
- MinIO direct access bypass (can analyst reach another analyst's files without API?)
- DoS via task flooding (concurrency budget enforcement)
- Audit log manipulation (can any role UPDATE or DELETE audit records?)

---

## 21. Open Questions Tracker

| # | Question | Status | Blocks |
|---|----------|--------|--------|
| OQ-1 | Authentication system — Active Directory / SSO or standalone? | **OPEN** | §15 Auth design, JWT vs OIDC/SAML |
| OQ-2 | Largest single dataset an analyst would query (row count, GB) | **OPEN** | Executor memory limits, file upload UX, Analyzer timeout |
| OQ-3 | Existing Word/PDF report templates from FPS — samples available? | **OPEN** | §14 Report template design |
| OQ-4 | Integration with case management system (NICE Actimize, ServiceNow) in V1? | **OPEN** | API contract scope |
| OQ-5 | Data freshness requirement for institutional datasets | **OPEN** | Data ingestion pipeline (not in V1 scope but affects MinIO retention) |
| OQ-6 | Dataset access approval authority — who approves per-analyst dataset access? | **OPEN** | Admin panel workflow design |
| OQ-7 | On-premise GPU hardware (model, VRAM, count) | **OPEN — IMMEDIATE** | §18 Deployment topology, §19 Performance targets, LLM model selection |
| OQ-8 | Expected peak concurrent analyst usage | **OPEN** | §10 Queue sizing, §18.1 node count |
| OQ-9 | Baseline metrics establishment (time studies for thematic review, benchmarking table) | **OPEN** | PRD §3 success metrics; does not block TDD |

**Resolution required before TDD is finalised:** OQ-1 (§15), OQ-7 (§18, §19)  
**Resolution required before build begins:** OQ-2, OQ-5, OQ-6, OQ-8  
**Resolution required before Closed Beta:** OQ-3, OQ-4, OQ-9

---

*This TDD is a living document. All changes must be reflected back into the PRD if they affect functional requirements. Architecture decisions that arise during build must be added to `00-discovery/04-architecture-decisions.md` before being implemented.*
