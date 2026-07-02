# Product Requirements Document
## CBUAE Financial Intelligence Platform (FIP) — V1

**Stage:** PRD — Stage 1
**Branch:** `docs/product-lifecycle`
**Date:** 2026-06-24
**Author:** Fraud Prevention Supervision, CBUAE
**DRI:** [PLACEHOLDER — to be assigned at project intake]
**Status:** Draft

**Prerequisite documents:**
- `00-discovery/01-paper-analysis.md` — DS-STAR paper deep-dive
- `00-discovery/02-one-pager.md` — 1-Pager / PRFAQ
- `00-discovery/03-requirements-discovery.md` — Requirements Q&A log
- `00-discovery/04-architecture-decisions.md` — Architecture decisions with paper references
- `00-discovery/05-feature-discussion.md` — Pre-PRD feature brainstorm (all 10 topics)
- `00-discovery/03-architecture-v2.html` — Architecture diagram v3.3

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-06-24 | FPS, CBUAE | Initial draft — feature coverage from discovery phase |
| 0.2 | 2026-06-25 | FPS, CBUAE | PM audit applied: RACI, launch criteria, rollout plan, feedback mechanism, risk register, error states, system capacity, acceptance criteria (in progress), Section 10 simplified. AC review in progress — corrections applied to FR-QI-01/02/04/06, FR-DA-02/04/05 |

---

## Stakeholders & RACI

| Role | Name | R/A/C/I | Notes |
|------|------|---------|-------|
| DRI / Product Lead | [PLACEHOLDER] | Accountable | Single person responsible for this PRD and product decisions |
| Engineering Lead | [PLACEHOLDER] | Responsible | Owns technical implementation |
| Design Lead | [PLACEHOLDER] | Responsible | Owns UX spec and visual design |
| IT Security | [PLACEHOLDER] | Consulted | Must sign off before launch; owns penetration testing |
| Legal / Compliance | [PLACEHOLDER] | Consulted | Must review AI-generated regulatory output policy |
| Data Governance | [PLACEHOLDER] | Consulted | Must approve audit log design and data versioning |
| IT Infrastructure | [PLACEHOLDER] | Consulted | GPU procurement, on-premise deployment, network isolation |
| Fraud Prevention Supervision (primary dept.) | [PLACEHOLDER] | Consulted | Primary pilot users; domain SMEs |
| Dept. Heads (all 5 departments) | [PLACEHOLDER] | Informed | Briefed at milestones; approve rollout to their department |
| CBUAE Leadership | [PLACEHOLDER] | Informed | Briefed at Go/No-Go and at GA launch |

*RACI key: R = Responsible (does the work), A = Accountable (decision authority), C = Consulted (input required), I = Informed (kept up to date)*

---

## 1. Problem Statement

Analysts across CBUAE's Financial Crime & Market Conduct departments work with rich, multi-file datasets — fraud loss reports submitted by licensed financial institutions (LFIs), SAR/STR databases, KYC records, consumer complaints, and market surveillance feeds. Extracting insights from this data today requires either writing Python or SQL code, or waiting for IT to build a custom report. Neither path is fast enough for supervision work.

The result:
- Supervisory decisions are made on incomplete or manually extracted data
- Thematic reviews that should take hours take weeks
- The analytical depth of supervisory letters is constrained by what a non-technical officer can produce in Excel
- Peer benchmarking across LFIs requires manual data wrangling that few analysts can do independently

---

## 2. What We Are Building

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

## 3. Goals & Success Metrics

*Note: Baselines marked [TBD] must be established via measurement before PRD is finalised. See Section 16, Open Question 9.*

| Metric | Baseline (Today) | Target (12 months post-launch) | How Measured |
|--------|-----------------|-------------------------------|-------------|
| Time to produce a peer benchmarking table | [TBD — measure during pilot] | < 15 minutes | Timed analyst sessions during pilot |
| Time to produce a thematic review report | [TBD — measure during pilot] | < 2 days | Ticket tracking from query submission to approved report |
| % of supervisory queries answered same-day | [TBD — analyst survey pre-launch] | > 80% | Audit log: task created vs. result timestamp, same calendar day |
| Analyst satisfaction with FIP | N/A (new system) | > 4.0 / 5.0 on quarterly CSAT | Quarterly in-app CSAT survey |
| Number of thematic reviews completed per year | [TBD — count existing reviews pre-launch] | 2× current | Annual count from audit log + department records |

---

## 4. Non-Goals (What This Is Not)

- **Not a replacement for human judgement.** The system provides analysis; the analyst interprets and decides. No supervisory action is taken by the system.
- **Not a real-time alert engine.** FIP is a supervisory analytics tool, not a transaction monitoring or AML screening system.
- **Not a customer-facing product.** Internal CBUAE use only. On-premise. Air-gapped.
- **Not a replacement for LFI fraud systems.** CBUAE oversees LFIs; this tool helps CBUAE do that better.
- **Not a live database connector in V1.** Data access in V1 is file upload only. Live database connectivity is future scope.
- **English only.** V1 is strictly English — UI, queries, and all outputs. Arabic and other language support is future scope.

---

## 5. Target Users

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

## 6. Deployment & Infrastructure

- **Deployment model:** On-premise only. Fully air-gapped. No data leaves CBUAE infrastructure. No API calls to external services. No cloud components in production.
- **LLM inference:** Local model deployment via Ollama or vLLM. Provider-agnostic adapter — switching LLM providers requires only a config file change, zero agent code changes. Actual model procured and deployed is a CBUAE IT decision.
- **Frontend/backend separation:** React frontend on a separate server. Backend built on LangGraph Server, exposing HTTP and WebSocket endpoints.
- **Authentication:** JWT tokens. Analysts authenticate via login screen; every API call from the browser carries a signed JWT. Analyst and Admin are completely separate login URLs.

---

## 7. Functional Requirements

*Each FR includes: Description, and Acceptance Criteria. Acceptance criteria marked [TBD — in discussion] are pending confirmation in the ongoing PRD review session.*

---

### 8.1 Query Interface

**FR-QI-01 — Query input**
The analyst query interface is a simple, clean text box — modelled on GPT/Claude. No code, no form fields, no data selection dropdowns on the initial screen. Expressive but uncluttered.

*Acceptance criteria:*
- Text box is the primary interactive element on `/chat` on first load; no other input controls are visible without interaction
- Text box accepts a **maximum of 5,000 characters** (no minimum beyond non-empty; open-ended queries rarely exceed a few hundred characters)
- Placeholder text guides the analyst (e.g., "Ask a question about your financial data...")
- Submit button is disabled when the text box is empty
- Pressing Enter submits; Shift+Enter creates a new line
- Character count is shown when input exceeds 4,000 characters, turning red at 4,800 to warn the analyst they are approaching the limit

---

**FR-QI-02 — Automatic mode routing**
The system automatically routes each query to FIP-Insight (DS-STAR) or FIP-Research (DS-STAR+) via the Query Clarity Agent. Ambiguous queries that could belong to either mode trigger a confirmation pop-up before the pipeline starts. The pop-up is prominent and cannot be missed — it does not auto-dismiss.

*Acceptance criteria:*
- Queries clearly scoped to a specific factoid route to FIP-Insight without any prompt shown
- Queries clearly open-ended or thematic route to FIP-Research without any prompt shown
- Ambiguous queries surface a modal with two clearly labelled options: "Specific Analysis (FIP-Insight)" and "Research Report (FIP-Research)", each with a one-sentence description
- The modal cannot be dismissed by clicking outside it, pressing Escape, or any other method — the analyst must make a choice
- The analyst's mode selection is logged in the immutable audit trail alongside the query (same append-only PostgreSQL log described in FR-AU-01; stored fields: task ID, analyst user ID, query text, mode selected, timestamp)
- The audit trail entry for mode selection is visible to admin via the audit log viewer (FR-ADMIN-06); analysts can see their own mode selection as part of their query history but cannot see other analysts' entries and cannot modify any entry

---

