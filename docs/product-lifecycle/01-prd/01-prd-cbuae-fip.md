# Product Requirements Document
## CBUAE Financial Intelligence Platform (FIP) — V1

**Stage:** PRD — Stage 1  
**Branch:** `docs/product-lifecycle`  
**Date:** 2026-06-24  
**Author:** Fraud Prevention Supervision, CBUAE  
**DRI:** TBD  
**Status:** Draft  
**Prerequisite documents:**
- `00-discovery/01-paper-analysis.md` — DS-STAR paper deep-dive
- `00-discovery/02-one-pager.md` — 1-Pager / PRFAQ
- `00-discovery/03-requirements-discovery.md` — Requirements Q&A log
- `00-discovery/04-architecture-decisions.md` — Architecture decisions with paper references
- `00-discovery/05-feature-discussion.md` — Pre-PRD feature brainstorm (all 10 topics)
- `00-discovery/03-architecture-v2.html` — Architecture diagram v3.3

---

## 1. Problem Statement

Analysts across CBUAE's Financial Crime & Market Conduct departments work with rich, multi-file datasets — fraud loss reports submitted by licensed financial institutions (LFIs), SAR/STR databases, KYC records, consumer complaints, and market surveillance feeds. Extracting insights from this data today requires either writing Python or SQL code, or waiting for IT to build a custom report. Neither path is fast enough for supervision work.

The result:
- Supervisory decisions are made on incomplete or manually extracted data
- Thematic reviews that should take hours take weeks
- The analytical depth of supervisory letters is constrained by what a non-technical officer can produce in Excel
- Peer benchmarking across LFIs requires manual data wrangling that few analysts can do independently

---

## 2. Hypothesis

If a non-technical analyst could type a question in plain English — *"Which LFIs have the highest social engineering fraud rate relative to their transaction volume?"* — and receive a clear, cited, data-backed answer in minutes, the quality and speed of supervisory work would materially improve.

This is now technically feasible. Google's DS-STAR paper (arXiv:2509.21825, 2025) demonstrated that a structured multi-agent pipeline can autonomously plan, code, execute, verify, and iterate over complex multi-file datasets with no human involvement between question and answer. On hard analytical tasks, it outperforms a frontier LLM used alone by 32 percentage points.

---

## 3. What We Are Building

The **Financial Intelligence Platform (FIP)** is a CBUAE-internal analytics system built on the DS-STAR and DS-STAR+ multi-agent architecture, adapted for the Financial Crime & Market Conduct vertical. It accepts natural language queries from non-technical analysts and returns data-backed answers and reports — with full traceability from question to code to result.

The system operates in two modes:

### FIP-Insight (DS-STAR mode)
For specific, factoid, or multi-step analytical questions. The analyst types a question; the system plans, codes, executes, verifies, and iterates autonomously until it produces a sufficient answer. Output is a chat-style response: a concise executive summary with supporting tables and interactive charts.

**Example queries:**
- "Which LFIs have the highest card fraud loss rate in Q1 2025 vs. the peer median?"
- "Show me fraud typology trends across UAE banks over the last 12 months."
- "Which LFIs are statistical outliers in their social engineering fraud detection rate?"

### FIP-Research (DS-STAR+ mode)
For open-ended research topics and thematic analysis. The system decomposes the topic into focused sub-questions, answers each independently using the DS-STAR inner engine, then synthesises a cited, structured report. Output is a formal document — structured sections, every claim cited to the sub-question and code that produced it.

**Example queries:**
- "Generate a thematic analysis of APP fraud growth across UAE banks in 2024."
- "Produce a sector-wide fraud trend report for H1 2025, suitable for a supervisory letter annex."
- "Create an evidence data summary for our enforcement case against LFI X."

---

## 4. Goals & Success Metrics

