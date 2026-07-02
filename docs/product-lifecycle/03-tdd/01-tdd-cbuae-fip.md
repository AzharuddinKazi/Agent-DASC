# Technical Design Document
## CBUAE Financial Intelligence Platform (FIP) — V1

**Stage:** TDD — Stage 3  
**Branch:** `docs/product-lifecycle`  
**Date:** 2026-07-02  
**Author:** Engineering, Agent-DASC  
**Status:** Draft v0.2 — In Review  
**PRD Reference:** `01-prd/01-prd-cbuae-fip.md` (v0.2)

**Prerequisite documents:**
- `00-discovery/01-paper-analysis.md` — DS-STAR paper deep-dive (arXiv:2509.21825)
- `00-discovery/04-architecture-decisions.md` — 18 architecture decisions with paper references (Q1–Q18)
- `00-discovery/03-architecture-v2.html` — Architecture diagram v3.3
- `00-discovery/05-feature-discussion.md` — Feature decisions (Topics 1–10)
- `01-prd/01-prd-cbuae-fip.md` — Full PRD with functional requirements and acceptance criteria

**Pending inputs (blocks TDD sections marked `[PENDING]`):**
- **OQ-1** — Authentication system (Active Directory / CBUAE SSO / standalone) — blocks §17 Auth design
- **OQ-7** — On-premise GPU hardware specs — blocks §20 Deployment, §21 Performance

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-07-01 | Engineering, Agent-DASC | Initial draft |
| 0.2 | 2026-07-02 | Engineering, Agent-DASC | Add Background, Goals/Non-Goals, Alternatives Considered, Observability; fix audit log concurrency race; fix PII in WS stdout_preview; resolve chart export (server-side); add Docker/K8s access model; add LibreOffice timeout; add checkpoint schema migration; add config.updated audit event; add soft-time-limit WS event |

---

## Table of Contents