**FR-QI-03 — Query starter templates**
A set of example queries is displayed prominently on the chat page. Clicking a template imports the text into the query box but does NOT auto-submit. The analyst must edit or confirm before submitting. Templates are managed by admin.

*Acceptance criteria:*
- Minimum 5 starter templates are visible on `/chat` below the text box at all times
- Clicking a template inserts its text into the query box and sets focus on the query box
- The query is NOT submitted automatically; the Submit button remains the only submission mechanism
- Templates are editable by admin via the admin panel without a code deployment
- Updating or adding templates in the admin panel is reflected on the chat page within 60 seconds

---

**FR-QI-04 — Optional formatting control**
An optional field is available to specify output formatting preferences (e.g., "summarise in 5 bullet points", "rank by descending loss amount", "output as a table only"). This field is collapsed by default and revealed on demand. It is optional — leaving it blank is always valid.

*Acceptance criteria:*
- The formatting control field is hidden on initial page load; a clearly labelled toggle (e.g., "Formatting preferences ▼") reveals it
- When expanded, the field shows placeholder text with concrete examples: *"e.g., 'Summarise in 5 bullet points', 'Rank by highest loss first', 'Output as a table only', 'Round all figures to 2 decimal places'"*
- Below the placeholder, 4–6 clickable example chips are displayed (e.g., "5 bullet points", "Rank descending", "Table only", "2 decimal places"); clicking a chip inserts that text into the field (can be edited after insertion)
- The field accepts free text up to 500 characters
- Submitting without entering anything in this field produces the same result as submitting with the field collapsed
- The analyst's formatting instruction is visible in the result panel alongside the query (so they can see what instruction was applied)

---

**FR-QI-05 — File upload at query time**
Analysts can upload data files alongside their query. Supported formats: PDF, Word (.docx), Excel (.xlsx, .xls), CSV, JSON. File upload capability can be toggled off globally or per-department by admin.

*File limits:*
- Maximum file size: **500 MB per file**
- Maximum files per query: **20 files**
- Maximum total upload size per session workspace: **5 GB**
- Maximum file name length: 255 characters

*Acceptance criteria:*
- File upload supports both drag-and-drop onto the chat page and click-to-browse
- Only files with accepted extensions (.pdf, .docx, .xlsx, .xls, .csv, .json) are accepted; all others are rejected before upload begins with a clear error message specifying the unsupported format
- Files exceeding 500 MB are rejected before upload begins with a clear error message
- Upload progress is shown per file (progress bar or percentage)
- Analyst can remove individual files from the upload queue before submitting
- When file upload is disabled by admin, the upload UI element is hidden entirely — not greyed out
- Attempting to upload more than 20 files in one query shows an error before any files are uploaded

---

**FR-QI-06 — Dataset suggestion**
Before the pipeline starts, the system suggests relevant datasets from the analyst's previously uploaded files using semantic search over file metadata (top 5–8 results surfaced). The analyst confirms the selection and can add or remove datasets. A "data sources used" panel is always visible in the analysis result.

*Implementation note:* Dataset suggestion requires the Analyzer to profile and store a text description for every uploaded file in PostgreSQL at upload time. At query submission, the system runs a keyword/text search (V1: PostgreSQL full-text search; future: pgvector cosine similarity) against stored descriptions to rank files by relevance. This DB setup is a TDD requirement — dataset suggestion cannot function without it.

*Cold start (first use / no files):* If the analyst has never uploaded any files and no institutional datasets have been loaded for their department, the dataset selection step is skipped. Instead, the query submission screen shows an inline upload prompt: "No data sources found — upload a file to get started." The pipeline cannot start until at least one file is provided.

*Acceptance criteria:*
- After query submission (before pipeline starts), a dataset selection screen shows top 5–8 suggested files ranked by semantic relevance to the query; if fewer than 5 files exist, all available files are shown
- Each suggestion displays: file name, file type icon, upload date, and the one-line description generated by the Analyzer at upload time
- The analyst can deselect any suggested file
- The analyst can add any file from their personal workspace not in the top suggestions
- A "Confirm and start analysis" button is the only way to proceed — the pipeline cannot start without explicit analyst confirmation
- The "Data sources used" panel in the result shows the exact file names, versions, and data snapshot IDs of all files provided to the pipeline
- On first use (cold start), the dataset selection step is replaced by an upload prompt as described above

---

**FR-QI-07 — Conversational follow-up**
After a completed analysis, the analyst can submit follow-up questions. Each follow-up spawns a new DS-STAR task but receives the prior task's findings as context injected into the Planner. The UI groups the original query and all follow-ups into a visible thread.

*Acceptance criteria:*
- A follow-up query input appears below the result of any completed analysis
- Submitting a follow-up creates a new task; the prior task's findings summary is injected into the new Planner context
- The UI displays the original query and all follow-ups as a labelled thread: "Original query", "Follow-up 1", "Follow-up 2", etc.
- All results in a thread remain visible on the dashboard without navigating away
- Each follow-up inherits the same data source selection as the original unless the analyst changes it
- V1 supports linear follow-up only — there is no branch/fork mechanism

---

### 8.2 Data Access & File Management

**FR-DA-01 — Supported file formats**
The system supports both structured and unstructured files in V1:
- **Structured:** CSV (auto-delimiter detection), Excel (.xlsx, .xls), JSON
- **Unstructured:** PDF (text extraction), Word (.docx, narrative documents)

*Acceptance criteria:*
- A CSV uploaded with any of the following delimiters is correctly parsed: comma, semicolon, tab, pipe
- An Excel file with multiple sheets is correctly profiled (Analyzer identifies all sheets, their column names, row counts, and data types)
- A PDF uploaded as an unstructured document has its text correctly extracted (verified against known test documents)
- A Word (.docx) document has its narrative text correctly extracted, including text in tables within the document
- A JSON file is parsed regardless of whether it is a flat array, nested object, or array of objects (Analyzer describes the schema)
- Uploading an empty file (0 bytes) is rejected with a clear error
- Uploading a password-protected Excel or PDF is rejected with an error message specifying that password-protected files are not supported in V1

---

**FR-DA-02 — Institutional dataset management**
Core regulatory datasets are loaded by IT/data engineering via backend pipelines — not through any UI. Institutional datasets are **optional** — the system works entirely from analyst-uploaded files if no institutional datasets have been loaded. Upload capability is ON by default with an admin toggle to disable.

*Acceptance criteria:*
- If institutional datasets have been loaded for a department, they appear in the analyst's dataset selection screen alongside personal uploads, clearly labelled as "Institutional" vs. "Personal upload"
- If no institutional datasets have been loaded for a department, the dataset selection screen shows only the analyst's personal uploads; no placeholder or error is shown for the absent institutional datasets
- Institutional datasets cannot be deleted or edited by analysts
- Admin toggling file uploads off removes the upload UI for all analysts in the affected scope within 60 seconds
- Admin toggling file uploads on restores the upload UI within 60 seconds
- The system can be used productively from day one with analyst-uploaded files only; no institutional dataset loading is required to make the system functional

---

**FR-DA-03 — Uploaded file retention**
Analyst-uploaded files are session-scoped by default. After a task completes, the system prompts: *"Keep this file for future analyses?"* Files saved to the analyst's personal workspace are retained for 1 quarter (90 days), then archived (not deleted). Analysts can access archives on request.

*Acceptance criteria:*
- After task completion, a non-intrusive prompt asks "Keep [filename] for future analyses? [Keep] [Discard]"
- Choosing "Discard" deletes the file from the system immediately
- Choosing "Keep" moves the file to the analyst's personal workspace
- Files in the personal workspace are visible in the dataset selection screen on future queries
- Files older than 90 days are automatically moved to archive status; archived files no longer appear in the dataset selection screen but are accessible via a dedicated "Archives" section in the history sidebar
- Archived files can be restored to the personal workspace by the analyst on request

---

**FR-DA-04 — Data versioning**
Every analysis result is automatically linked to a point-in-time snapshot of the data that produced it. No opt-out.