| Metric | Baseline (Today) | Target (12 months post-launch) |
|--------|-----------------|-------------------------------|
| Time to produce a peer benchmarking table | 3–5 days (manual Excel) | < 15 minutes |
| Time to produce a thematic review report | 4–8 weeks | < 2 days |
| % of supervisory queries answered same-day | ~20% | > 80% |
| Analyst satisfaction with data access | TBD (baseline survey) | > 4.0 / 5.0 |
| Number of thematic reviews completed per year | TBD (baseline) | 2× current |

---

## 5. Non-Goals (What This Is Not)

- **Not a replacement for human judgement.** The system provides analysis; the analyst interprets and decides. No supervisory action is taken by the system.
- **Not a real-time alert engine.** FIP is a supervisory analytics tool, not a transaction monitoring or AML screening system.
- **Not a customer-facing product.** Internal CBUAE use only. On-premise. Air-gapped.
- **Not a replacement for LFI fraud systems.** CBUAE oversees LFIs; this tool helps CBUAE do that better.
- **Not a live database connector in V1.** Data access in V1 is file upload only. Live database connectivity is future scope.

---

## 6. Target Users

**All five departments under CBUAE Financial Crime & Market Conduct.** The primary initiating department is Fraud Prevention Supervision.

**V1 treats all analysts identically regardless of department.** No department-specific UI, templates, or workflows in V1. Department-specific customisation is future scope.

| Department | Role | Representative Queries |
|------------|------|----------------------|
| **Fraud Prevention Supervision** ⭐ | Supervises LFI fraud prevention frameworks; benchmarks fraud loss data | "Which LFIs have the highest card fraud loss rate vs. peer median?", "Show fraud typology trends by LFI over 12 months" |
| **AML / CFT Supervision** | Supervises LFI AML/CFT compliance obligations | "Which LFIs have declining STR filing rates?", "Show typology distribution vs. FATF benchmarks" |
| **Market Conduct & FCPS** | Monitors consumer complaints, market behaviour, mis-selling | "Show complaint volumes by LFI and product category", "Identify potential mis-selling patterns" |
| **Enforcement** | Takes regulatory action against violations | "Pull all fraud loss data for LFI X across 3 years", "Generate an evidence summary for case #XXXX" |
| **Policy & Research** | Develops regulatory frameworks; conducts sector-wide research | "What is the UAE-wide fraud loss trend by channel?", "Compare UAE fraud rates against GCC benchmarks" |

**User persona:** Non-technical. Analysts understand the domain deeply (regulatory frameworks, LFI behaviour, financial crime typologies) but cannot write Python or SQL. They rely on technical colleagues or manual Excel for data analysis today.

---

## 7. Deployment & Infrastructure

- **Deployment model:** On-premise only. Fully air-gapped. No data leaves CBUAE infrastructure. No API calls to external services. No cloud components.
- **LLM inference:** Local model deployment via Ollama or vLLM. Provider-agnostic adapter — switching LLM providers requires only a config file change, zero agent code changes. Actual model procured and deployed is a CBUAE IT decision.
- **Frontend/backend separation:** React frontend on a separate server. Backend built on LangGraph Server, exposing HTTP and WebSocket endpoints.
- **Authentication:** JWT tokens. Analysts authenticate via login screen; every API call from the browser carries a signed JWT. Analyst and Admin are completely separate login URLs.

---

## 8. Functional Requirements

### 8.1 Query Interface

**FR-QI-01 — Query input**
The analyst query interface is a simple, clean text box — modelled on GPT/Claude. No code, no form fields, no data selection dropdowns on the initial screen. Expressive but uncluttered.

**FR-QI-02 — Automatic mode routing**
The system automatically routes each query to FIP-Insight (DS-STAR) or FIP-Research (DS-STAR+) via the Query Clarity Agent. Ambiguous queries that could belong to either mode trigger a confirmation pop-up before the pipeline starts. The pop-up is prominent and cannot be missed — it does not auto-dismiss.

**FR-QI-03 — Query starter templates**
A set of example queries is displayed prominently on the chat page. Clicking a template imports the text into the query box but does NOT auto-submit. The analyst must edit or confirm before submitting. Templates are managed by admin.