1. [Background & Motivation](#1-background--motivation)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Alternatives Considered](#3-alternatives-considered)
4. [System Overview](#4-system-overview)
5. [Architecture Topology](#5-architecture-topology)
6. [Technology Stack](#6-technology-stack)
7. [LangGraph Pipeline — DS-STAR Implementation](#7-langgraph-pipeline--ds-star-implementation)
8. [Agent Specifications](#8-agent-specifications)
9. [Docker Sandbox](#9-docker-sandbox)
10. [LLM Provider Adapter](#10-llm-provider-adapter)
11. [Database Schema](#11-database-schema)
12. [File Storage](#12-file-storage)
13. [Task Queue](#13-task-queue)
14. [REST API](#14-rest-api)
15. [WebSocket](#15-websocket)
16. [Frontend Architecture](#16-frontend-architecture)
17. [Report Generation](#17-report-generation)
18. [Authentication & RBAC](#18-authentication--rbac)
19. [Audit Log](#19-audit-log)
20. [Data Versioning & Snapshots](#20-data-versioning--snapshots)
21. [Deployment Architecture](#21-deployment-architecture)
22. [Performance Considerations](#22-performance-considerations)
23. [Security Implementation](#23-security-implementation)
24. [Observability & Monitoring](#24-observability--monitoring)
25. [Open Questions Tracker](#25-open-questions-tracker)

---

## 1. Background & Motivation

CBUAE's Financial Crime & Market Conduct division supervises 47+ Licensed Financial Institutions (LFIs) across five departments: Fraud Prevention Supervision, AML/CFT Supervision, Market Conduct, Enforcement, and Policy & Research.

**Current state:** Supervisory analysis is performed manually. An analyst querying "Which LFIs have the highest APP fraud rate relative to transaction volume?" must request data from IT, wait for an extract, clean the file in Excel, write pivot tables, and produce a summary — a process taking 2–4 days per analysis. Thematic reviews (e.g., a sector-wide APP fraud trend analysis) take weeks. Non-technical analysts cannot independently query data at all.

**Pain:** The bottleneck is not data availability — CBUAE receives structured fraud loss reports, SAR/STR records, KYC/CDD data, and market surveillance data from all LFIs. The bottleneck is the translation layer between a natural language supervisory question and a data-backed answer.

**Proposed solution:** The Financial Intelligence Platform (FIP) lets analysts type their question in plain English, observe the system reason through it step by step, and receive a data-backed answer with full traceability — question → plan → code → result. Built on the DS-STAR multi-agent architecture (arXiv:2509.21825, Google Cloud, Sept 2025), deployed entirely on-premise within CBUAE's air-gapped network.

---

## 2. Goals & Non-Goals

### Goals (V1)

- **G1:** Allow any analyst in the five FIP departments to submit a natural language query and receive a data-backed answer — without writing code or involving IT.
- **G2:** Support two query modes: FIP-Insight (specific factoid/analytical questions) and FIP-Research (open-ended thematic reports with citations).
- **G3:** Every result is fully explainable: analysts can inspect the plan, the generated code, and the raw output for every round.
- **G4:** Full immutable audit trail: every query, every code version, every result is logged in a tamper-evident append-only store. Required for regulatory examination readiness.
- **G5:** Zero data leaves the CBUAE perimeter. All LLM inference runs locally. No cloud APIs in production.
- **G6:** Department-level data access control: an analyst can only query datasets their department is permitted to access.
- **G7:** Export results as Word, PDF, and Excel reports using CBUAE-branded templates.
- **G8:** REST API for programmatic consumption of results by other internal systems.

### Non-Goals (V1 — explicit exclusions)

- **NG1:** Real-time or streaming data ingestion. V1 is batch-upload only — analysts upload files or admins provision institutional datasets. No live feeds.
- **NG2:** Integration with external case management systems (NICE Actimize, ServiceNow). API contract is internal-only in V1 (see OQ-4).
- **NG3:** Email or SMS notifications. No email relay in the air-gapped environment (see FR-AH-03 in PRD).
- **NG4:** Mobile application. Web browser only.
- **NG5:** Arabic language support. English interface only in V1.
- **NG6:** Automated scheduled analysis (cron-triggered reports). Analyst-initiated only.
- **NG7:** Self-service LFI data submission portal. Institutional data is loaded by admin only.
- **NG8:** Cross-divisional access (other CBUAE divisions outside Financial Crime & Market Conduct). Scope is the five departments above.
- **NG9:** Model fine-tuning or training. LLM inference only; no training pipeline.
- **NG10:** Exposing generated Python code directly to analysts by default. Code is archived and accessible to admins; analyst-facing result is the narrative + tables + charts.

---

## 3. Alternatives Considered

### A1: Agent Orchestration Framework

**Chosen: LangGraph**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **LangGraph** | ✅ Chosen | Native PostgreSQL checkpointing (critical for crash recovery on 70-min tasks). `interrupt()` primitive enables pause/extend without a new graph instance. Strict typed `StateGraph` with Pydantic models. First-class conditional edges support DS-STAR's backtracking Router cleanly. Actively maintained by LangChain company. |
| CrewAI | ❌ Rejected | Task-centric abstraction (not state-graph). No native checkpointing — crash loses all progress. Less control over agent-to-agent routing; backtracking Router pattern not expressible natively. |
| AutoGen | ❌ Rejected | Conversation-oriented multi-agent model. Not suited to DS-STAR's strict round-by-round iterative structure with explicit state accumulation and backtracking. |
| Custom FSM (Python) | ❌ Rejected | We would rebuild checkpointing, interrupt/resume, state typing, and conditional edge routing — all of which LangGraph provides. No upside; significant engineering overhead and higher long-term maintenance burden. |

---

### A2: Code Execution Sandbox

**Chosen: Docker with custom seccomp profile**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Docker + seccomp** | ✅ Chosen | Well-understood operational model. Pre-built images, rich library ecosystem, standard Kubernetes support. Custom seccomp profile blocks `socket`, `connect`, `ptrace`, `mount`. Per-task container with `docker exec` per round avoids cold-start overhead. |
| gVisor (`runsc`) | ⚠️ V2 candidate | Kernel-emulation isolation is stronger than seccomp filtering. Rejected for V1: ~20% CPU overhead vs. native; requires Kubernetes `RuntimeClass` configuration; limited compatibility with `scikit-learn` compiled C extensions (untested). **Flagged for V2 if pen test identifies Docker seccomp gaps.** |
| Firecracker microVM | ❌ Rejected | Best theoretical isolation (hypervisor boundary). Rejected: 125 ms+ VM boot latency vs. <5 ms `docker exec`; no pre-built analytics image ecosystem; overkill for a read-only analytics workload where the primary threat is data exfiltration, not kernel exploits. |
| WebAssembly (WASM) | ❌ Rejected | Python runtime in WASM is experimental. Required libraries (`pandas`, `scikit-learn`, `pdfplumber`) lack mature WASM builds. Performance unknown. Not viable for V1 timeline. |

---

### A3: Task Queue

**Chosen: Celery + Redis Sentinel**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Celery + Redis Sentinel** | ✅ Chosen | Mature ecosystem. `task_acks_late` + `task_reject_on_worker_lost` provides exactly-once semantics on worker crash — critical for 70-min tasks. Priority queue support (insight vs. research). DLQ with retry. Extensive monitoring via Flower and Prometheus exporters. |
| ARQ (Async Redis Queue) | ❌ Rejected | No priority queue. No DLQ. No `acks_late` equivalent. Insufficient retry/backoff control. Better suited to short-lived tasks. |
| FastAPI `BackgroundTasks` | ❌ Rejected | In-process, no persistence. Worker process restart loses all in-flight tasks. Fundamentally unsuited to long-running tasks requiring crash recovery. |
| Kafka | ❌ Rejected | Correct for streaming pipelines; wrong for task queues. Adds operational complexity (Zookeeper or KRaft), no native task-result pattern, disproportionate overhead for the expected task volume (<50 concurrent tasks). |

---

### A4: Object Storage

**Chosen: MinIO**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **MinIO** | ✅ Chosen | S3-compatible API: zero code change if ever migrated; per-bucket encryption at rest (AES-256 SSE-S3); bucket-level access policies; active community; single binary deployment. |
| NFS/shared filesystem | ❌ Rejected | No object-level encryption. No access policy per path (directory permissions only). Race conditions on concurrent writes. Harder to reason about path isolation between tasks and users. |
| Ceph | ❌ Rejected | Functionally superior but operationally prohibitive for the team size. Ceph requires dedicated cluster management expertise and significant hardware overhead. No advantage over MinIO at the expected storage volumes. |

---

### A5: LangGraph Checkpoint Store — PostgreSQL vs. Redis

**Chosen: PostgreSQL**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **PostgreSQL** | ✅ Chosen | `langgraph-checkpoint-postgres` is the canonical production-grade backend. Single source of truth: checkpoints, task state, audit log, and RBAC all in one system — one fewer operational dependency. Durable by default; queryable for debugging. |
| Redis (native) | ❌ Rejected | Checkpoint durability depends on AOF persistence being correctly configured; misconfiguration silently loses checkpoints. Redis restart without AOF flushes all state. For 70-minute tasks, the durability guarantee of PostgreSQL WAL is non-negotiable. |

---

### A6: LLM Serving — Ollama vs. vLLM

**Decision: Deferred to OQ-7 resolution. Both adapters are implemented; CBUAE IT selects based on GPU specs.**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Ollama** | ✅ Default | Single binary; excellent model management (`ollama pull`); adequate throughput for sequential requests (~500 tok/s on a single A100). Lower operational burden. Chosen as the default unless OQ-7 shows concurrent load exceeds single-request throughput. |
| vLLM | ✅ If needed | Continuous batching provides 3–5× higher throughput at the cost of operational complexity. Appropriate if OQ-7 reveals the GPU cluster must serve >4 concurrent 70B-class inference requests. The `OllamaAdapter` and `vLLMAdapter` share the same `LLMAdapter` interface — switching requires only a config change. |

---

## 4. System Overview

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

## 5. Architecture Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ANALYST BROWSER                                                         │
│  React SPA — /login · /chat · /dashboard · /admin                       │
│  ┌──────────┐   HTTPS + JWT    ┌─────────────────────────────────────┐  │
│  │  React   │ ────────────────►│         Nginx (reverse proxy)       │  │
│  │  + WS    │ ◄────────────────│         TLS termination             │  │
│  └──────────┘   WS + JWT       └──────────────┬──────────────────────┘  │
└────────────────────────────────────────────────│─────────────────────────┘
                                                 │ mTLS
                        ┌────────────────────────▼─────────────────────────┐
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
                        │                 │ HTTP (mTLS)                    │
                        │   ┌─────────────▼───────────────────────────┐   │
                        │   │  Sandbox Service (separate pod)          │   │
                        │   │  Owns Docker daemon                      │   │
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
- Zone C (Workers → Sandbox Service → PostgreSQL / MinIO / Ollama): mTLS, internal only
- Zone D (Vault): mTLS, AppRole auth; all secrets fetched at service startup; no env-var secrets

**What is NOT present in this topology:**
- No internet gateway. No external DNS resolution. No cloud endpoints.
- No email relay (V1 has no email notifications — FR-AH-03).
- No CI/CD runner (deployments handled via offline artifact delivery by IT).

---

## 6. Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend framework | React 18 | Pinned in `package.json`; doc references major version only |
| Frontend styling | Tailwind CSS 4 | |
| Frontend components | shadcn/ui (latest) | Built on Radix UI primitives |
| Charts (primary) | Recharts 2 | For standard bar, line, area, pie |
| Charts (fallback) | Plotly.js 5 | For advanced types Recharts can't handle |
| WebSocket client | Native browser WebSocket API | No library needed |
| API server | FastAPI | Python 3.11+ |
| Agent orchestration | LangGraph 0.2+ | LangGraph Server for checkpoint management |
| Checkpoint store | PostgreSQL 16 | Via `langgraph-checkpoint-postgres` |
| Task queue | Celery 5 | |
| Queue broker | Redis Sentinel 7 | HA mode with 3 Sentinel nodes |
| Result backend | Redis 7 | Same Sentinel cluster |
| LLM inference | Ollama (prod) / Gemini API (dev) | Behind provider adapter; see §3 A6 |
| Object storage | MinIO | S3-compatible, on-premise |
| Relational database | PostgreSQL 16 | Single instance + streaming replica |
| Secret management | HashiCorp Vault 1.17+ | AppRole auth |
| Reverse proxy | Nginx 1.25+ | TLS termination, static asset serving |
| Sandbox runtime | Docker 26+ (rootless) | Managed by dedicated Sandbox Service pod; see §9 |
| Report: Word | python-docx-template | Jinja2 template engine for .docx |
| Report: PDF | LibreOffice headless | Converts .docx → .pdf server-side |
| Report: Excel | openpyxl | |
| Auth | PyJWT + bcrypt | HS256 tokens; 8-hour expiry; [PENDING OQ-1] |
| Internal comms | mTLS (mutual TLS) | All service-to-service |
| Containerisation | Docker Compose (dev) / Kubernetes (prod) | |
| Schema migrations | Alembic | Versioned migrations; see §21.4 |

**Authoritative version pins:** `backend/requirements.txt` and `frontend/package.json`. Version numbers in this document reflect major versions only and are informational.

**Python version:** 3.11 throughout (backend, workers, sandbox). Type hints required on all public functions.

---

## 7. LangGraph Pipeline — DS-STAR Implementation

### 7.1 Graph Overview

Two separate LangGraph `StateGraph` definitions:

1. **`dsstar_graph`** — FIP-Insight (DS-STAR mode)
2. **`dsstar_plus_graph`** — FIP-Research (DS-STAR+ mode); internally calls `dsstar_graph` per sub-question

Both graphs checkpoint to PostgreSQL after every node execution. The checkpoint key is `(thread_id=task_id, checkpoint_id=round_number)`.

### 7.2 DS-STAR State Schema

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
    # Schema versioning for checkpoint migration (see §7.6)
    schema_version: int = 1

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

### 7.3 DS-STAR Graph Definition

```
Nodes:
  analyzer      → Profiles files, produces D
  planner       → Generates plan step pₖ
  coder         → Generates complete script sₖ
  executor      → Runs sₖ via Sandbox Service; captures stdout/stderr/exit_code
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

### 7.4 Round Budget Logic

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

### 7.5 DS-STAR+ Graph Definition

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

### 7.6 Checkpoint Recovery

LangGraph checkpoints after every node. On worker crash:

1. Celery's task retry mechanism detects the dead worker (heartbeat timeout: 60 s).
2. Task is re-queued at **high priority** (ahead of new submissions).
3. New worker picks up the task; calls `graph.get_state(thread_id=task_id)` to find last checkpoint.
4. Graph resumes from the last completed node — no rounds are replayed.
5. WS event `checkpoint_recovery` is emitted to the frontend: "Recovered from checkpoint at Round N."

### 7.7 Checkpoint Schema Migration

When `DSStarState` schema changes between deployments, in-flight checkpoints may be incompatible. Strategy:

1. `DSStarState` carries a `schema_version: int` field (current: 1).
2. On graph load, after `graph.get_state()`, compare `state.schema_version` against the current schema version constant (`CURRENT_SCHEMA_VERSION = 1` in `backend/agents/state.py`).
3. If versions differ, run the registered migration function before resuming:

```python
MIGRATIONS: dict[tuple[int, int], Callable[[dict], dict]] = {
    (1, 2): migrate_v1_to_v2,   # Example: added steering_hint_ids field in v2
}

def migrate_state(raw: dict, from_version: int, to_version: int) -> dict:
    for v in range(from_version, to_version):
        raw = MIGRATIONS[(v, v + 1)](raw)
    return raw
```

4. Migration functions are pure data transformations (add missing fields with defaults, rename keys).
5. **Deployment rule:** Migrations must be backwards-compatible for one release cycle. Never rename a field in a single release — add the new field first, deprecate the old one in the next.
6. If no migration exists for the version gap, the task is marked `failed` with error `"Checkpoint schema incompatible — re-submit query."` A WS event and audit log entry are emitted.

---

## 8. Agent Specifications

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

### 8.1 Analyzer

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

### 8.2 Query Clarity Agent

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

### 8.3 Planner

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

### 8.4 Coder

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
- For charts: output a JSON object with keys: type, title, x_label, y_label, data.
  Also render the chart using matplotlib and save as /tmp/<chart_name>.png at 150 DPI.
  (Both outputs are required: JSON for the interactive frontend, PNG for PDF/Word export)
- For Excel output: use openpyxl; write to /tmp/<filename>.xlsx
- Wrap all code in try/except; print informative error messages before raising
```

**Pre-installed libraries in sandbox:** `pandas`, `numpy`, `openpyxl`, `python-docx`, `PyPDF2`, `pdfplumber`, `beautifulsoup4`, `scipy`, `scikit-learn` (inference only, no training), `tabulate`, `jinja2`, `matplotlib`

**Script archive:** Every `sₖ` is stored in MinIO at `scripts/{task_id}/round_{k}.py`. Referenced by the audit log via `script_id`. The analyst can download any version from the result panel.

---

### 8.5 Executor

**Purpose:** Runs `sₖ` inside the task's Docker container via the Sandbox Service. Captures stdout, stderr, and exit code.

**Mechanism:**
```python
async def execute_round(task_id: str, script: str, round_number: int) -> ExecutionResult:
    # Call the Sandbox Service (separate pod) via mTLS HTTP
    response = await sandbox_client.post(
        f"/sandbox/{task_id}/exec",
        json={"script": script, "round": round_number, "timeout": EXECUTION_TIMEOUT_SECONDS}
    )
    result = ExecutionResult(**response.json())

    # Cap outputs
    stdout = result.stdout[:10_240]   # 10 KB hard cap
    stderr = result.stderr[:2_048]    # 2 KB cap

    return ExecutionResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr,
        files_written=result.files_written  # /tmp files copied to MinIO by Sandbox Service
    )
```

**stdout_preview PII masking:** The `stdout` field returned here is used in:
1. `RoundResult.stdout` — stored in LangGraph state and passed to subsequent agents.
2. `round_complete` WebSocket event — streamed to the analyst's browser as `stdout_preview`.

**Path (2) bypasses the Finalizer's PII masking layer.** To prevent raw PII from reaching the browser in intermediate rounds, the Executor applies a lightweight regex mask before populating `stdout_preview` for the WS event:

```python
PII_PATTERNS = [
    (r'\b[A-Z]{2}\d{6,9}\b', '[ACCOUNT]'),       # UAE account number pattern
    (r'\b784-\d{4}-\d{7}-\d\b', '[NATIONAL_ID]'), # UAE national ID
    (r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]{0,16})?\b', '[IBAN]'),
]

def mask_for_preview(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text[:500]  # Preview capped at 500 chars
```

The full unmasked `stdout` is preserved in `RoundResult.stdout` for agent consumption. The masked, truncated version is what appears in the WS `stdout_preview` field.

**File output handling:** After each round, the Sandbox Service scans `/tmp` for new files and copies them to MinIO at `outputs/{task_id}/round_{k}/`. The Finalizer retrieves these for report assembly.

---

### 8.6 Debugger

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

### 8.7 Verifier

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

### 8.8 Router

**Purpose:** Decides whether to add a step or backtrack to a prior step.

**Input:** `(q_mapped, D, p₀..pₖ, rₖ)`

**Output:** Either `"add_step"` or an integer `l ∈ {1,...,k}` (backtrack index)

**Decision semantics:**
- `"add_step"`: The plan direction is correct but incomplete — continue forward
- Integer `l`: Step `pₗ` was erroneous — truncate plan to `{p₀..pₗ₋₁}` and have Planner regenerate `pₗ`

**On backtrack:** `state.plan` is sliced to `plan[:l]`. All truncated steps are marked `"truncated"` in the audit log (not deleted). The Planner regenerates from the truncated plan. The Coder does NOT receive `sₖ₋₁` after a backtrack — it works from the truncated plan only (from Q6).

---

### 8.9 Finalizer

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
  "chart_png_keys": ["outputs/task-123/final/chart_fraud_rate.png"],
  "files": ["fraud_analysis_abc.xlsx"],
  "is_complete": true,
  "incomplete_summary": null
}
```

**Explainer layer (CBUAE addition):** After the Finalizer, a separate Explainer agent converts technical output into plain English for non-technical analysts. Example:
> "ABC Bank's card fraud loss rate is 0.18% of transaction volume — 3.2× the peer median of 0.056%. The dominant fraud type is social engineering (61%), concentrated in the mobile banking channel (78% of losses)."

The Explainer output is displayed as the first paragraph of the result. The full Finalizer output (tables, charts) follows.

---

### 8.10 Sub-Question Generator (DS-STAR+ only)

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

### 8.11 Report Writer (DS-STAR+ only)

**Purpose:** Synthesises a cited, structured report from the evidence set `{(sqᵢ, aᵢ, sᵢ)}`.

**Input:** `(q_open, evidence_set, R_prior)` — `R_prior` is `None` on first pass; the partial report on refinement passes

**Output:** Markdown document with fixed structure:
```
# [Report Title]
**Date:** | **Analyst:** | **Classification:** INTERNAL

## Executive Summary
...inline citations: (Source: Sub-question 2 — Card fraud by LFI)...

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

**LLM used:** The highest-quality available model in the provider adapter (configured separately from the Flash-tier agents). In development: Gemini 2.5 Pro. In production: largest available local model (OQ-7 dependent).

---

## 9. Docker Sandbox

### 9.1 Sandbox Service Architecture

The Docker daemon is NOT accessible directly from Celery worker pods. Workers call a dedicated **Sandbox Service** pod over mTLS HTTP. This avoids the Docker socket security antipattern (mounting `/var/run/docker.sock` into a worker pod grants that pod root on the host node).

```
Celery Worker Pod          Sandbox Service Pod
┌──────────────┐           ┌──────────────────────────┐
│ LangGraph    │  mTLS     │ FastAPI (sandbox API)     │
│ Executor     │──────────►│                           │
│ node         │◄──────────│ SandboxManager            │
└──────────────┘           │   (Docker SDK)            │
                           │                           │
                           │ Mounted: /var/run/docker.sock
                           │ (only this pod has access) │
                           └──────────────────────────┘
```

**Sandbox Service API:**
```
POST /sandbox/{task_id}/start        — Create container; mount data paths
POST /sandbox/{task_id}/exec         — Run script; returns stdout/stderr/exit_code/files
POST /sandbox/{task_id}/stop         — Destroy container
GET  /sandbox/{task_id}/files        — List /tmp output files
POST /sandbox/{task_id}/files/copy   — Copy /tmp files to MinIO
GET  /sandbox/health                 — Active container count, capacity
```

**Kubernetes:** Sandbox Service runs as a `Deployment` (not `DaemonSet`). The Docker socket is mounted only into this deployment's pods. Worker pods have no host mounts.

### 9.2 Container Lifecycle

```
Task submitted → Sandbox Service creates container → Rounds execute via exec → Task ends → Container destroyed

Per-task: 1 container
Per-round: docker exec (no container restart)
DS-STAR+: 1 container per sub-question (sub-questions don't share state)
```

### 9.3 Container Specification

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
    jinja2==3.1.* matplotlib==3.9.*

# No network tools, no curl, no wget, no git
```

### 9.4 Security Constraints

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

### 9.5 Execution Timeout

Per-round execution timeout: **120 seconds** (configurable via `SANDBOX_EXEC_TIMEOUT_SECONDS`). If exceeded: process killed, `exit_code = 124` (timeout), stderr set to `"Execution timed out after 120 seconds."`. This round is treated identically to any other non-zero exit code — Debugger attempts to fix the script (likely by adding chunked reading or reducing data size).

### 9.6 Container Manager

```python
class SandboxManager:
    """Manages per-task Docker containers. Thread-safe. Called only from Sandbox Service."""

    async def start(self, task_id: str, data_paths: list[str]) -> str:
        """Start container for task. Returns container_id."""

    async def execute(self, task_id: str, script: str, timeout: int) -> ExecutionResult:
        """Run script via docker exec. Returns stdout, stderr, exit_code."""

    async def copy_outputs(self, task_id: str, round_number: int) -> list[str]:
        """Copy /tmp/* from container to MinIO. Returns MinIO keys."""

    async def stop(self, task_id: str) -> None:
        """Stop and remove container. Called on task complete/failed/stopped."""

    async def cleanup_orphans(self) -> None:
        """Called on Sandbox Service startup. Removes containers from crashed prior instances."""
```

---

## 10. LLM Provider Adapter

### 10.1 Interface

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

### 10.2 Implementations

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

### 10.3 Configuration

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

## 11. Database Schema

**Engine:** PostgreSQL 16. All tables use `UUID` primary keys. Timestamps are `TIMESTAMPTZ` (UTC). No soft-deletes — records are immutable once created (append-only audit design).

**Schema migrations:** Managed by Alembic. Migration scripts live in `backend/migrations/versions/`. Zero-downtime migration rules: new columns must be `NULLABLE` or have a `DEFAULT`; no column renames in a single release; no table drops without a deprecation cycle. See §21.4 for migration deployment procedure.

### 11.1 Schema: Users & RBAC

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

### 11.2 Schema: Files & Datasets

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

### 11.3 Schema: Tasks

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

### 11.4 Schema: Audit Log

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
CREATE INDEX idx_audit_log_payload ON audit_log USING gin(payload);
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
| `task.soft_time_limit` | 65-minute soft limit hit | task_id, round_number, status_at_limit |
| `result.exported` | Export downloaded | task_id, format, user_id |
| `result.reformatted` | Reformat triggered | task_id, new_instruction |
| `result.feedback` | Thumbs up/down | task_id, rating, comment |
| `result.flagged` | Flag as incorrect | task_id, description |
| `audit.queried` | Admin queries audit log | querying_user_id, filters_applied |
| `audit.integrity_checked` | Chain integrity verified | run_by_user_id, result (intact/broken_at) |
| `file.uploaded` | File upload completes | dataset_id, file_name, file_size |
| `file.profiled` | Analyzer completes profiling | dataset_id, schema_type_detected |
| `session.login` | Successful login | user_id |
| `session.logout` | Logout or token expiry | user_id |
| `config.updated` | Admin changes system config | key, old_value, new_value, changed_by |

### 11.5 Schema: Data Snapshots

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

### 11.6 Schema: Admin & Config

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

-- Append-only config history. Never UPDATE; always INSERT a new record.
-- Current value is the record with the highest id for a given key.
CREATE TABLE system_config (
    id          BIGSERIAL PRIMARY KEY,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    changed_by  UUID REFERENCES users(id),
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_system_config_key ON system_config(key, id DESC);

-- Current value query: SELECT DISTINCT ON (key) * FROM system_config ORDER BY key, id DESC;

-- Seed default config
INSERT INTO system_config (key, value) VALUES
    ('file_upload_enabled', 'true'),
    ('max_concurrent_insight_tasks', '5'),
    ('max_concurrent_research_tasks', '3'),
    ('max_concurrent_containers', '8');
```

**Config change rule:** The `PATCH /api/v1/admin/config` endpoint always INSERTs a new row and emits a `config.updated` audit event. Direct `UPDATE` on `system_config` is never performed. This provides a full config change history without a separate audit table.

---

## 12. File Storage

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

## 13. Task Queue

### 13.1 Celery Configuration

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
    "task_soft_time_limit": 3900,     # 65 min soft limit → raises SoftTimeLimitExceeded
    "task_time_limit": 4200,          # 70 min hard limit → SIGKILL
}
```

**Soft time limit handling:** When `SoftTimeLimitExceeded` is raised at 65 minutes, the Celery task catches it and:
1. Sets `task.status = "incomplete"` in the database.
2. Emits WS event `task_soft_time_limit` to the analyst: "Analysis reached the 65-minute limit. Results so far are available."
3. Writes a `task.soft_time_limit` audit log entry.
4. Runs the Finalizer on the last available round result (best-effort).
5. Acknowledges the Celery task (does not retry — analyst can re-submit if needed).

### 13.2 Priority Queue

```python
# Two queues: high priority for Insight, lower for Research
CELERY_TASK_ROUTES = {
    "workers.tasks.run_insight_task": {"queue": "insight"},
    "workers.tasks.run_research_task": {"queue": "research"},
}

# Worker startup: drain insight queue preferentially
# celery -A backend.celery worker -Q insight,research --concurrency=8
```

### 13.3 Concurrency Budget Enforcement

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

### 13.4 Dead-Letter Queue

```python
# DLQ Celery queue for permanently failed tasks
@celery.task(bind=True, max_retries=2, default_retry_delay=30)
def run_insight_task(self, task_id: str):
    try:
        run_dsstar(task_id)
    except SoftTimeLimitExceeded:
        handle_soft_limit(task_id)      # Best-effort finalisation; does not retry
    except Exception as exc:
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            move_to_dlq(task_id, str(exc))
            notify_admin_dlq(task_id)
```

DLQ items appear in the admin health dashboard (FR-ADMIN-05) with task ID, error summary, and timestamp. Admin can trigger manual retry.

---

## 14. REST API

**Base URL:** `/api/v1`  
**Auth:** All endpoints except `/auth/*` require `Authorization: Bearer <JWT>`.  
**Content-Type:** `application/json` unless noted.

### 14.1 Authentication

```
POST   /api/v1/auth/login
       Body: { "email": str, "password": str }
       Returns: { "access_token": str, "expires_in": 28800, "user": UserDTO }

POST   /api/v1/auth/logout
       Invalidates token (server-side token blocklist in Redis)

GET    /api/v1/auth/me
       Returns current user profile and department
```

### 14.2 Tasks (Core)

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

### 14.3 Datasets

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

### 14.4 Exports

```
GET    /api/v1/tasks/{id}/export/docx
GET    /api/v1/tasks/{id}/export/pdf
GET    /api/v1/tasks/{id}/export/xlsx
       Content-Type: application/octet-stream
       Content-Disposition: attachment; filename="FIP_{date}_{slug}.{ext}"
       Streams file from MinIO through API server.
       Audit log event: result.exported
```

### 14.5 Admin

```
GET    /api/v1/admin/users
POST   /api/v1/admin/users
PATCH  /api/v1/admin/users/{id}          # deactivate, change dept
GET    /api/v1/admin/audit-log           # Query params: user_id, dept, date_from, date_to, event_type, query_text, page
GET    /api/v1/admin/audit-log/export    # Returns CSV
POST   /api/v1/admin/audit-log/verify-integrity  # Returns IntegrityReport; logs audit.integrity_checked
GET    /api/v1/admin/health              # Real-time: queue depth, active tasks, GPU util, error rate, DLQ count
GET    /api/v1/admin/dlq                 # List DLQ items
POST   /api/v1/admin/dlq/{id}/retry     # Manual retry
GET    /api/v1/admin/templates           # Query templates list
POST   /api/v1/admin/templates
PATCH  /api/v1/admin/templates/{id}
DELETE /api/v1/admin/templates/{id}
GET    /api/v1/admin/config              # Returns current value per key (latest row per key)
PATCH  /api/v1/admin/config             # Body: { "key": str, "value": str }; INSERTs new row; emits config.updated
```

### 14.6 Error Response Format

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

## 15. WebSocket

**Endpoint:** `WSS /ws/tasks/{task_id}`  
**Auth:** JWT passed as query parameter `?token=<JWT>` on connection (standard WS limitation — no custom headers).  
**Protocol:** JSON messages only.

### 15.1 Server → Client Events

```typescript
type WSEvent =
  | { type: "task_queued";            data: { queue_position: number; estimated_wait_minutes: number } }
  | { type: "task_started";           data: { started_at: string } }
  | { type: "analyzer_complete";      data: { files_profiled: number; descriptions: FileDescription[] } }
  | { type: "round_started";          data: { round: number; max_rounds: number; plan_step: string } }
  | { type: "round_complete";         data: { round: number; verifier_verdict: "Yes"|"No"; router_decision: string; stdout_preview: string } }
  //  ^ stdout_preview: PII-masked (regex pass) and capped at 500 chars before sending — see §8.5
  | { type: "debug_attempt";          data: { round: number; attempt: number; error_type: string } }
  | { type: "task_paused";            data: { paused_at_round: number; checkpoint_expires_at: string } }
  | { type: "round_cap_reached";      data: { round: number; hard_cap: number } }
  | { type: "task_soft_time_limit";   data: { round: number; message: string } }
  | { type: "task_complete";          data: { result: FIPResult; is_complete: boolean } }
  | { type: "task_failed";            data: { error_summary: string } }
  | { type: "task_stopped";           data: {} }
  | { type: "checkpoint_recovery";    data: { recovered_from_round: number } }
  | { type: "queue_position_update";  data: { position: number; estimated_wait_minutes: number } }
  // DS-STAR+ only:
  | { type: "subquestions_generated"; data: { sub_questions: string[]; count: number } }
  | { type: "subquestion_started";    data: { index: number; total: number; question: string } }
  | { type: "subquestion_complete";   data: { index: number; answer_preview: string } }
  | { type: "report_writing_started"; data: {} }
  | { type: "refinement_round";       data: { k: number; new_subquestions: string[] } }
  | { type: "report_complete";        data: { result: FIPResearchResult } }
```

### 15.2 Client → Server Events

```typescript
type WSClientEvent =
  | { type: "hint";   data: { hint_text: string } }
  | { type: "pause";  data: {} }
  | { type: "stop";   data: {} }
  | { type: "extend"; data: {} }
```

### 15.3 Connection Management

- Connection is kept alive for the duration of the task.
- Server sends a `ping` frame every 30 seconds; client must respond with `pong`.
- On disconnect (JWT expired, browser tab closed), the task continues running. The analyst reconnects and receives the current state via `GET /api/v1/tasks/{id}` on reconnect; WS reconnects and resumes streaming.
- Max 2 concurrent WS connections per task (allows analyst to open on two browser tabs).

---

## 16. Frontend Architecture

### 16.1 Application Structure

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

### 16.2 Key Component Behaviours

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
- Expanded (full trace): current agent, round counter `N / max`, last stdout preview (truncated 500 chars, PII-masked by server), steering hints list
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

### 16.3 State Management

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

### 16.4 Routing

```typescript
// React Router v6
/login            → <Login />              (public)
/chat             → <Chat />               (auth required)
/dashboard        → <Dashboard />          (auth required)
/dashboard?task=X → <Dashboard /> with task pre-loaded
/admin            → <Admin />              (admin role required; 403 page for analysts)
```

---

## 17. Report Generation

### 17.1 Pipeline

```
FIP Result JSON
      │
      ▼
Report Writer (LangGraph node)
      │ Produces: Markdown document + chart references + table data
      ▼
Jinja2 Template Engine (python-docx-template)
      │ Merges content into .docx template; embeds chart PNGs (see §17.3)
      ▼
.docx file → MinIO (fip-reports/)
      │
      ├──────────────────────────────────────► .docx download
      │
      ▼
LibreOffice headless (subprocess call, 60s timeout)
      │ libreoffice --headless --convert-to pdf
      │ On timeout or error: serve .docx with inline warning (see §17.2)
      ▼
.pdf file → MinIO (fip-reports/)
      │
      ▼
Excel export (separate path):
      openpyxl → one sheet per table → charts as embedded PNG images
      .xlsx file → MinIO (fip-reports/)
```

### 17.2 LibreOffice Failure Handling

LibreOffice headless is invoked via `subprocess.run()` with a hard timeout:

```python
async def convert_docx_to_pdf(docx_path: str, output_dir: str) -> str | None:
    try:
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, docx_path],
            timeout=60,          # Hard timeout: 60 seconds
            capture_output=True,
            check=True
        )
        return result.stdout  # Path to generated PDF
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice PDF conversion timed out for %s", docx_path)
        return None
    except subprocess.CalledProcessError as e:
        logger.error("LibreOffice conversion failed: %s", e.stderr)
        return None
```

**Fallback:** If conversion returns `None`, the export endpoint serves the `.docx` file with HTTP header `X-FIP-Warning: PDF conversion failed; DOCX provided instead`. The frontend displays an inline notice: "PDF generation failed — download the Word file instead."

**Health check:** The Sandbox Service checks LibreOffice availability at startup by converting a test file. If the check fails, it logs a critical error and prevents pod readiness (Kubernetes readiness probe fails until resolved).

### 17.3 Chart Rendering for Exports

**Decision (V1): Server-side matplotlib rendering only.**

The Coder is instructed (§8.4 system prompt) to output both a chart JSON object and a matplotlib PNG at `/tmp/<chart_name>.png`. The Sandbox Service copies PNGs to MinIO alongside the script outputs. The Finalizer embeds the PNG files into the `.docx` via `python-docx-template`.

This approach is reliable regardless of whether the analyst's browser tab is open — exports triggered hours later (from query history) work correctly. The Recharts frontend still renders from the chart JSON for the interactive view; the matplotlib PNGs are used exclusively for Word/PDF/Excel exports.

**Interactive vs. export rendering:**

| Context | Rendering | Source |
|---------|-----------|--------|
| Browser result panel | Recharts (interactive) | Chart JSON from Coder |
| Word/PDF export | matplotlib PNG (300 DPI) | PNG from sandbox /tmp |
| Excel export | openpyxl chart + PNG | PNG embedded via openpyxl |

### 17.4 Word Template System

System default template (`fip-templates/default.docx`) contains:
- CBUAE letterhead and classification banner
- Jinja2 placeholders: `{{ title }}`, `{{ date }}`, `{{ analyst_name }}`, `{{ department }}`, `{{ executive_summary }}`, `{{ methodology }}`, `{{ findings_sections }}`, `{{ recommendations }}`
- Footer: classification, page numbers, "Generated by FIP — AI-assisted analysis. Verify before use."

Analyst custom templates (FR-OUT-07) follow the same placeholder schema. Validation: on upload, check that at least one recognised placeholder is present; reject with error if none found.

---

## 18. Authentication & RBAC

> **`[PENDING OQ-1]`** — The auth mechanism depends on whether CBUAE has Active Directory / SSO. The design below covers the standalone JWT approach. If OQ-1 confirms AD/SSO, §18.1 is replaced with OIDC/SAML integration; §18.2–18.4 remain unchanged.

### 18.1 JWT Authentication (Standalone — current design)

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

### 18.2 RBAC Enforcement

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

### 18.3 Admin vs Analyst Separation

Admin page is served at a separate path (`/admin`). A non-admin JWT hitting any `/api/v1/admin/*` endpoint receives `403` — no redirect to login. Admin accounts are created by other admins; they cannot self-register. Admin and analyst roles are mutually exclusive in `users.role`.

### 18.4 Password Policy (Standalone auth only)

- Minimum 12 characters; at least one uppercase, one lowercase, one number, one symbol
- Stored as bcrypt hash (cost factor 12)
- Forced password change on first login
- No password reset via email in V1 (no email system) — admin resets via `PATCH /api/v1/admin/users/{id}`

---

## 19. Audit Log

### 19.1 Write Path — Concurrency-Safe Design

The audit log must maintain a valid hash chain under concurrent writes from multiple tasks running simultaneously. A naive read-then-insert pattern creates a race: two concurrent tasks both read the same `prev_hash`, compute two different hashes from it, and insert records that both claim the same `prev_record` as parent — breaking the chain.

**Resolution: Single-writer async queue.** All audit writes are serialized through a single asyncio coroutine within each API/worker process. Multiple concurrent tasks enqueue their entries; the writer processes them strictly in order.

```python
class AuditLogger:
    """
    All audit writes serialized through a single asyncio.Queue.
    At most one INSERT is in flight at any time — eliminates hash-chain concurrency race.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._queue: asyncio.Queue[AuditEntry] = asyncio.Queue()
        self._writer_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Called at application startup. Spawns the writer coroutine."""
        self._writer_task = asyncio.create_task(self._writer_loop())

    async def stop(self) -> None:
        """Called at shutdown. Drains the queue before stopping."""
        await self._queue.join()
        if self._writer_task:
            self._writer_task.cancel()

    async def log(
        self,
        event_type: str,
        task_id: UUID | None,
        user_id: UUID | None,
        department_id: UUID | None,
        payload: dict,
    ) -> None:
        """Enqueue an audit entry. Returns immediately; write is async."""
        entry = AuditEntry(
            event_type=event_type,
            task_id=task_id,
            user_id=user_id,
            department_id=department_id,
            payload=payload,
        )
        await self._queue.put(entry)

    async def _writer_loop(self) -> None:
        while True:
            entry = await self._queue.get()
            try:
                await self._write_to_db(entry)
            except Exception as exc:
                # Audit write failures are critical — log to stderr and structured log.
                # Do NOT crash the writer loop; remaining entries must still be written.
                logger.critical("AUDIT WRITE FAILED: %s | entry: %s", exc, entry)
            finally:
                self._queue.task_done()

    async def _write_to_db(self, entry: AuditEntry) -> None:
        prev_record = await self._get_last_record()
        prev_hash = prev_record.entry_hash if prev_record else "0" * 64

        entry_data = json.dumps({
            "event_type": entry.event_type,
            "task_id": str(entry.task_id),
            "user_id": str(entry.user_id),
            "payload": entry.payload,
            "created_at": now_utc().isoformat(),
        }, sort_keys=True)

        entry_hash = sha256(f"{prev_hash}{entry_data}".encode()).hexdigest()

        await self._insert(
            entry_hash=entry_hash,
            prev_hash=prev_hash,
            event_type=entry.event_type,
            task_id=entry.task_id,
            user_id=entry.user_id,
            department_id=entry.department_id,
            payload=entry.payload,
        )
```

**One `AuditLogger` instance per process.** The FastAPI application and each Celery worker each maintain their own `AuditLogger` instance. Inter-process concurrency is handled by the `BIGSERIAL` primary key: each process's writer loop reads `SELECT MAX(id)` as its `prev_record`. Sequential inserts from different processes may occasionally read the same `MAX(id)` if they overlap at the millisecond level. The asyncio queue eliminates intra-process races; inter-process races are detected at integrity-check time.

**For production-grade integrity guarantees across multiple worker processes**, the `_write_to_db` method uses a PostgreSQL advisory lock:

```python
async def _write_to_db(self, entry: AuditEntry) -> None:
    async with self._db.begin():
        # Lock key 42 is the audit log writer lock — single global lock across all processes
        await self._db.execute(text("SELECT pg_advisory_xact_lock(42)"))
        prev_record = await self._get_last_record()
        # ... rest of write logic ...
        await self._insert(...)
    # Lock released automatically on transaction commit
```

The advisory lock serializes across processes. Lock contention is acceptable: audit writes are low-frequency (< 10/second) and the lock is held for < 1 ms per write.

### 19.2 Tamper Detection

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

**Scale consideration:** `verify_chain_integrity()` performs a full sequential scan. At ~20 events/task × 100 tasks/day × 365 days ≈ 730,000 records in year one. At year three: ~2.2M records. The scan is read-only and runs on the replica — it does not block production writes. Expected runtime at 2M records: < 60 seconds.

**Scheduled check:** Run nightly via a Celery Beat task at 02:00. Results logged as `audit.integrity_checked` event. Admin dashboard shows last check timestamp and result.

**Exposed as:** `POST /api/v1/admin/audit-log/verify-integrity` — returns `IntegrityReport`. The action of running this check is itself logged to the audit log.

---

## 20. Data Versioning & Snapshots

Every time an analyst confirms dataset selection and starts a task, the system creates a point-in-time snapshot of each selected file. This ensures that even if the underlying file is updated or deleted, the result of the analysis remains verifiable against the exact data that produced it.

### 20.1 Snapshot Creation

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

### 20.2 Snapshot Access Control

- **Analysts:** Can view snapshot metadata (file name, snapshot ID, timestamp, row count) for their own tasks via the "Data sources used" panel. Cannot download snapshot files directly. Cannot access other analysts' snapshots.
- **Admin:** Full access to any snapshot by task ID. `GET /api/v1/admin/tasks/{id}/snapshots/{snapshot_id}/download` streams the snapshot file. Logged in audit log.
- **No deletion:** Snapshots are never deleted. No retention policy in V1. Storage growth monitored in admin health dashboard.

---

## 21. Deployment Architecture

> **`[PENDING OQ-7]`** — GPU hardware specs (model, VRAM, count) unknown. The deployment topology below assumes a minimum viable on-premise server cluster. Actual node counts, GPU allocation, and inference throughput must be validated against OQ-7 before the TDD is finalised.

### 21.1 Assumed Server Topology (to be confirmed)

```
Node 1 — Web / API server
  - Nginx (TLS termination, reverse proxy)
  - FastAPI application server (Gunicorn + Uvicorn workers: 4)
  - Redis Sentinel node 1

Node 2 — Worker server A
  - Celery worker (concurrency: 4)
  - Sandbox Service pod (owns Docker daemon)
  - Redis Sentinel node 2

Node 3 — Worker server B
  - Celery worker (concurrency: 4)
  - Sandbox Service pod (owns Docker daemon)
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

### 21.2 Container Orchestration

**V1 target:** Kubernetes (K8s) on bare metal. Docker Compose provided for development only.

Kubernetes resources:
- `Deployment`: api-server, celery-worker, nginx, sandbox-service
- `StatefulSet`: postgresql, redis-sentinel (3 replicas), minio
- `ConfigMap`: Non-secret config
- `Secret`: References to Vault paths (Vault Agent Injector pattern — secrets mounted as files, not env vars)
- `PersistentVolumeClaim`: PostgreSQL data, MinIO data, sandbox data mount

**Docker socket access:** Only the `sandbox-service` Deployment mounts the host Docker socket (`/var/run/docker.sock`). The `celery-worker` Deployment has no host mounts. This is enforced via Kubernetes `PodSecurityPolicy` (or OPA Gatekeeper rule) that rejects `hostPath` mounts on pods not in the `sandbox` service account.

**No Helm chart in V1.** Plain Kubernetes YAML manifests in `infrastructure/k8s/`. This keeps the deployment understandable by CBUAE IT without Helm expertise.

### 21.3 Air-Gap Verification

Before launch, the following must pass (from FR Launch Criteria §11):
```bash
# From every node: all outbound connections must fail
curl --max-time 5 https://api.anthropic.com  # Must fail
curl --max-time 5 https://generativelanguage.googleapis.com  # Must fail
curl --max-time 5 https://registry.npmjs.org  # Must fail
# ... etc. for all external endpoints
```

All container images must be pre-pulled into a private on-premise container registry (e.g., Harbor) during an internet-connected build phase, then the network connection is severed before production deployment.

### 21.4 Database Migration Procedure

Managed by Alembic. Migration files in `backend/migrations/versions/`.

**Zero-downtime migration rules:**
1. New columns: always `NULLABLE` or with a `DEFAULT` value — never block writes.
2. No column renames in a single release: add new column → backfill → update code → drop old column in the subsequent release.
3. No table drops without a full deprecation cycle (code no longer references the table for at least one release).
4. Index creation: use `CREATE INDEX CONCURRENTLY` to avoid table locks.

**Deployment procedure:**
```bash
# Run on each deployment, before starting new application pods
alembic upgrade head

# Verify migration applied
alembic current
```

Migrations run in the CI/CD pipeline before pods are updated. If migration fails, deployment is aborted and pods continue running the prior version.

### 21.5 Development / Staging Environment

**Local development:**
```bash
docker compose -f docker-compose.dev.yml up
# Starts: FastAPI, Celery worker, Redis, PostgreSQL, MinIO, Ollama (with a small model)
# Uses GeminiAdapter by default (set GEMINI_API_KEY in .env.local)
```

**Staging environment:**
- Mirrors production topology on a smaller scale (single worker node, no GPU — uses GeminiAdapter)
- Synthetic data only — no real CBUAE LFI data
- Deployed from the same Kubernetes manifests with `ENV=staging` overlay
- Accessible only from CBUAE internal network (same as production)

---

## 22. Performance Considerations

### 22.1 LLM Inference Latency

The dominant factor in task duration is LLM inference. Each round invokes 2–5 LLM calls (Planner, Coder, Verifier, and optionally Debugger + Router). At a local Flash model doing ~500 tokens/second, a round with ~1000 token output takes ~2 seconds per call → 4–10 seconds per round for agent calls alone.

**P95 targets (from PRD §9.1):**

| Scenario | Target | Key assumption |
|----------|--------|---------------|
| Insight, easy (≤3 rounds) | < 3 min | Flash inference at 500 tok/s |
| Insight, hard (≤10 rounds) | < 20 min | Flash inference at 500 tok/s |
| Research (7 sub-questions, K=1) | < 60 min | Sequential; Flash for agents, Pro for Writer |
| Reformat only | < 30 sec | Finalizer only; no pipeline re-run |

**[PENDING OQ-7]:** If local GPU inference is materially slower than assumed, these targets may not be achievable. Must benchmark actual inference throughput against real hardware before committing to targets.

### 22.2 Database Indexing

Critical indexes already defined in §11. Additional:

```sql
-- Admin search queries (partial text match on payload):
CREATE INDEX idx_audit_log_payload ON audit_log USING gin(payload);

-- Config current value lookup:
CREATE INDEX idx_system_config_key ON system_config(key, id DESC);
```

### 22.3 MinIO Storage Estimates

Conservative estimate per active analyst per month:
- Uploaded data: 500 MB average × 20 uploads = 10 GB
- Snapshots: ~10 GB (deduplication reduces this)
- Scripts: ~50 KB per task × 100 tasks = 5 MB
- Reports: ~2 MB per report × 50 reports = 100 MB

**Total per analyst per month:** ~20 GB. With 50 analysts: ~1 TB/month raw growth (before deduplication). MinIO cluster must be provisioned with at least 12 months of projected storage from day one.

---

## 23. Security Implementation

### 23.1 Secrets Management

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

### 23.2 mTLS Configuration

All service-to-service communication uses mutual TLS with certificates issued by an internal CA (managed by Vault PKI secrets engine). Certificate rotation: 30-day validity, auto-renewed 5 days before expiry.

```
Nginx → FastAPI:        mTLS, cert CN=api-server
FastAPI → Postgres:     mTLS, cert CN=api-server, verified against DB CA
FastAPI → MinIO:        mTLS, cert CN=api-server
FastAPI → Redis:        TLS (Redis does not support mTLS natively)
Worker → Sandbox Svc:   mTLS, cert CN=celery-worker
Worker → Postgres:      mTLS, cert CN=celery-worker
Worker → MinIO:         mTLS, cert CN=celery-worker
Worker → Ollama:        mTLS, cert CN=celery-worker
All → Vault:            mTLS + AppRole token
```

### 23.3 Input Sanitisation

**File upload:** Content-type validation at the API layer (reject if MIME type doesn't match extension). File content is never injected directly into LLM prompts — only the Analyzer's structured description `D` is passed. This prevents prompt injection via file content (Risk R4 in PRD §14).

**Query text:** Maximum 5,000 characters. HTML stripped server-side before storage. The query is not executed as code — it is passed to the LLM as plain text within a structured system prompt. Prompt injection risk is mitigated by the agent system prompts explicitly instructing agents to treat user input as data, not instruction.

**Sandbox:** See §9.4. The sandbox security profile is the primary mitigation for Risk R5.

### 23.4 Pen Test Scope (Pre-Launch Requirement)

Per PRD §11 Launch Criteria, the following must be covered by IT Security's penetration test:
- Sandbox escape via crafted Python script
- Prompt injection via uploaded PDF, Excel, or CSV content
- JWT tampering (algorithm confusion, signature bypass)
- RBAC bypass (cross-department dataset access, cross-analyst task access)
- MinIO direct access bypass (can analyst reach another analyst's files without API?)
- DoS via task flooding (concurrency budget enforcement)
- Audit log manipulation (can any role UPDATE or DELETE audit records?)
- Docker socket access (can a Celery worker pod reach the Docker daemon?)

---

## 24. Observability & Monitoring

### 24.1 Metrics

All services expose Prometheus metrics at `/metrics`. The following are emitted in addition to standard FastAPI/Celery/PostgreSQL metrics:

**Task metrics:**
```
fip_task_total{mode, status}                        — Counter: tasks by mode and terminal status
fip_task_duration_seconds{mode}                     — Histogram: end-to-end task duration
fip_task_rounds_total{mode}                         — Histogram: rounds used per completed task
fip_task_queue_depth{queue}                         — Gauge: waiting tasks (insight, research)
fip_task_active{mode}                               — Gauge: currently running tasks
```

**Agent / LLM metrics:**
```
fip_llm_latency_seconds{agent, model_tier}          — Histogram: LLM call latency per agent
fip_llm_tokens_total{agent, model_tier, direction}  — Counter: tokens in/out per agent (for cost tracking)
fip_agent_errors_total{agent, error_type}           — Counter: agent-level failures
fip_debug_attempts_total                            — Counter: Debugger invocations
fip_circuit_breaker_trips_total                     — Counter: circuit breaker firings
```

**Sandbox metrics:**
```
fip_sandbox_active_containers                       — Gauge: running containers
fip_sandbox_exec_duration_seconds                   — Histogram: per-round execution time
fip_sandbox_timeout_total                           — Counter: execution timeouts
fip_sandbox_exit_codes_total{exit_code}             — Counter: exit codes (0, 1, 124, etc.)
```

**Infrastructure metrics:**
```
fip_audit_log_write_latency_seconds                 — Histogram: audit INSERT latency
fip_audit_log_queue_depth                           — Gauge: pending audit entries
fip_checkpoint_recovery_total                       — Counter: LangGraph checkpoint recoveries
fip_dlq_depth                                       — Gauge: dead-letter queue depth
```

### 24.2 SLOs

| SLO | Target | Measurement |
|-----|--------|-------------|
| Insight task P95 completion | < 20 min | `fip_task_duration_seconds{mode="insight"}` p95 |
| API availability | > 99.5% per month | Nginx upstream error rate |
| Audit log write success rate | > 99.99% | `fip_audit_log_write_failures_total` / total writes |
| WS event delivery latency | < 500 ms P95 | Time from node completion to WS send |
| Sandbox success rate | > 95% (exit_code = 0 before Debugger) | `fip_sandbox_exit_codes_total{exit_code="0"}` |

**Error budget:** 99.5% monthly availability = 3.6 hours downtime budget per month. Any outage > 1 hour requires an incident review.

### 24.3 Dashboards (Grafana)

Five dashboards, deployed as Grafana JSON provisioning files in `infrastructure/grafana/`:

| Dashboard | Key panels |
|-----------|-----------|
| **Operations Overview** | Queue depths, active tasks/containers, DLQ depth, error rate (5 min), last integrity check result |
| **Task Latency** | P50/P95/P99 duration by mode; round count distribution; reformat latency |
| **LLM Inference** | Tokens/sec by model tier; latency heatmap by agent; token spend rate |
| **Error Analysis** | Failed tasks by error type; debug attempt rate; circuit breaker history; DLQ items |
| **Audit Log Health** | Write latency; queue depth; daily event counts by type; integrity check history |

### 24.4 Alerting Rules

All alerts fire to the ops team via the internal alert channel (no external webhook — air-gapped):

```yaml
alerts:
  - name: DLQNonEmpty
    condition: fip_dlq_depth > 0 for 5m
    severity: critical
    message: "Tasks in dead-letter queue — immediate attention required"

  - name: LLMHighLatency
    condition: fip_llm_latency_seconds{model_tier="flash"} p95 > 30s for 10m
    severity: warning
    message: "Ollama inference latency elevated — check GPU utilisation"

  - name: ContainerCapacityHigh
    condition: fip_sandbox_active_containers / 8 > 0.9 for 5m
    severity: warning
    message: "Sandbox container capacity > 90% — tasks may queue"

  - name: WorkerHeartbeatLost
    condition: celery_worker_heartbeat_age > 120s
    severity: critical
    message: "Celery worker unresponsive — task recovery may be needed"

  - name: AuditIntegrityFailed
    condition: last audit.integrity_checked result == "broken"
    severity: critical
    message: "AUDIT LOG CHAIN INTEGRITY BROKEN — security incident suspected"

  - name: APIErrorRateHigh
    condition: http_request_duration_seconds{status=~"5.."} rate(5m) > 0.05
    severity: warning
    message: "API 5xx error rate > 5% — investigate"
```

### 24.5 Health Endpoint

`GET /api/v1/admin/health` returns:
```json
{
  "queue_depth": { "insight": 3, "research": 1 },
  "active_tasks": { "insight": 4, "research": 2 },
  "active_containers": 6,
  "max_containers": 8,
  "dlq_depth": 0,
  "llm_status": "healthy",
  "llm_latency_p95_ms": 2100,
  "db_status": "healthy",
  "minio_status": "healthy",
  "vault_status": "healthy",
  "audit_log_last_integrity_check": "2026-07-01T02:00:00Z",
  "audit_log_integrity_intact": true,
  "uptime_seconds": 86400
}
```

`llm_status` is determined by a background health-check task that sends a minimal prompt to the configured LLM every 60 seconds and records success/failure.

---

## 25. Open Questions Tracker

| # | Question | Status | Blocks |
|---|----------|--------|--------|
| OQ-1 | Authentication system — Active Directory / SSO or standalone? | **OPEN** | §18 Auth design, JWT vs OIDC/SAML |
| OQ-2 | Largest single dataset an analyst would query (row count, GB) | **OPEN** | Executor memory limits, file upload UX, Analyzer timeout |
| OQ-3 | Existing Word/PDF report templates from FPS — samples available? | **OPEN** | §17 Report template design |
| OQ-4 | Integration with case management system (NICE Actimize, ServiceNow) in V1? | **OPEN** | API contract scope |
| OQ-5 | Data freshness requirement for institutional datasets | **OPEN** | Data ingestion pipeline (not in V1 scope but affects MinIO retention) |
| OQ-6 | Dataset access approval authority — who approves per-analyst dataset access? | **OPEN** | Admin panel workflow design |
| OQ-7 | On-premise GPU hardware (model, VRAM, count) | **OPEN — IMMEDIATE** | §21 Deployment topology, §22 Performance targets, LLM model selection, Ollama vs vLLM |
| OQ-8 | Expected peak concurrent analyst usage | **OPEN** | §13 Queue sizing, §21.1 node count |
| OQ-9 | Baseline metrics establishment (time studies for thematic review, benchmarking table) | **OPEN** | PRD §3 success metrics; does not block TDD |

**Resolution required before TDD is finalised:** OQ-1 (§18), OQ-7 (§21, §22)  
**Resolution required before build begins:** OQ-2, OQ-5, OQ-6, OQ-8  
**Resolution required before Closed Beta:** OQ-3, OQ-4, OQ-9

---

*This TDD is a living document. All changes must be reflected back into the PRD if they affect functional requirements. Architecture decisions that arise during build must be added to `00-discovery/04-architecture-decisions.md` before being implemented.*