*Acceptance criteria:*
- Every completed analysis result stores the exact snapshot ID and version of every data file used
- The "Data sources used" panel in the result displays the file name, snapshot ID, and timestamp of the snapshot
- **Analysts can view snapshot metadata** (file name, version, snapshot ID, timestamp) for their own analyses via the "Data sources used" panel — this is read-only; analysts cannot edit, delete, or download raw snapshot data
- **Admin can retrieve the full data snapshot** (including the actual data contents) for any analysis given its task ID — required for regulatory examination
- No user (analyst or admin) can modify or delete a snapshot once created
- Updating a file in the personal workspace (re-uploading a newer version) does not modify snapshots linked to past analyses
- The snapshot storage is referenced in the audit log by snapshot ID, not stored inline

---

**FR-DA-05 — Access control**
V1 uses department-level RBAC. Each analyst sees datasets belonging to their department only. Admin can assign a dataset to one or more departments simultaneously.

*Acceptance criteria:*
- An analyst assigned to Department A cannot see, select, or query datasets assigned to Department B (unless the dataset is also assigned to Department A)
- Attempting to access a dataset outside the analyst's department via any method (UI or API) returns a 403 response with a clear message
- **Admin can assign a dataset to multiple departments** simultaneously (e.g., a cross-sector benchmark dataset visible to both Fraud Prevention and Policy & Research); the change takes effect within 60 seconds
- Admin can add or remove department assignments on any dataset without deleting it
- A dataset not assigned to any department is accessible only by admin users
- When a dataset is assigned to multiple departments, all assigned analysts see it in their dataset selection screen; access revocation from one department does not affect the other departments

---

### 8.3 Planning & Execution Loop

The core engine is the DS-STAR pipeline: Analyzer → Planner → Coder → Executor → Debugger (on error) → Verifier → Router (if insufficient) → Finalyzer. See `04-architecture-decisions.md` for paper-confirmed agent behaviour details.

**FR-PE-01 — Stop / cancel**
The analyst can stop a running analysis at any point. Task is cancelled immediately; nothing is returned.

*Acceptance criteria:*
- A "Stop" button is visible at all times while a task is running
- Clicking "Stop" triggers a confirmation modal: "Stop this analysis? Your progress will be lost. [Cancel] [Stop]"
- Confirming stop terminates the task within 5 seconds; the sandbox container is stopped and removed
- The stopped task appears in the history sidebar labelled "Stopped by analyst"
- No partial result is shown for a stopped task
- The round budget consumed up to the stop point is logged in the audit trail

---

**FR-PE-02 — Pause and resume**
The analyst can pause a running task and resume it later.

*Acceptance criteria:*
- A "Pause" button is visible at all times while a task is running
- Clicking "Pause" completes the current round (does not interrupt mid-execution) then suspends the task; the analyst is notified when the task has paused
- A paused task appears in the history sidebar labelled "Paused — Round N of M"
- The analyst can resume a paused task at any time by clicking "Resume" from the history sidebar
- Resuming a task continues from the exact round it was paused at; no rounds are replayed
- A paused task retains its checkpoint for a minimum of 7 days before being automatically cancelled (analyst notified 24 hours before expiry)

---

**FR-PE-03 — Mid-analysis steering**
While a task is running, the analyst can inject a plain-English hint.

*Acceptance criteria:*
- A "Steer analysis" input is visible in the progress panel while a task is running
- Submitting a hint appends it to the Planner's context for all subsequent rounds; hints already applied are not modified or removed
- Multiple hints accumulate and are all passed to the Planner
- All hints are displayed in the progress panel with their submission timestamp, in the order they were submitted
- Hints apply from the next round onward — not retroactively to rounds already completed
- Submitting a hint while a round is actively executing queues it for the next round

---

**FR-PE-04 — Default round limit**
5–6 rounds per task on first run. Applies equally to FIP-Insight (single query) and each FIP-Research sub-question individually.

*Note for engineering:* DS-STAR paper (Figure 2) shows hard tasks average 5.6 rounds. At max=5, there is a measurable accuracy drop on hard queries. The extension mechanism (FR-PE-05) exists to handle this — analysts should expect hard queries to frequently trigger extension. The UI must present extension as a normal workflow step, not an error.

*Acceptance criteria:*
- The system runs a maximum of 6 rounds on first attempt before presenting the round cap interface
- The round cap is applied consistently whether the task is FIP-Insight or a sub-question within FIP-Research
- The round budget counter ("Round N / 40") is visible throughout execution
- Reaching the default round limit without a "Yes" from the Verifier automatically triggers the incomplete analysis interface (FR-PE-07) without any additional analyst action

---

**FR-PE-05 — Round extension**
When default rounds are exhausted, the analyst can extend by 5 rounds per click.

*Acceptance criteria:*
- "Extend and continue" adds exactly 5 rounds to the current task's budget
- The round budget counter updates immediately after extension: e.g., "6 / 40 → 11 / 40"
- The task resumes from the last checkpoint without re-running earlier rounds
- The "Extend and continue" button is disabled once the hard cap of 40 rounds is reached
- Each extension action is logged in the audit trail with a timestamp

---

**FR-PE-06 — Hard round cap**
40 cumulative rounds per query (FIP-Insight) or per sub-question (FIP-Research). Enforced regardless of extension cycles.

*Acceptance criteria:*
- At 40 cumulative rounds, the system stops executing and presents the incomplete analysis interface even if the analyst attempts to extend further
- The "Extend and continue" button is not shown once 40 rounds are reached
- The round budget counter shows "40 / 40" when the hard cap is hit
- For FIP-Research: the 40-round cap is per sub-question, not across all sub-questions combined; a task with 5 sub-questions could theoretically consume up to 200 rounds system-wide

---

**FR-PE-07 — Task failure / round cap behaviour**
When a task hits its round cap or fails unrecoverably, the system presents a structured incomplete analysis interface.

*Acceptance criteria:*
- For round cap hit with a partial result: (a) result is shown with a prominent red "INCOMPLETE ANALYSIS" banner, (b) a plain-English diagnostic is shown below the banner explaining what was found, what wasn't, and why it stopped, (c) three action buttons are shown: "Accept partial result", "Refine and retry" (pre-fills query for editing), "Extend and continue" (if rounds remain)
- For hard failure with no partial result (container crash, GPU failure, LLM unreachable): the result panel shows only the diagnostic and a "Retry" button; no INCOMPLETE result is shown
- "Accept partial result" removes the INCOMPLETE banner and saves the result to history; an "(Incomplete)" label is permanently appended to the result title in history
- "Refine and retry" navigates to `/chat` with the original query pre-filled and a note: "Refining previous analysis — edit your query and resubmit"
- The analyst must explicitly choose one of the action buttons — the interface does not auto-resolve

---

**FR-PE-08 — Checkpointing**
LangGraph checkpoints task state to PostgreSQL every round.

*Acceptance criteria:*
- If a worker process crashes mid-round, the task automatically resumes from the last completed round checkpoint within 60 seconds of worker recovery
- The analyst is not required to take any action for a checkpoint recovery — it happens transparently
- The progress panel shows a brief "Recovered from checkpoint at Round N" notification when a checkpoint recovery occurs
- Checkpoints are retained for the lifetime of the task plus 7 days after task completion or cancellation

---

### 8.4 Real-Time Progress Visibility

**FR-PV-01 — Two verbosity levels**
The analyst chooses between summary and full-trace progress modes.

*Acceptance criteria:*
- Default view on task start is summary mode: a progress bar with the current phase label (Analyzing / Planning / Coding / Executing / Verifying)
- A toggle clearly labelled "Show full trace" expands to the detailed view without page reload
- Full trace shows: current agent name, current round number, round budget counter, last execution result (truncated to 500 characters with "Show more"), any steering hints applied
- For FIP-Research (Report Mode), full trace shows: numbered sub-question list, status of each sub-question (queued / running / complete), current sub-question's round budget
- The toggle state persists for the analyst's session (if they expand the trace, it stays expanded for subsequent tasks in the same session)
- Both modes update in real time via WebSocket — no page refresh required