**FR-QI-04 — Optional formatting control**
An optional field is available to specify output formatting preferences (e.g., "summarise in 5 bullet points", "rank by descending loss amount", "output as a table only"). This field is collapsed by default and revealed on demand. It is optional — leaving it blank is always valid.

**FR-QI-05 — File upload at query time**
Analysts can upload data files alongside their query. Supported formats: PDF, Word (.docx), Excel (.xlsx, .xls), CSV, JSON. Any number of files per query. File upload capability can be toggled off globally or per-department by admin.

**FR-QI-06 — Dataset suggestion**
Before the pipeline starts, the system suggests relevant datasets from the analyst's previously uploaded files using semantic search over file metadata (top 5–8 results surfaced). The analyst confirms the selection and can add or remove files. A "data sources used" panel is always visible in the analysis result.

**FR-QI-07 — Conversational follow-up**
After a completed analysis, the analyst can submit follow-up questions. Each follow-up spawns a new DS-STAR task but receives the prior task's findings as context injected into the Planner. The UI groups the original query and all follow-ups into a visible thread. V1 supports linear follow-up only — branching is future scope.

---

### 8.2 Data Access & File Management

**FR-DA-01 — Supported file formats**
The system supports both structured and unstructured files in V1:
- **Structured:** CSV (auto-delimiter detection), Excel (.xlsx, .xls), JSON
- **Unstructured:** PDF (text extraction), Word (.docx, narrative documents)

Both format types are core to V1. The Analyzer handles each differently: tabular profiling for structured files; text extraction, structure identification, and entity recognition for documents.

**FR-DA-02 — Institutional dataset management**
Core regulatory datasets (LFI fraud loss reports, SAR/STR records, KYC/CDD, transaction monitoring alerts, market surveillance data, consumer complaints) are loaded by IT/data engineering via backend pipelines — not through any UI. Analysts can supplement with personal file uploads. Upload capability is ON by default with an admin toggle to disable globally or per-department.

**FR-DA-03 — Uploaded file retention**
Analyst-uploaded files are session-scoped by default. After a task completes, the system prompts: *"Keep this file for future analyses?"* Files saved to the analyst's personal workspace are retained for 1 quarter, then archived (not deleted). Analysts can access archives on request.

**FR-DA-04 — Data versioning**
Every analysis result is automatically linked to a point-in-time snapshot of the data that produced it. This is on by default for all datasets, with no opt-out. Required for regulatory defensibility: if a finding in a supervisory letter is ever challenged, the exact data snapshot that produced it must be retrievable.

**FR-DA-05 — Access control**
V1 uses department-level RBAC. Each analyst sees datasets belonging to their department only. Future: Informatica Data Catalog integration as a pluggable access adapter — whatever access an analyst has in the org-wide catalog will be reflected in FIP without manual re-configuration. Architecture must accommodate this adapter pattern.

---

### 8.3 Planning & Execution Loop

The core engine is the DS-STAR pipeline: Analyzer → Planner → Coder → Executor → Debugger (on error) → Verifier → Router (if insufficient) → Finalyzer. See `04-architecture-decisions.md` for paper-confirmed agent behaviour details.

**FR-PE-01 — Stop / cancel**
The analyst can stop a running analysis at any point. Task is cancelled immediately; nothing is returned.

**FR-PE-02 — Pause and resume**
The analyst can pause a running task and resume it later. LangGraph checkpoints to PostgreSQL every round — resuming restores from the exact round the task was paused at.

**FR-PE-03 — Mid-analysis steering**
While a task is running, the analyst can inject a plain-English hint (e.g., "Focus on card fraud only, ignore wire transfers"). The hint is appended to the Planner's context for all subsequent rounds. Multiple hints accumulate — they are not overwritten. All hints are visible in the real-time progress panel with timestamps. In V1, hints apply from the next round onward only (no backtracking to earlier rounds).

