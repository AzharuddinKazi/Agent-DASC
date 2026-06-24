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

## Topics Not Yet Started

| # | Topic |
|---|-------|
| 3 | The Planning & Execution Loop — what happens between query submission and result |
| 4 | Output types — tables, charts, narratives, files |
| 5 | DS-STAR+ thematic reports — trigger, output, audience |
| 6 | Department-specific features — what differs per department |
| 7 | PII handling — what gets masked, for whom, when |
| 8 | Audit & compliance — what the system must log, for how long |
| 9 | API & export — REST API consumers, export formats |
| 10 | Frontend — full UI layout, what actions are available |

---

*This document is updated after every discussion session. Nothing goes into the PRD without first being confirmed here.*