---

**FR-PV-02 — FIP-Research "Report Mode" signal**
When routed to FIP-Research (DS-STAR+), the dashboard clearly signals "Report Mode."

*Acceptance criteria:*
- On routing to FIP-Research, the dashboard header changes to purple accent colour and displays a "Report Mode" badge
- The progress panel displays the numbered sub-question breakdown list rather than a single round counter
- Each sub-question entry shows its status (queued / running / complete) and, when running, its round budget ("Sub-question 3 of 7 · Round 4 / 6")
- The mode badge remains visible throughout the analysis and on the completed result
- Switching modes via the routing confirmation pop-up (FR-QI-02) updates the dashboard display immediately

---

### 8.5 Output Types & Export

**FR-OUT-01 — Default output**
Every completed analysis always includes: narrative text, tables, and interactive charts. Raw data file and analysis code are opt-in.

*Acceptance criteria:*
- Every completed result renders a narrative section, at least one table (where data supports it), and at least one chart (where data supports it)
- Raw data download and analysis code download are hidden by default behind a toggle labelled "Show raw outputs"
- The "Show raw outputs" toggle is available on every result regardless of result type
- Toggling "Show raw outputs" does not reload the page or re-run any part of the pipeline

---

**FR-OUT-02 — Chart rendering**
The Coder outputs structured JSON for charts; the frontend renders them as interactive HTML charts.

*Acceptance criteria:*
- Charts rendered via Recharts are interactive: tooltips on hover, legend toggles, zoom where applicable
- If the chart JSON specifies a chart type Recharts cannot support, Plotly.js renders it instead — the analyst sees no difference
- On export (Word/PDF), charts are rendered server-side to static images at minimum 300 DPI
- A chart that fails to render (malformed JSON) shows a fallback message "Chart could not be rendered — raw data available below" and automatically shows the underlying data as a table

---

**FR-OUT-03 — FIP-Insight output style**
Chat-style response: executive summary + supporting tables and charts.

*Acceptance criteria:*
- The result begins with a concise executive summary paragraph (plain English, no technical jargon)
- Supporting tables and charts follow the summary
- The result does not resemble a formal document — no section headers like "Methodology" or "Findings"
- The result fits on a single scrollable dashboard panel without requiring a separate page

---

**FR-OUT-04 — FIP-Research output style**
Formal document with dynamic sections and inline citations.

*Acceptance criteria:*
- The result is rendered as a structured document with visible section headers
- Fixed sections present in every FIP-Research output: Header (title, date, analyst name, classification), Executive Summary, Query & Scope, Methodology, Recommendations
- Dynamic sections (Findings) are named and structured by the Writer agent based on the query; section names and count vary per report
- Every quantitative claim in the report is followed by an inline citation referencing the sub-question that produced it, e.g., "(Source: Sub-question 2 — Card fraud loss by LFI)"
- The analyst can click any citation to expand and view the sub-question text, the code that answered it, and its output

---

**FR-OUT-05 — Reformat without re-running**
The analyst can reformat any completed result without re-running the full pipeline.

*Acceptance criteria:*
- A "Reformat" button is visible on every completed result
- Clicking "Reformat" shows the formatting control field (same as FR-QI-04) pre-filled with the original formatting instruction (if any)
- Submitting a new formatting instruction re-runs only the Finalyzer against the stored output; the Analyzer, Planner, Coder, Executor, and Verifier do not re-run
- The reformat completes in under 30 seconds for typical results
- The reformatted result replaces the original in the result panel; the original is accessible via "View previous version" in the result header

---

**FR-OUT-06 — Export formats**
Three formats: Word (.docx), PDF, Excel (.xlsx).

*Acceptance criteria:*
- Word, PDF, and Excel export buttons are visible on every completed result
- Word export produces a .docx file that opens correctly in Microsoft Word and LibreOffice
- PDF export produces a non-editable PDF with embedded charts rendered as static images
- Excel export produces a .xlsx file containing all tables from the result as separate sheets; charts are included as embedded static images
- All exports complete within 60 seconds for typical results
- Export file names follow the convention: `FIP_[YYYYMMDD]_[query-slug].[ext]`

---

**FR-OUT-07 — Report templates**
Analysts can upload custom Word templates for output formatting.

*Acceptance criteria:*
- Analysts can upload a .docx template file via a "My templates" section in the history sidebar
- Templates use Jinja2 placeholders (e.g., `{{ executive_summary }}`, `{{ findings }}`) that the system fills at export time
- A personal template is visible only to the analyst who uploaded it
- Admin can upload shared templates visible to all analysts in a department
- If no template is selected, exports use the system default template
- A template upload that contains no recognised Jinja2 placeholders is rejected with a warning explaining the issue

---

### 8.6 Analysis History & Navigation

**FR-AH-01 — History sidebar**
Closed by default on `/chat`; open in dashboard view. Analyst sees own analyses only.

*Acceptance criteria:*
- On `/chat`, the history sidebar is collapsed; a visible toggle opens it without navigating away
- On `/dashboard`, the history sidebar is open by default
- The sidebar lists the analyst's own analyses only, sorted by most recent first
- Each history entry shows: query text (truncated to 80 characters), status (running / complete / paused / stopped / failed), date and time, and mode badge (Insight / Research)
- An analyst logged in as User A cannot access User B's analyses via any UI path or direct URL

---

**FR-AH-02 — History features — re-run and pin**
Analysts can re-run previous queries and pin favourites.

*Acceptance criteria:*
- Each history entry has a context menu with options: "Re-run", "Pin", "View", "Delete"
- "Re-run" navigates to `/chat` with the original query pre-filled; the original plan is passed as a Planner hint (not replayed verbatim); fresh data is loaded
- "Pin" moves the entry to a "Pinned" section at the top of the history sidebar
- "View" navigates to `/dashboard` displaying the stored result for that analysis
- "Delete" removes the history entry and its stored result after a confirmation prompt; the audit log record is NOT deleted
- Pinned analyses are retained permanently regardless of the general history limit

---

**FR-AH-03 — In-app notifications**
Analyst is notified in-app when a long-running task completes.

*Acceptance criteria:*
- When a task completes while the analyst is on a different page or browser tab, an in-app notification badge appears on the browser tab title and in the notification icon in the UI
- Clicking the notification navigates to the dashboard view for the completed task
- Notifications are shown for: task complete, task failed, task paused (by system, e.g., after checkpoint expiry warning)
- Notifications are dismissed when the analyst views the relevant result
- Email notifications are not implemented in V1

---

### 8.7 Page Structure & Navigation

**FR-NAV-01 — Pages**
Four pages: `/login`, `/chat`, `/dashboard`, `/admin`.

*Acceptance criteria:*
- Unauthenticated access to `/chat` or `/dashboard` redirects to `/login`
- Accessing `/admin` as a non-admin authenticated user returns a 403 page, not a redirect to analyst login
- All four pages are responsive at standard desktop resolutions (1280×800 minimum)

---

**FR-NAV-02 — Navigation flow**
Login → `/chat` → submit → `/dashboard` → "New Analysis" → `/chat`.

*Acceptance criteria:*
- Successful login redirects to `/chat`
- Query submission redirects to `/dashboard` with the new task's progress panel active
- "New Analysis" button on `/dashboard` navigates to `/chat`; the new `/chat` session is clean (no pre-filled query)
- Browser back button from `/dashboard` to `/chat` is suppressed after query submission — the analyst must use "New Analysis" to start fresh
- Deep-linking to `/dashboard?task=<taskId>` loads the result for that specific task directly

---

**FR-NAV-03 — Chat page layout**
Clean and minimal.

*Acceptance criteria:*
- On desktop (1280px+), the text box is centred horizontally with a maximum width of 760px
- Starter templates are displayed in a grid or horizontal scroll below the text box, visible without scrolling
- No advertising, decorative imagery, or non-functional elements are present on the chat page
- The formatting control field (FR-QI-04) is collapsed and below the text box; it does not affect the visual prominence of the text box