**FR-PE-04 — Default round limit**
5–6 rounds per task on first run. This applies equally to FIP-Insight (single query) and each FIP-Research sub-question individually.

*Note:* The DS-STAR paper (Figure 2) shows hard tasks average 5.6 rounds. At max=5, there is a measurable accuracy drop on hard queries. Analysts should expect that hard queries will frequently use the extension mechanism — this is expected behaviour, not a system failure. The UI must communicate this clearly.

**FR-PE-05 — Round extension**
When default rounds are exhausted without a sufficient result, the system presents the Option E interface (see FR-PE-07) and offers "Extend and continue." Extension adds 5 rounds per click (fixed increment). Analyst-chosen increment is future scope.

**FR-PE-06 — Hard round cap**
40 cumulative rounds per query for FIP-Insight. 40 cumulative rounds per sub-question for FIP-Research. The cap is enforced regardless of how many extension cycles the analyst runs. Round budget is always visible to the analyst ("12 / 40 rounds used").

**FR-PE-07 — Task failure / round cap behaviour**
When a task hits its round cap or fails unrecoverably:
- **(a) Best partial result** — shown with a prominent **INCOMPLETE ANALYSIS** label
- **(b) Plain-English diagnostic** — what was found, what wasn't, why it stopped, suggested next steps
- **(c) Three action buttons:**
  - **Accept partial result** — takes the incomplete output as-is
  - **Refine and retry** — pre-fills the query box for editing and resubmission
  - **Extend and continue** — resumes from checkpoint, consuming from the remaining round budget

For hard failures with no partial result (container crash, GPU failure): diagnostic only + a Retry button.

**FR-PE-08 — Checkpointing**
LangGraph checkpoints task state to PostgreSQL every round. Tasks resume from the last checkpoint on worker crash or unexpected interruption — no work is lost.

---

### 8.4 Real-Time Progress Visibility

**FR-PV-01 — Two verbosity levels**
The analyst chooses between two progress display modes:
- **Summary:** A progress bar showing the current pipeline phase (Analyzing / Planning / Coding / Executing / Verifying / etc.)
- **Full trace:** Expandable panel showing — in FIP-Insight: sub-questions generated, current sub-question, current round number, current agent executing; in FIP-Research: numbered sub-question list with per-sub-question status (queued / running / complete) and per-sub-question round budget

Purpose: build analyst confidence in the system. Analysts must feel the system is working, not treating it as a black box.

**FR-PV-02 — FIP-Research "Report Mode" signal**
When routed to FIP-Research (DS-STAR+), the dashboard clearly signals "Report Mode":
- Purple accent colour in the header (vs. default blue for FIP-Insight)
- "Report Mode" badge
- Progress panel shows a numbered sub-question breakdown list (each sub-question with status: queued / running / complete)
- Round budget shown per sub-question: "Sub-question 3 of 7 · Round 4 / 6"

The analyst always knows which mode they are in and can see the full scope of work.

---

### 8.5 Output Types & Export

**FR-OUT-01 — Default output**
Every completed analysis always includes: narrative text, tables, and interactive charts. Raw data file and analysis code are opt-in via a toggle in the result panel — available but not shown by default.

**FR-OUT-02 — Chart format**
The Coder outputs a structured JSON describing data, chart type, axes, and configuration — not a static image. The frontend renders this as native interactive HTML charts using Recharts (React-native, consistent with ShadCN/Tailwind). Plotly.js is used as a fallback for chart types Recharts cannot support. On export to Word/PDF, the chart JSON is server-side rendered to a static image.

**FR-OUT-03 — FIP-Insight output style**
Chat-style response: concise executive summary paragraph followed by supporting tables and charts. Designed to feel like a direct answer, not a document.

**FR-OUT-04 — FIP-Research output style**
Formal document: structured sections following examiner report / thematic review / supervisory letter annex format. Dynamic section structure — the Writer agent decides section names and count based on the query and evidence collected. Fixed elements across all reports: Header (title, date, analyst, classification), Executive Summary, Query & Scope, Methodology, dynamic findings sections, Recommendations. Citations are inline throughout — every claim references the sub-question and code that produced it.

