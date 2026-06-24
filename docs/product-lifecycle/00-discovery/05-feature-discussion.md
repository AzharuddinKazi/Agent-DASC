# Feature Discussion Log — Pre-PRD Brainstorm

**Branch:** `docs/product-lifecycle`  
**Date:** 2026-06-24  
**Purpose:** Running record of every feature discussed, decided, deferred, or left open before writing the PRD. Updated continuously. Nothing goes into the PRD without first appearing here as confirmed.

---

## How to read this document

- ✅ **Confirmed** — decision is locked, goes into PRD as-is
- 🔄 **Open** — raised but not yet decided; needs follow-up
- 🔮 **Future scope** — explicitly deferred to v2 or later
- ❌ **Rejected** — considered and ruled out

---

## Topic 1: Query Interface

### Confirmed decisions

| # | Feature | Decision |
|---|---------|---------|
| 1 | Frontend stack | React + Tailwind + ShadCN. Web-first application. No desktop/mobile in V1. |
| 2 | Query input | Simple text box, GPT/Claude-like. Expressive but not cluttered. |
| 3 | Query routing (Mode A vs B) | Automatic via Query Clarity Agent. Ambiguous queries trigger a prominent pop-up asking the analyst to confirm intent before the pipeline starts. Pop-up must not be missable. |
| 4 | Analysis history sidebar | Closed by default on the Chat UI page. Opens in full Dashboard view. Each analyst sees their own analyses only — no cross-analyst visibility. |
| 5 | History features | Analysts can re-run previous queries, pin favourites. Re-run = "Apply same approach" — old plan used as a hint to the Planner, fresh/updated data, not verbatim plan replay. |
| 6 | Real-time progress visibility | Two verbosity levels: (a) summary progress bar showing current phase, (b) expandable full agent trace — sub-questions generated, current sub-question, current round number, current agent executing. Analyst chooses verbosity. Purpose: build analyst confidence in the system. |
| 7 | Report generation format | python-docx-template fills a .docx template. LibreOffice headless converts to PDF. Single generation path, two output formats. |
| 8 | Report template | Analyst can upload a custom Word template (e.g., CBUAE-branded). Templates can be personal (private) or shared at department level. System fills in content via Jinja2 placeholders. |
| 9 | Data connectivity — V1 | File upload only. Any file format: PDF, Word, Excel, JSON, CSV. Live database connectivity is deferred to future scope. |
| 10 | Async notifications | In-app notifications for V1 (analyst notified when long-running task completes without staying at screen). Email notifications deferred to future scope. |
| 11 | Query templates / starter prompts | Displayed prominently on the Chat UI. Clicking a template imports it into the text box but does NOT auto-submit. Analyst edits or fills in parameters before submitting. |
| 12 | Formatting control | Analyst can optionally specify output format preferences at query time (e.g., "summarise in 5 bullet points", "rank by descending loss amount"). Field is optional and collapsed by default. |
| 13 | Conversational follow-up | Analyst can ask follow-up questions on a completed analysis. Each follow-up spawns a new DS-STAR task but receives the prior task's findings as context injected into the Planner (Option B). UI groups related queries into a thread — analyst sees the full conversation. |
| 14 | Conversation branching | Deferred to V2. V1 supports linear follow-up only. |
| 15 | Role-based query visibility | Each analyst sees only their own analysis history. No cross-role or cross-department history sharing in V1. |
| 16 | Checkpointing | V1 requirement. LangGraph checkpoints to PostgreSQL every round. Task resumes from last checkpoint on worker crash or unexpected interruption. |
| 17 | ML model building in sandbox | Deferred to future scope. Architecture already supports it (same sandbox, different class of scripts). |

---

## Topic 2: Data Access & the Analyzer

### Confirmed decisions