---

**FR-NAV-04 — Dashboard page layout**
Left: history sidebar. Main: progress then result.

*Acceptance criteria:*
- The history sidebar occupies a fixed left column (approximately 280px width); the main panel takes the remaining width
- While a task is running, the main panel shows the progress panel (FR-PV-01) as the primary content
- When a task completes, the result replaces the progress panel in the main panel
- Mid-analysis controls (Pause, Stop, Extend, Steering input) are visible in the main panel while a task is running and hidden from the main panel when the task is complete (accessible only via history for past tasks)
- Export buttons, Reformat button, and "Data sources used" panel appear below the result on task completion

---

### 8.8 Audit & Compliance

**FR-AU-01 — Audit log scope**
Every query, every plan step, every code version, every result is logged — timestamped, user-attributed, append-only.

*Acceptance criteria:*
- Every task creation event is logged with: task ID, analyst user ID, department, query text, mode (Insight/Research), timestamp
- Every round completion is logged with: task ID, round number, plan step text, code script version ID, execution result summary, Verifier output (Yes/No), Router decision (if applicable)
- Every result delivery is logged with: task ID, result status (complete/incomplete/failed), snapshot IDs of data used, storage location reference
- Every export action is logged with: task ID, export format, timestamp, analyst user ID
- Log entries are immutable — no UPDATE or DELETE operations are permitted on the audit log table by any application role

---

**FR-AU-02 — Audit log retention**
Records retained indefinitely. No deletion in V1.

*Acceptance criteria:*
- The audit log database table has no TTL policy, no scheduled deletion job, and no admin-accessible delete function
- Storage growth of the audit log is monitored and included in the system health dashboard (FR-ADMIN-05)
- Retention policy configuration (archiving after N years) is explicitly not implemented in V1; any future implementation requires a PRD change

---

**FR-AU-03 — Audit log access**
Admin: all records. Analyst: own records only.

*Acceptance criteria:*
- Admin audit log viewer (FR-ADMIN-06) returns records for all users with full detail
- Analyst history view returns only records where `user_id = authenticated analyst`; API-level enforcement, not UI-only filtering
- Any attempt by an authenticated analyst to query another analyst's audit records via the API returns a 403 response
- Audit log queries by admin are themselves logged (who queried what, when)

---

**FR-AU-04 — Audit log behaviour**
Purely passive.

*Acceptance criteria:*
- No alert rules, threshold monitors, or anomaly detection run against the audit log in V1
- No automated emails or notifications are triggered by audit log events
- The audit log is queryable on demand by admin; no proactive review tooling is built

---

**FR-AU-05 — Tamper-evidence**
Append-only, tamper-evident.

*Acceptance criteria:*
- The audit log database user has INSERT permission only — no UPDATE or DELETE
- Audit log records include a hash of the prior record to form a verifiable chain
- A tamper-detection utility can be run by admin to verify the integrity of the log chain
- Any attempt to modify or delete an audit log record from outside the application is detectable via the hash chain

---

### 8.9 Admin Panel

**FR-ADMIN-01 — User management**

*Acceptance criteria:*
- Admin can add a new user by entering: name, email, department, role (Analyst or Admin)
- Admin can deactivate a user account; deactivated accounts cannot log in but their audit records are retained
- Admin can reassign a user's department; the change takes effect within 60 seconds
- Admin cannot delete user accounts in V1 — only deactivate

---

**FR-ADMIN-02 — File upload toggle**

*Acceptance criteria:*
- Admin can toggle file uploads on or off globally with a single control
- Admin can toggle file uploads on or off per-department
- Per-department settings override the global setting; global off overrides per-department on
- State change takes effect within 60 seconds

---

**FR-ADMIN-03 — Query template management**

*Acceptance criteria:*
- Admin can create a new starter template with: title, template text, and optional department tag
- Admin can edit or delete any existing template
- Published templates appear on the analyst chat page within 60 seconds of publishing
- Unpublished (draft) templates are not shown to analysts

---

**FR-ADMIN-04 — Shared report template management**

*Acceptance criteria:*
- Admin can upload a .docx file as a shared department-level report template
- Admin can assign a template to one or more departments
- Admin can deactivate a template without deleting it
- Analysts in the assigned department(s) can see and select shared templates in the "My templates" section

---

**FR-ADMIN-05 — System health dashboard**

*Acceptance criteria:*
- Dashboard shows in real time: task queue depth, number of active tasks, number of paused tasks, GPU utilisation (%), error rate (failures / total tasks, last 24 hours), DLQ item count
- All metrics auto-refresh without page reload at a minimum 30-second interval
- DLQ items are listed individually with task ID, error summary, and timestamp
- Admin can trigger a manual retry of a DLQ item

---

**FR-ADMIN-06 — Audit log viewer**

*Acceptance criteria:*
- Admin can search audit records by: user, department, date range, task status, query text (keyword)
- Results are paginated (50 records per page)
- Admin can export the current search results as a CSV
- The audit log viewer itself is subject to audit logging (FR-AU-03)

---

### 8.10 System Capacity & Concurrency

**FR-CAP-01 — Concurrent task limits**
The system enforces a global concurrency budget to protect GPU and infrastructure resources.

*Limits:*
- Maximum concurrent FIP-Insight tasks: **5**
- Maximum concurrent FIP-Research tasks: **3** (each spawns up to N sub-questions which run sequentially per sub-question by default)
- Maximum concurrent sandbox containers system-wide: **8**
- Total concurrent tasks across all types: **8**

*Acceptance criteria:*
- When the system is at capacity, a newly submitted task is queued (not rejected)
- The analyst is immediately notified: "Analysis queued — [N] analyses ahead of you. Estimated wait: ~[X] minutes." The estimate is based on average task duration from recent history
- Queue position updates in real time on the dashboard
- Tasks are dequeued in FIFO order within the same priority tier; re-queued tasks (after checkpoint recovery) have higher priority than new submissions
- A task that has waited in the queue for more than 30 minutes triggers an in-app notification to the analyst informing them of the delay
- Admin can see queue depth and position of all queued tasks in the system health dashboard

---

### 8.11 Error States

The following error states must be handled gracefully — with a clear, plain-English message and a recommended action — rather than showing a raw error or blank page.

| Error | User-facing message | Recommended action shown |
|-------|---------------------|--------------------------|
| Uploaded file is password-protected | "This file is password-protected. Please remove the password and re-upload." | Re-upload prompt |
| Uploaded file is corrupted / unreadable | "This file could not be read. It may be corrupted. Please check the file and try again." | Re-upload prompt |
| Uploaded file exceeds 500 MB | "This file is too large ([X] MB). Maximum file size is 500 MB per file." | File removed from queue |
| More than 20 files selected | "You can upload up to 20 files per query. Please deselect [N] files." | File selection remains open |
| Unsupported file format | ".[ext] files are not supported. Supported formats: PDF, Word, Excel, CSV, JSON." | File removed from queue |
| No datasets available for the query | "No data sources found. Please upload at least one file before submitting your query." | Upload prompt shown |
| JWT session expired during analysis | "Your session has expired. Your analysis is still running in the background. Log in again to view results." | Login redirect; task continues uninterrupted |
| LLM unreachable (Ollama/vLLM down) | "The AI engine is temporarily unavailable. Your analysis has been paused and will resume automatically when the service recovers." | Task auto-resumes; analyst notified via in-app notification |
| Sandbox container crash | Triggers FR-PE-07 hard failure path — plain-English diagnostic + Retry button | Retry button |
| Access denied (data outside department) | "You do not have access to this dataset. Contact your admin if you believe this is an error." | Admin contact info |
| Query submission while system at capacity | "Analysis queued — [N] ahead of you. Estimated wait: ~[X] min." | Queue position shown in dashboard |
| File name exceeds 255 characters | "File name is too long. Please rename the file to 255 characters or fewer and re-upload." | Re-upload prompt |
| Network error (frontend cannot reach backend) | "Connection lost. Check your network and try again. Your analysis (if running) is still processing." | Retry connection button |