**FR-OUT-05 — Reformat without re-running**
The analyst can trigger a reformat of any completed result (re-sort, regroup, relabel, change format) by re-running only the Finalyzer against the stored output. The full pipeline does not re-execute.

**FR-OUT-06 — Export formats**
Three formats available on any completed analysis: **Word (.docx)** (editable), **PDF** (read-only shareable), **Excel (.xlsx)** (tables and raw data). Export is available from the result panel.

**FR-OUT-07 — Report templates**
Analysts can upload a custom Word template (e.g., CBUAE-branded). Templates can be personal (private to the analyst) or shared at department level (managed by admin). The system fills in content via Jinja2 placeholders.

---

### 8.6 Analysis History & Navigation

**FR-AH-01 — History sidebar**
The analysis history sidebar is closed by default on the chat page. It is open in the full dashboard view. Each analyst sees their own analyses only — no cross-analyst visibility.

**FR-AH-02 — History features**
Analysts can re-run previous queries and pin favourites. Re-running a previous query means: the old plan is used as a hint to the Planner (not replayed verbatim), fresh/updated data is loaded, and the full pipeline runs again.

**FR-AH-03 — In-app notifications**
For long-running tasks where the analyst has navigated away, an in-app notification alerts them when the task completes. Email notifications are future scope.

---

### 8.7 Page Structure & Navigation

**FR-NAV-01 — Pages**
Four pages in V1:
- `/login` — login screen (analyst)
- `/chat` — query interface
- `/dashboard` — active analysis view + history
- `/admin` — admin panel (completely separate URL, not visible to regular analysts; admin users have their own login)

**FR-NAV-02 — Navigation flow**
Login → `/chat` → submit query → redirected to `/dashboard` → "New Analysis" button → `/chat`. The "New Analysis" button is the only navigation path from dashboard back to chat. No persistent top nav between the two pages — the query submission action is the intentional transition point.

**FR-NAV-03 — Chat page layout**
Clean, minimal. Text box centred on screen. Starter templates displayed prominently below the text box. History sidebar present but collapsed. Formatting control field collapsed by default.

**FR-NAV-04 — Dashboard page layout**
Left panel: full analysis history sidebar (open). Main panel: live agent progress during execution, then result (narrative + tables + charts) when complete. Mid-analysis controls (Pause, Stop, Extend, Steering input) visible while task is running. On completion: export buttons (Word, PDF, Excel), Reformat button, raw data / code opt-in toggle, "Data sources used" panel.

---

### 8.8 Audit & Compliance

**FR-AU-01 — Audit log scope**
Every query, every plan step, every code version, every execution result is logged — timestamped, user-attributed, append-only. Result data is stored by reference (task ID + storage location), not inline in the log. The audit log is lean and queryable.

**FR-AU-02 — Audit log retention**
Records are retained indefinitely. No deletion in V1. Retention policy configuration (archive after N years) is future scope.

**FR-AU-03 — Audit log access**
Two tiers:
- **Admin:** Full access to all records across all users
- **Analyst:** Can view their own query history only; no visibility into other analysts' records

**FR-AU-04 — Audit log behaviour**
Purely passive. The log is a compliance record, not a monitoring tool. No alerting, anomaly detection, or active review in V1. Available on demand for regulatory examination.

**FR-AU-05 — Tamper-evidence**
The audit log is append-only and tamper-evident. No record can be modified or deleted after it is written.

---

### 8.9 Admin Panel

The admin panel is at a separate URL, accessible only to admin users. Regular analysts never see it.

**FR-ADMIN-01 — User management**
Add/remove users, assign department and role.

**FR-ADMIN-02 — File upload toggle**
Enable/disable analyst file uploads globally or per-department.

**FR-ADMIN-03 — Query template management**
Create, edit, and publish the starter templates shown on the analyst chat page.