| # | Feature | Decision |
|---|---------|---------|
| 1 | Institutional data management | Option C: Core regulatory datasets (LFI fraud loss reports, SAR/STR records, KYC/CDD, transaction monitoring alerts, market surveillance, consumer complaints) managed by IT/data team via admin panel. Analysts can supplement with personal file uploads. Upload capability is ON by default with an admin toggle to disable. |
| 2 | Dataset selection | System suggests relevant datasets via semantic search over pre-indexed file metadata (surfaces top 5–8). Analyst confirms the selection and can add or remove datasets before the Analyzer runs. A "data sources used" panel is always visible in the analysis result. |
| 3 | Analyst-uploaded file retention | Session-scoped by default. After task completes, system prompts: "Keep this file for future analyses?" Files saved to personal workspace are retained for 1 quarter then archived (not deleted). Analyst can access archives on request. |
| 4 | RBAC | Department-level access for V1. Each analyst sees datasets belonging to their department only. Future: Informatica Data Catalog integration as a pluggable access adapter — whatever access an analyst has in the org-wide catalog will be reflected in the system without manual re-configuration. Architecture must accommodate this adapter pattern. |

### Admin Panel — confirmed scope

**Important clarification:** The admin panel does NOT include data management or data upload. All data is uploaded by analysts themselves and stays within their own session and account. Institutional datasets are loaded via backend pipelines (IT/data engineering), not through any admin UI. The admin panel is purely for system and user governance.

**V1 scope:**
- User management — add/remove users, assign department and role
- File upload toggle — enable/disable globally or per department
- Query template management — create, edit, publish shared templates visible on the Chat UI
- Shared report template management — upload and govern department-level Word templates centrally
- System health dashboard — task queue depth, active tasks, GPU utilisation, error rates, DLQ alerts
- Audit log viewer — searchable log of all queries, by user, date, department

**Future scope:**
- LLM provider switching (Gemini → Ollama → Azure)
- Informatica Data Catalog connector configuration
- Per-department RBAC granularity
- Email notification configuration
- Data retention policy management

### Remaining Topic 2 decisions

| # | Question | Decision |
|---|---------|---------|
| Q5 | Structured vs unstructured file support in V1 | ✅ **Both in V1.** Supporting structured (CSV, Excel, JSON) and unstructured (PDF, Word as narrative documents) simultaneously is a core selling point of the system. The Analyzer handles each format differently: tabular profiling for structured files; text extraction, structure identification, and entity recognition for documents. This must not be deferred. |
| Q6 | Data versioning | ✅ **On by default for all datasets.** Every analysis result is automatically linked to a point-in-time snapshot of the data that produced it. No exceptions. Required for regulatory defensibility — if a finding in a supervisory letter is ever challenged, the exact data snapshot that produced it must be retrievable. |

---

## Topic 3: The Planning & Execution Loop

### Confirmed decisions

| # | Feature | Decision |
|---|---------|---------|
| 1 | Stop / cancel | Analyst can stop a running analysis entirely at any point. Task is cancelled, nothing returned. |
| 2 | Pause and resume | Analyst can pause a running task and resume it later. Enabled by LangGraph checkpointing to PostgreSQL — resumes from the exact round it was paused at. V1. |
| 3 | Mid-analysis steering | Analyst can inject a plain-English hint while the task is running (e.g., "Focus on card fraud only, ignore wire transfers"). Hint is appended to the Planner's context for all subsequent rounds. Multiple hints accumulate — they are not overwritten. All hints visible in the real-time progress panel with timestamps. V1: hints apply from next round onward only (no backtracking). V2: smart backtracking when hint contradicts current plan direction. |
| 4 | Default round limit | 5–6 rounds per task on first run. Applies equally to DS-STAR (single query) and each DS-STAR+ sub-question individually. Departure from paper's 20-round default — chosen for faster analyst feedback. |
| 5 | Extension mechanism | When default rounds are exhausted without a sufficient result, the system presents Option E (see below) and offers "Extend and continue." Extension adds 5 rounds per click (fixed increment). Analyst-chosen increment is V2. |
| 6 | Hard round cap | 40 cumulative rounds per query for DS-STAR. 40 cumulative rounds per sub-question for DS-STAR+. Cap is enforced regardless of how many "Extend and continue" cycles the analyst runs. Round budget always visible to analyst ("12 / 40 rounds used"). |
| 7 | Task failure / max rounds behaviour (Option E) | When a task hits its round cap or fails unrecoverably, the system shows: (a) best partial result clearly labelled **INCOMPLETE ANALYSIS**, (b) plain-English diagnostic — what was found, what wasn't, why it stopped, suggested next steps, (c) three action buttons: **Accept partial result** / **Refine and retry** (pre-fills query for editing) / **Extend and continue** (resumes from checkpoint, consumes from remaining round budget). For hard failures with no partial result (container crash, GPU failure): diagnostic only + Retry button. |