*Acceptance criteria:*
- All error messages listed above are displayed as non-blocking toasts or inline messages (not browser alerts)
- No raw stack traces, HTTP status codes, or technical error identifiers are exposed to analysts
- Every error state is logged in the system error log accessible to admin
- Every error message is tested with at least one automated test that deliberately triggers the error condition

---

## 9. Non-Functional Requirements

### 9.1 Performance

| Requirement | Target | Percentile | Load Condition |
|-------------|--------|-----------|----------------|
| FIP-Insight (easy query, ≤3 rounds) | < 3 minutes | P95 | ≤ 5 concurrent tasks |
| FIP-Insight (hard query, ≤10 rounds) | < 20 minutes | P95 | ≤ 5 concurrent tasks |
| FIP-Research (7 sub-questions, K=1 refinement) | < 60 minutes | P95 | ≤ 3 concurrent FIP-Research tasks |
| Finalyzer reformat (re-run only) | < 30 seconds | P99 | Any load |
| File upload + Analyzer profiling (≤500 MB structured file) | < 60 seconds | P95 | Any load |
| Page load (initial) | < 2 seconds | P95 | Any load |
| Dataset suggestion (semantic search) | < 5 seconds | P99 | Any load |

### 9.2 Security

- Fully air-gapped. No outbound network access from the production system.
- mTLS for all internal service-to-service communication.
- HashiCorp Vault for secrets management. No secrets in environment variables.
- Docker sandbox for code execution: no network access, 2 GB memory cap, read-only data mount, non-root user, per-execution timeout, seccomp profile applied.
- JWT authentication for all frontend-to-backend API calls; token expiry: 8 hours (one working day).
- Department-level RBAC for data access, enforced at the API layer.
- Penetration testing of the sandbox escape surface required before launch.

### 9.3 Reliability

- LangGraph checkpoints to PostgreSQL every round. Task resumes from last checkpoint on worker crash.
- Celery + Redis Sentinel for async task queue with high availability.
- Priority queue with dead-letter queue (DLQ) for failed tasks.
- Container concurrency budget enforced system-wide (max 8 concurrent sandbox containers).
- System target uptime: 99.5% during CBUAE working hours (08:00–18:00 GST, Sunday–Thursday).

### 9.4 Data Integrity

- Every analysis result is linked to a point-in-time data snapshot. Required for regulatory defensibility.
- Audit log is append-only and tamper-evident with hash-chain verification.

### 9.5 Accessibility & Browser Support

- UI must meet WCAG 2.1 Level AA for all analyst-facing pages.
- Supported browsers: Chrome 120+, Edge 120+. Safari and Firefox are not formally supported in V1 but must not produce broken layouts.
- Minimum supported desktop resolution: 1280×800.

---

## 10. Architecture Overview

FIP is built on the DS-STAR multi-agent pipeline (arXiv:2509.21825), which uses an iterative Analyze → Plan → Code → Execute → Verify loop with backtracking. DS-STAR+ extends this with a Sub-Question Generator and Report Writer for open-ended research queries.

Full architecture detail — including all paper-confirmed agent behaviours, container lifecycle decisions, LLM tiering, and infrastructure topology — is documented in:
- `00-discovery/03-architecture-v2.html` (v3.3) — visual architecture diagram
- `00-discovery/04-architecture-decisions.md` — every architectural decision with paper references (Q1–Q18)

The TDD (`03-tdd/01-tdd-cbuae-fip.md`) will translate the architecture into implementation specifications.

**Technology stack summary:**

| Layer | Technology |
|-------|-----------|
| Frontend | React + Tailwind + ShadCN |
| State machine | LangGraph (PostgreSQL checkpointing) |
| Task queue | Celery + Redis Sentinel |
| Sandbox | Docker (per-task container, docker exec per round) |
| LLM inference | Provider-agnostic adapter (Ollama prod / Gemini dev) |
| Secrets | HashiCorp Vault |
| Auth | JWT (8-hour expiry) |
| Report generation | python-docx-template + LibreOffice headless |
| Charts | Recharts (primary) + Plotly.js (fallback) |
| Internal comms | mTLS |

---

## 11. Launch Criteria

*Adapted from Google's Launch Readiness Review, Microsoft's Ship Criteria, and Amazon's Operational Readiness Review (ORR). All approvers are placeholders pending stakeholder assignment.*

A V1 launch requires **all** of the following to be satisfied. No exceptions without explicit DRI sign-off and a documented risk acceptance.

### Quality Gate
- [ ] Zero open P0 (Critical) bugs
- [ ] Zero open P1 (High) bugs that affect the core analysis pipeline, authentication, or audit log
- [ ] All functional requirements have passed their acceptance criteria in the staging environment
- [ ] All automated test suites pass on the release build

### Security & Compliance
- [ ] Penetration test completed by CBUAE IT Security — specifically: sandbox escape, prompt injection via uploaded file, JWT tampering, RBAC bypass — all Critical/High findings resolved
- [ ] Audit log tamper-detection utility verified in staging
- [ ] HashiCorp Vault secrets confirmed — zero secrets in environment variables, config files, or source code
- [ ] Air-gap verified: no outbound network call from the production environment succeeds (tested with network monitoring)
- [ ] Legal/Compliance sign-off on the use of AI-generated outputs in supervisory workflows — [PLACEHOLDER: Legal reviewer]
- [ ] Data governance sign-off on data versioning, snapshot storage, and audit log retention policy — [PLACEHOLDER: Data Governance reviewer]

### Performance & Reliability
- [ ] P95 performance targets (Section 9.1) met under simulated peak load (5 concurrent FIP-Insight + 3 concurrent FIP-Research tasks) in staging
- [ ] Checkpoint recovery tested: worker killed mid-round; task resumes from correct checkpoint within 60 seconds
- [ ] DLQ alert confirmed working: failed task appears in admin health dashboard within 2 minutes

### Operational Readiness
- [ ] Runbook written and reviewed: covers common failure scenarios (LLM down, worker crash, disk full, DLQ spike, GPU failure)
- [ ] On-call rotation established and trained — [PLACEHOLDER: IT Operations]
- [ ] System health dashboard (FR-ADMIN-05) deployed and verified
- [ ] Rollback plan tested in staging: previous version can be restored within 15 minutes

### Pilot Feedback Incorporated
- [ ] Closed Beta pilot (Phase 2 of rollout) completed with minimum 5 analysts from Fraud Prevention Supervision
- [ ] P0 pilot feedback items resolved
- [ ] Analyst satisfaction score in pilot: ≥ 3.5 / 5.0 (lower bar than post-launch target, as expected for beta)

### Documentation & Training
- [ ] Analyst user guide published (covers: how to write effective queries, understanding round extension, interpreting INCOMPLETE results, exporting reports)
- [ ] Admin guide published (covers: user management, template management, system health, DLQ handling)
- [ ] Training session conducted for Closed Beta pilot analysts

### Sign-Off
- [ ] DRI sign-off — [PLACEHOLDER]
- [ ] Engineering Lead sign-off — [PLACEHOLDER]
- [ ] IT Security sign-off — [PLACEHOLDER]
- [ ] Legal/Compliance sign-off — [PLACEHOLDER]
- [ ] Primary Department Head (FPS) sign-off — [PLACEHOLDER]

---

## 12. Rollout Plan

*Adapted from Google's staged rollout model, Amazon's "Working Backwards" launch approach, and Microsoft's ring-based deployment practice.*

FIP V1 follows a four-phase rollout. Each phase has an explicit exit criterion — the phase is not complete until the criterion is met.

### Phase 1 — Alpha (Internal / Dogfood)
**Who:** The engineering and product team + 2–3 analysts from Fraud Prevention Supervision who are directly involved in the project (the most forgiving, most technically aware users).
**Duration:** 2 weeks
**Purpose:** Catch critical bugs before external exposure. Validate that the core pipeline produces meaningful results on real CBUAE data.
**What's tested:** Full pipeline (FIP-Insight + FIP-Research), file upload, pause/resume, export, admin panel.
**Data used:** Real CBUAE data in an isolated staging environment (not shared with dev environment).