**FR-ADMIN-04 — Shared report template management**
Upload and manage department-level Word report templates.

**FR-ADMIN-05 — System health dashboard**
Task queue depth, active tasks, GPU utilisation, error rates, dead-letter queue alerts.

**FR-ADMIN-06 — Audit log viewer**
Searchable log of all queries, filterable by user, date, and department.

---

## 9. Non-Functional Requirements

### 9.1 Performance

| Requirement | Target |
|-------------|--------|
| FIP-Insight (easy query, 3 rounds) | < 3 minutes end-to-end |
| FIP-Insight (hard query, 10+ rounds) | < 20 minutes end-to-end |
| FIP-Research (7 sub-questions, K=1 refinement) | < 60 minutes end-to-end |
| Finalyzer reformat (re-run only) | < 30 seconds |
| File upload and Analyzer profiling | < 60 seconds per file for structured files up to 500 MB |

### 9.2 Security

- Fully air-gapped. No outbound network access from the system.
- mTLS for all internal service-to-service communication.
- HashiCorp Vault for secrets management. No secrets in environment variables.
- Docker sandbox for code execution: no network access, 2 GB memory cap, read-only data mount, non-root user, per-execution timeout.
- JWT authentication for all frontend-to-backend API calls.
- Department-level RBAC for data access.

### 9.3 Reliability

- LangGraph checkpoints to PostgreSQL every round. Task resumes from last checkpoint on worker crash.
- Celery + Redis Sentinel for async task queue with high availability.
- Priority queue with dead-letter queue (DLQ) for failed tasks.
- Container concurrency budget enforced system-wide (max concurrent sandbox containers).

### 9.4 Data Integrity

- Every analysis result is linked to a point-in-time data snapshot. Required for regulatory defensibility.
- Audit log is append-only and tamper-evident.

---

## 10. Architecture Overview

The system is a multi-agent pipeline built on the DS-STAR architecture (arXiv:2509.21825). Full architecture detail is in `00-discovery/03-architecture-v2.html` (v3.3) and `00-discovery/04-architecture-decisions.md`.

### Core agents (FIP-Insight)
1. **Analyzer** — profiles every data file; produces per-file descriptions (D). Critical: removing it drops hard-task accuracy by 18 pp (paper ablation).
2. **Planner** — generates one plan step per round, conditioned on the last execution result.
3. **Coder** — extends the previous script sₖ₋₁ with the new plan step; always outputs a complete standalone script (Listing 51, paper-confirmed).
4. **Executor** — runs the script in an isolated Docker sandbox. One container per task (not per round) — rounds execute via docker exec.
5. **Debugger** — two-step: (1) Traceback Summariser condenses raw stderr; (2) Code Fixer repairs the script. Max 3 attempts per round (Listings 55–57, paper-confirmed).
6. **Verifier** — LLM-as-judge; outputs "Yes" / "No" (Listing 52, paper-confirmed).
7. **Router** — on "No": either "Add Step" (Planner adds pₖ₊₁) or index l (truncate plan to {p₀…pₗ₋₁} and regenerate from pₗ).
8. **Finalyzer** — generates a Python formatting script and executes it in the sandbox (Listing 54, paper-confirmed — not text-only reformatting).

### Additional agents (FIP-Research / DS-STAR+)
- **Sub-Question Generator** — decomposes the open-ended query into focused sub-questions; also handles gap-finding in refinement mode (no separate Evaluator agent — Algorithm 2, paper-confirmed).
- **Report Writer** — synthesises a cited, structured report from all sub-question answers. Uses Pro-tier LLM (highest quality).
- K=1 refinement round by default (paper-confirmed: "DS-STAR+ refines its report only for one round"). Early stop if Generator produces zero new sub-questions.