---

## Topic 4: Output Types

### Confirmed decisions

| # | Feature | Decision |
|---|---------|---------|
| 1 | Default output | Narrative + tables + charts always included. Raw data file and analysis code are opt-in via a toggle in the result panel — available but not surfaced by default. |
| 2 | Chart output format | Coder outputs a structured JSON describing data, chart type, axes, and configuration — not a matplotlib PNG. Frontend renders it as native interactive HTML charts using Recharts (React-native, matches ShadCN/Tailwind aesthetic). Plotly.js used as fallback for chart types Recharts cannot support. On export to Word/PDF, the same JSON is server-side rendered to a static image. |
| 3 | Reformat without re-running | Analyst can trigger a reformat of any completed result (re-sort, regroup, relabel, change format) by re-running only the Finalizer against the existing stored output. Full pipeline does not re-execute. Fast and cheap. |
| 4 | DS-STAR output feel | Chat-style response — concise executive summary paragraph + supporting tables and charts. Feels like a direct answer, not a document. |
| 5 | DS-STAR+ output feel | Formal document — structured sections matching examiner report / thematic review / supervisory letter annex format used by CBUAE today. Department-specific templates govern section structure. |
| 6 | Charting library | Recharts for V1. If Recharts cannot meet a specific requirement, Plotly.js used for that chart type. Other libraries (Vega-Lite) considered in future if needed. |

---

## Topic 5: DS-STAR+ Thematic Reports

### Confirmed decisions

| # | Feature | Decision |
|---|---------|---------|
| 1 | UI mode signalling | Once routing is confirmed as DS-STAR+, the UI clearly signals "Report Mode" — different header, different progress layout (sub-question breakdown prominent, not a single round tracker). Analyst always knows which mode they're in. |
| 2 | Report section structure | Dynamic — the Writer agent decides sections based on the query and evidence collected. No fixed template imposed. Fixed elements across all reports: Header (title, date, analyst, classification), Executive Summary, Query & Scope, Methodology, dynamic findings sections (Writer decides names and count), Recommendations. Citations are inline throughout — not in a separate annex. |
| 3 | CBUAE report adaptation | Department templates control branding, header/footer, document classification markings, and tone. They do not mandate a fixed section structure. "Recommendations" becomes "Supervisory Recommendations" in regulatory templates. |
| 4 | Refinement: no separate Evaluator | Paper confirmed (Algorithm 2): there is no separate Evaluator agent. The Sub-Question Generator handles both initial decomposition AND gap-finding for refinement. In refinement mode, Generator receives the current report R and identifies missing coverage. Default K=1 refinement round (paper's setting). K is configurable in the admin panel. Early stop: if Generator produces zero new sub-questions, refinement terminates. |
| 5 | Debugger correction (paper confirmed) | Debugger receives `(s, traceback, D)` — not just `(s, traceback)`. Data descriptions D are critical for fixing semantic errors (wrong column names, wrong sheet names, wrong JSON paths). This must be reflected in all Debugger prompt implementations. |
| 6 | Report audience | Primarily internal (analyst, their manager, department head). Reports going to LFIs (as supervisory letter annexes) get a "regulatory tone" modifier in the Writer's prompt — but same structure. |

---

## Topics Not Yet Started

| # | Topic |
|---|-------|
| 6 | Department-specific features — what differs per department |
| 7 | PII handling — what gets masked, for whom, when |
| 8 | Audit & compliance — what the system must log, for how long |
| 9 | API & export — REST API consumers, export formats |
| 10 | Frontend — full UI layout, what actions are available |

---

*This document is updated after every discussion session. Nothing goes into the PRD without first being confirmed here.*