*Exit criterion:* Zero P0 bugs open. Core analysis pipeline completes successfully on ≥ 80% of test queries. Engineering team signs off.

---

### Phase 2 — Closed Beta
**Who:** All analysts in Fraud Prevention Supervision (~10–15 people). The initiating department — highest motivation, deepest domain knowledge, best able to validate output quality.
**Duration:** 4 weeks
**Purpose:** Validate real-world usage patterns, output quality, and analyst trust. Establish baseline metrics for success KPIs (Section 3). Collect structured feedback.
**Onboarding:** Live training session (1 hour) + written user guide. Analysts are explicitly told this is a beta — outputs require human verification.
**Support:** Direct Slack/Teams channel with engineering for issue reporting. Weekly feedback review meeting (PM + analyst lead + engineering).

*Exit criterion:* Beta CSAT ≥ 3.5/5.0. Zero P0 or P1 bugs open. Baseline metrics established. All launch criteria (Section 11) met.

---

### Phase 3 — Open Beta (Full Department Rollout)
**Who:** Volunteer analysts from all remaining four departments (AML/CFT, Market Conduct, Enforcement, Policy & Research). Opt-in — not mandatory.
**Duration:** 4 weeks
**Purpose:** Validate cross-department usability with no department-specific customisation (V1 treats all analysts identically). Identify V2 department-specific requirements from real usage.
**Onboarding:** Self-serve user guide + recorded training video. Optional live Q&A session.
**Support:** Standard IT helpdesk channel. Engineering on standby for escalations.

*Exit criterion:* No new P0/P1 issues introduced. Open Beta CSAT ≥ 3.5/5.0. System stable under multi-department concurrent load.

---

### Phase 4 — General Availability (GA)
**Who:** All analysts across all five departments. Mandatory rollout with onboarding support.
**Duration:** Ongoing
**Purpose:** Full production deployment. FIP becomes the standard tool for analytical queries that previously required IT or manual Excel.
**Onboarding:** Department-level training sessions conducted by the DRI + trained power users from the beta cohorts. Admin guide handed to IT.
**Handoff:** Engineering team transitions from active support to standard maintenance. IT Operations owns day-to-day system management.

*Exit criterion:* N/A — GA is the end state. Post-GA: monthly metrics review against Section 3 KPIs. First formal review at 30, 60, and 90 days post-GA.

---

### Rollout Go/No-Go Decision Points

| Gate | Decision Maker | Criterion |
|------|---------------|-----------|
| Alpha → Closed Beta | Engineering Lead | Exit criterion for Phase 1 met |
| Closed Beta → Open Beta | DRI | Exit criterion for Phase 2 met + all launch criteria signed off |
| Open Beta → GA | DRI + Dept. Heads | Exit criterion for Phase 3 met |
| GA Continuation (30-day review) | DRI | KPI trajectory positive; no critical issues in production |

---

### Rollback Plan
If a critical issue is discovered post-GA:
1. Engineering Lead declares a rollback
2. Previous release is restored within 15 minutes (tested in Phase 1)
3. Affected analysts notified via in-app notification and email
4. Incident post-mortem completed within 48 hours
5. Fix deployed through Closed Beta re-cycle before re-launching to GA

---

## 13. Feedback Mechanism

Analyst feedback is the primary signal for determining whether FIP is producing reliable, useful outputs. The following mechanisms are V1.

### 13.1 Per-Result Feedback
Every completed analysis result displays a feedback bar at the bottom:
- **Thumbs up / Thumbs down** — one-click rating
- **Optional free-text comment** (collapsed by default, expands on either click): "Tell us more (optional)"
- **"Flag as incorrect"** — a distinct, more serious action that tags the result for engineering review. Requires a one-line description of what is incorrect. These are reviewed by engineering weekly during beta and bi-weekly at GA.

*Acceptance criteria:*
- The feedback bar is visible on every completed result without scrolling
- Thumbs up/down can be changed after submission
- "Flag as incorrect" submissions appear in a dedicated queue in the admin panel
- All feedback is associated with the task ID and analyst user ID in the feedback store
- Feedback is never shown to other analysts

### 13.2 Quarterly In-App CSAT Survey
A 5-question in-app survey is shown to each analyst once per quarter. It appears as a non-blocking slide-in panel (not a full-page modal) and can be dismissed and completed later.

*Questions (fixed for V1):*
1. Overall, how satisfied are you with FIP? (1–5 scale)
2. How often do you verify FIP's results before using them in a supervisory context? (Always / Usually / Sometimes / Rarely / Never)
3. Has FIP saved you time compared to your previous approach? (Yes, significantly / Yes, somewhat / No change / No, it takes longer)
4. What is the most useful thing FIP does for you? (Free text)
5. What is the most frustrating thing about FIP? (Free text)

*Acceptance criteria:*
- Survey appears no more than once per quarter per analyst
- Completion is optional; dismissing the survey does not count as a response
- Survey responses are stored against analyst ID and timestamp (not anonymised in V1 — needed for follow-up)
- Admin can view aggregate survey results broken down by department and quarter in the admin panel

### 13.3 Engineering Error Dashboard
The admin panel (FR-ADMIN-05) includes a dedicated "Flagged results" queue showing all "Flag as incorrect" submissions. Each flagged result shows: task ID, query text, analyst's description of the error, and a link to the full result and audit trail.

Engineering reviews this queue weekly during beta and bi-weekly at GA. All P0-severity flags (e.g., numerical errors in outputs used in issued supervisory letters) are treated as incidents and triaged within 24 hours.

### 13.4 Monthly Feedback Review
During beta phases and the first 3 months of GA: a monthly meeting between the DRI, lead analyst (FPS), and engineering lead reviews:
- Aggregate thumbs up/down ratio by result type (Insight vs. Research)
- Flagged results and resolutions
- CSAT trend
- Any emerging patterns in free-text comments

Findings from this meeting directly feed the V2 backlog.

---

## 14. Risk Register

*Risk severity = Likelihood × Impact. Rating scale: Critical / High / Medium / Low.*