### Technology stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Tailwind + ShadCN |
| State machine | LangGraph (PostgreSQL checkpointing) |
| Task queue | Celery + Redis Sentinel |
| Sandbox | Docker (per-task container, docker exec per round) |
| LLM inference | Provider-agnostic adapter: Ollama (prod) / Gemini (dev) / Azure OpenAI (optional) |
| Secrets | HashiCorp Vault |
| Auth | JWT |
| Report generation | python-docx-template + LibreOffice headless (Word → PDF) |
| Charts | Recharts (primary) + Plotly.js (fallback) |
| Internal comms | mTLS |

---

## 11. Out of Scope for V1

| Feature | Status |
|---------|--------|
| Department-specific UI, templates, regulatory knowledge injection | 🔮 V2 |
| PII masking | 🔮 V2 (revisit when live DB connectivity is added) |
| Live database connectivity | 🔮 V2 |
| External REST API consumers (machine-to-machine) | 🔮 V2 |
| Email notifications | 🔮 V2 |
| Conversation branching (non-linear follow-up) | 🔮 V2 |
| Mid-analysis steering backtracking (hints affecting past rounds) | 🔮 V2 |
| ML model building in the sandbox | 🔮 Future |
| Analyst-chosen round extension increment | 🔮 V2 |
| Informatica Data Catalog integration | 🔮 V2 |
| LLM provider switching via admin panel | 🔮 V2 |
| Per-department RBAC granularity | 🔮 V2 |
| Data retention policy management | 🔮 V2 |
| JSON / programmatic export format | 🔮 V2 |
| GCC/international comparison datasets | 🔮 V2 |

---

## 12. Open Questions

These questions are not blockers for the PRD but must be resolved before the TDD and Security Review.

| # | Question | Needed For |
|---|----------|-----------|
| 1 | How do analysts authenticate today? (Active Directory, CBUAE SSO?) | JWT integration design |
| 2 | What is the largest dataset an analyst would query in a single session? (rows / GB) | Infrastructure sizing, Executor memory limits |
| 3 | Are there existing report templates used for supervisory letters? | Finalyzer template design |
| 4 | Does output need to integrate with an existing case management system in V1? (NICE Actimize, Oracle FCCM, ServiceNow?) | API contract — currently scoped out of V1 |
| 5 | What is the data freshness requirement? (24-hour-old data acceptable, or near-real-time?) | Data ingestion pipeline design |
| 6 | Who has authority to approve what an analyst can query? (Sensitivity tiers for datasets) | RBAC policy design |
| 7 | What GPU hardware is available on-premise? | LLM model selection, inference throughput sizing |
| 8 | How many concurrent analysts are expected to use the system at peak? | Task queue sizing, container concurrency budget |

---

## 13. Appendix: Feature Decision Traceability

All features in this PRD trace back to confirmed decisions in `00-discovery/05-feature-discussion.md`. The table below maps PRD sections to their source.

| PRD Section | Source Document | Topic |
|-------------|----------------|-------|
| 8.1 Query Interface | `05-feature-discussion.md` | Topic 1 |
| 8.2 Data Access & File Management | `05-feature-discussion.md` | Topic 2 |
| 8.3 Planning & Execution Loop | `05-feature-discussion.md` | Topic 3 |
| 8.4 Real-Time Progress | `05-feature-discussion.md` | Topic 1 (items 6, 7) |
| 8.5 Output Types & Export | `05-feature-discussion.md` | Topics 4 & 5 |
| 8.6 Analysis History & Navigation | `05-feature-discussion.md` | Topic 1 (items 4, 5, 10) |
| 8.7 Page Structure & Navigation | `05-feature-discussion.md` | Topic 10 |
| 8.8 Audit & Compliance | `05-feature-discussion.md` | Topic 8 |
| 8.9 Admin Panel | `05-feature-discussion.md` | Topic 2 (admin scope) |
| Section 10 Architecture | `04-architecture-decisions.md` + `03-architecture-v2.html` v3.3 | Q1–Q18 |
| Section 7 Deployment | `03-requirements-discovery.md` | Requirements 2 & 5 |

---

*This PRD is a living document. Changes require updating the source feature discussion log first, then this document. No feature enters the TDD without first being confirmed here.*