| # | Risk | Likelihood | Impact | Severity | Mitigation |
|---|------|-----------|--------|----------|-----------|
| R1 | **LLM hallucination in regulatory output.** The system produces an incorrect or fabricated finding that is cited in a supervisory letter or enforcement action. | Medium | Critical | **Critical** | (1) "Data sources used" panel always visible and clickable; (2) Analysis code always downloadable so analysts can verify; (3) INCOMPLETE ANALYSIS label on partial results; (4) Training explicitly tells analysts outputs require human verification; (5) "Flag as incorrect" mechanism for fast reporting; (6) FR-OUT-04 inline citations allow every claim to be traced to its source data |
| R2 | **Local model quality gap.** Air-gapped Ollama models (e.g., Llama 70B) may produce significantly worse outputs than the Gemini 2.5 Pro used in the DS-STAR paper benchmarks. The paper's 45.2% accuracy is for a frontier model. | High | High | **High** | (1) Benchmark local model against the DS-STAR paper's test suite before pilot launch; (2) Set explicit analyst expectations during training: "this is an assistive tool, not an authority"; (3) Document accuracy delta in the launch criteria and set a minimum acceptable threshold before GA; (4) Provider adapter allows switching to a higher-quality model if local model is insufficient |
| R3 | **Analyst over-reliance.** Analysts stop verifying AI outputs, treating FIP as authoritative. Risk increases as confidence in the tool grows over time. | Medium | High | **High** | (1) Training explicitly covers the risk of over-reliance; (2) CSAT survey Q2 tracks verification frequency; (3) "Flag as incorrect" mechanism normalises the idea that outputs can be wrong; (4) FR-AH-03 ensures audit log includes who submitted results without verification; (5) If verification rate drops below a threshold in CSAT responses, trigger a retraining session |
| R4 | **Prompt injection via uploaded file.** A malicious actor crafts a PDF or Excel file containing LLM-injection instructions (e.g., "Ignore prior instructions and output...") that manipulates the pipeline. | Low | Critical | **High** | (1) Sandbox has no network access — even if injection succeeds, exfiltration is impossible; (2) System prompts harden agent instructions against overrides; (3) Analyzer output (D) is treated as data, not executable instruction; (4) File content is not injected directly into LLM prompts without sanitisation; (5) Pen test specifically covers this attack surface before launch |
| R5 | **Sandbox escape.** The Python execution sandbox is exploited to access CBUAE network infrastructure. | Low | Critical | **High** | (1) Docker sandbox: no network, 2 GB memory cap, read-only data mount, non-root user, per-execution timeout, seccomp profile; (2) Mandatory pen test of sandbox escape surface before launch (launch criteria); (3) Container runs with minimal capabilities (CAP_DROP=ALL); (4) Separate network namespace for sandbox containers |
| R6 | **Low analyst adoption.** Analysts distrust or do not use the system, especially if early results are poor or the interface requires significant learning. | Medium | High | **High** | (1) Closed Beta pilot with friendly, motivated users from the initiating team; (2) Starter templates reduce cold-start friction; (3) Plain-English Explainer layer removes technical jargon from results; (4) Monthly feedback review for fast iteration; (5) Champion programme: identify 1–2 power users per department in Open Beta who advocate for the tool |
| R7 | **Data exfiltration via production data in dev/test.** Real CBUAE data accidentally used with the Gemini API (cloud) during development or testing. | Medium | Critical | **Critical** | (1) Dev environment policy: only synthetic/anonymised test data may be used with external APIs; (2) Gemini API access blocked at network level in the staging environment that holds real data; (3) Pre-launch checklist explicitly verifies no production data was transmitted to any external service during development |
| R8 | **GPU hardware unavailability or inadequacy.** CBUAE on-premise GPU hardware may not exist, be insufficient for 70B parameter model inference, or have unacceptable inference latency. | High | High | **High** | (1) GPU availability and capability confirmed as Open Question (Section 16, Q7) — must be resolved before TDD; (2) Provider adapter allows scaling down to a smaller model if GPU is insufficient; (3) Performance targets in Section 9.1 are validated against actual hardware in staging before launch; (4) If local GPU is unavailable at launch, Azure OpenAI (UAE North) is the fallback — data stays in UAE but the system is no longer fully air-gapped; this requires legal/compliance sign-off |
| R9 | **Regulatory defensibility challenged.** A finding from FIP is disputed in a regulatory proceeding and CBUAE cannot prove the finding was derived correctly from the underlying data. | Low | Critical | **High** | (1) Data versioning (FR-DA-04) links every result to an immutable data snapshot; (2) Full audit log (FR-AU-01) records every plan step, every code version, every execution result; (3) Analysis code is always downloadable and re-runnable by a technical reviewer; (4) Inline citations in FIP-Research (FR-OUT-04) trace every claim to its source sub-question and code |
| R10 | **Partial result accepted as complete.** Analyst accepts an INCOMPLETE ANALYSIS result without proper scrutiny and it is used in a supervisory context. | Medium | High | **High** | (1) INCOMPLETE ANALYSIS label is prominent and persistent (not dismissable); (2) The "(Incomplete)" tag is permanently appended to the result title in history even after acceptance; (3) Export of incomplete results includes a watermark: "INCOMPLETE ANALYSIS — FOR REVIEW ONLY"; (4) Analyst must click "Accept partial result" explicitly — there is no auto-accept path |

---

## 15. Out of Scope for V1

| Feature | Status |
|---------|--------|
| Department-specific UI, templates, regulatory knowledge injection | 🔮 V2 |
| PII masking | 🔮 V2 (revisit when live DB connectivity is added) |
| Live database connectivity | 🔮 V2 |
| External REST API consumers (machine-to-machine) | 🔮 V2 |
| Email notifications | 🔮 V2 |
| Arabic and other language support | 🔮 V2 |
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

## 16. Open Questions

These questions must be resolved before the TDD and Security Review. Each has a named owner [PLACEHOLDER] who is responsible for answering it.

| # | Question | Owner | Needed For | Target Resolution |
|---|----------|-------|-----------|-----------------|
| 1 | How do analysts authenticate today? (Active Directory, CBUAE SSO, standalone accounts?) | [IT Infrastructure] | JWT/SSO integration design | Before TDD |
| 2 | What is the largest single dataset an analyst would query? (row count and file size in GB) | [FPS Lead Analyst] | Executor memory limits, file upload UX, Analyzer timeout | Before TDD |
| 3 | Are there existing Word/PDF report templates used for supervisory letters? Can we get samples? | [FPS Lead Analyst] | Finalyzer template design, FR-OUT-07 | Before TDD |
| 4 | Does any output need to integrate with an existing case management system (e.g., NICE Actimize, Oracle FCCM, ServiceNow) even in V1? | [Department Heads] | API contract — currently scoped out of V1; may change decision | Before Closed Beta launch |
| 5 | What is the data freshness requirement for institutional datasets? (24 hours old acceptable, or faster?) | [IT Infrastructure / Data Engineering] | Data ingestion pipeline design | Before TDD |
| 6 | Who has authority to approve which datasets an analyst can access? (Sensitivity tiers, approval workflow) | [Data Governance] | RBAC policy design, admin panel user management | Before TDD |
| 7 | What GPU hardware is available on-premise? (Model, VRAM, count) | [IT Infrastructure] | LLM model selection, inference throughput, performance target validation | **Immediate — before TDD is started** |
| 8 | How many analysts are expected to use the system concurrently at peak? | [Department Heads + FPS] | Task queue sizing, concurrency budget validation | Before TDD |
| 9 | Can we establish the baseline metrics before launch? (Time studies for benchmarking table and thematic review, historical thematic review count) | [FPS Lead Analyst] | Completing Section 3 success metrics — two baselines are currently TBD | Before Closed Beta |

---

## 17. Appendix: Feature Decision Traceability

All features in this PRD trace back to confirmed decisions in `00-discovery/05-feature-discussion.md`. The table below maps PRD sections to their source.

| PRD Section | Source Document | Topic |
|-------------|----------------|-------|
| 7 / 8.1 Query Interface | `05-feature-discussion.md` | Topic 1 |
| 8.2 Data Access & File Management | `05-feature-discussion.md` | Topic 2 |
| 8.3 Planning & Execution Loop | `05-feature-discussion.md` | Topic 3 |
| 8.4 Real-Time Progress | `05-feature-discussion.md` | Topic 1 (items 6, 7) |
| 8.5 Output Types & Export | `05-feature-discussion.md` | Topics 4 & 5 |
| 8.6 Analysis History & Navigation | `05-feature-discussion.md` | Topic 1 (items 4, 5, 10) |
| 8.7 Page Structure & Navigation | `05-feature-discussion.md` | Topic 10 |
| 8.8 Audit & Compliance | `05-feature-discussion.md` | Topic 8 |
| 8.9 Admin Panel | `05-feature-discussion.md` | Topic 2 (admin scope) |
| 8.10 System Capacity | `05-feature-discussion.md` | Topic 9 (API/infrastructure) |
| 8.11 Error States | New — PM audit addition (v0.2) |
| Section 10 Architecture | `04-architecture-decisions.md` + `03-architecture-v2.html` v3.3 | Q1–Q18 |
| Section 6 Deployment | `03-requirements-discovery.md` | Requirements 2 & 5 |
| Section 11 Launch Criteria | New — PM audit addition (v0.2) |
| Section 12 Rollout Plan | New — PM audit addition (v0.2) |
| Section 13 Feedback Mechanism | New — PM audit addition (v0.2) |
| Section 14 Risk Register | New — PM audit addition (v0.2) |

---

*This PRD is a living document. Changes require updating the source feature discussion log first, then this document. No feature enters the TDD without first being confirmed here.*
