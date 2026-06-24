# Architecture Decisions & Q&A Log

**Branch:** `docs/product-lifecycle`  
**System:** CBUAE FIP — DS-STAR + DS-STAR+ Implementation  
**Purpose:** A living record of architectural questions raised during design, the answers derived from the paper, and our final decisions for the CBUAE deployment.

Each entry follows the pattern: **Question → What the paper says → Our decision → Rationale**.

---

## Q1: Does a new Docker container spin up for each execution round, or is one container reused across all rounds of a task?

**Date:** 2026-06-24

### What the paper says
The paper specifies that the Executor runs each script `sₖ` in an "isolated Docker sandbox" with specific constraints (no network, 2 GB memory cap, read-only data mount, non-root user, per-execution timeout). The paper does **not** prescribe whether the container is fresh per round or persistent for the task lifetime. The paper's formal concern is isolation and reproducibility, not container lifecycle efficiency.

The paper does specify one critical design: **the Coder always generates a complete, self-contained script `sₖ` each round** — not a delta or patch. `s₂` re-does everything `s₁` did, plus one more step. This means the execution environment is treated as stateless regardless of whether the container persists.

### Our decision
**One container per task, alive for all rounds.** Each round runs its complete `sₖ` via `docker exec` inside the already-running container. The container is started when the task begins and destroyed when the task completes, times out, or fails.

For DS-STAR+: **one container per sub-question**. Sub-questions do not share state, so each gets its own container that lives for the duration of that sub-question's DS-STAR inner loop.

### Rationale
| Factor | Per-round ephemeral | Per-task persistent (our choice) |
|--------|--------------------|---------------------------------|
| Cold-start cost | ~3s per container × 20 rounds × n sub-questions — can add minutes of pure overhead | One cold start per task |
| State leakage risk | Zero | Negligible — because `sₖ` always re-imports and re-computes everything from scratch, stale variables in a warm container produce the same result as a fresh one |
| Crash blast radius | A crash in round k doesn't affect round k+1 | A container crash kills the whole task — mitigated by LangGraph checkpointing (task resumes from last checkpoint in a new container) |
| Complexity | Simple but slow | Requires container lifecycle management per task |

The complete-script design (paper's own choice) is what makes per-task persistence safe. Without it, warm container state would be a correctness risk.

---

## Q2: Does the Analyzer run once per task, once per round, or once per session?

**Date:** 2026-06-24

### What the paper says
The Analyzer runs **once per task, before any planning begins**. The paper's pipeline explicitly sequences it as the first step: `Analyzer → Planner → Coder → Executor → ...`. The Analyzer's output `D` (per-file descriptions) is computed once and then passed into the Planner and Coder as fixed context for all subsequent rounds.

The ablation study confirms this is the single most critical component: removing the Analyzer drops hard-task accuracy from 45.2% → 26.98% (−18 pp). It is the foundation.

### Our decision
**Runs once per DS-STAR task.** For DS-STAR+, the Analyzer runs once before the Sub-Question Generator and `D` is shared across all sub-questions (they all query the same data files). Sub-questions do not re-run the Analyzer independently.

### Rationale
- Data files don't change during a task — there is no new information to discover mid-run.
- Re-running the Analyzer each round would be expensive (profiling large CSV files is slow) and produce identical output.
- For DS-STAR+, sharing `D` across sub-questions is correct: all sub-questions are decompositions of the same open-ended query over the same data.

---

## Q3: Why does `sₖ` include everything from `s₀`? Doesn't this mean data is reloaded from disk every round?

**Date:** 2026-06-24

### What the paper says
The Coder is explicitly designed to generate a **complete, cumulative script** each round — not a delta. The paper states: "Round k: Given `(q, D, p₀..pₖ, sₖ₋₁)` → extends prior script with the new step." The resulting `sₖ` implements the full plan `{p₀,...,pₖ}` as a single executable Python file.

### What this means in practice
Yes, every round re-reads data files from the mounted volume. A task with 20 rounds over a 500 MB CSV will read that file 20 times.

### Our decision
Accept the data re-read cost per round. For very large files, the Coder's system prompt instructs it to use memory-efficient loading (chunking, column selection, row limits) so no single script load is excessive. Within the persistent container, the OS page cache will service most re-reads from memory after the first round.

**Optimization available if needed:** Pre-load and serialize data to Feather/Parquet at container start, and instruct the Coder to read from the cached format. This is a post-MVP optimization, not needed for initial implementation.

### Rationale for the paper's design choice
- **Stateless reproducibility:** Any single `sₖ` can be run in isolation on any machine and produce `rₖ`. No dependency on prior execution state.
- **Debuggability:** To debug why round 12 produced a wrong result, you just run `s₁₂`. No need to replay the first 11 rounds.
- **Simplicity:** The Coder's task is "write a script that does this plan" — not "patch the last script." Simpler prompt, simpler code, fewer bugs.

---

## Q4: Are DS-STAR+ sub-questions executed in parallel or sequentially?

**Date:** 2026-06-24

### What the paper says
The paper does not prescribe parallelism vs. sequential execution of sub-questions. It describes the DS-STAR inner engine being run "per sub-question" but leaves the orchestration topology to the implementer.

### Our decision
**Sequential by default.** Parallel execution is available as a config flag (`dsstar_plus.parallel_subquestions: true`) but disabled by default.

### Rationale
| | Sequential | Parallel |
|--|------------|----------|
| Resource usage | Predictable — n sub-questions × 1 container at a time | Bursts to n containers simultaneously |
| On-premise GPU pressure | Moderate — one LLM inference stream at a time | High — n concurrent inference streams compete for the same GPUs |
| Sub-question inter-dependency | Can feed result of sq₁ into context of sq₂ (future enhancement) | Runs blind — sub-questions can't reference each other's results |
| Default for CBUAE | Correct — on-premise, shared GPU, multiple concurrent analyst users | Only appropriate when analyst needs faster turnaround and system is lightly loaded |

Sequential execution also enables a future optimization: if sq₁ reveals something unexpected about the data (e.g., a column is missing), the Sub-Question Generator can revise sq₂ before it runs.

---

## Q5: Does the LLM context window overflow as the plan grows across 20 rounds?

**Date:** 2026-06-24

### What the paper says
Each agent receives the full cumulative context at each call:
- Planner: `(q, D, p₀..pₖ₋₁, rₖ₋₁)`
- Coder: `(q, D, p₀..pₖ, sₖ₋₁)`
- Verifier: `(q, p₀..pₖ, sₖ, rₖ)`

The paper caps the pipeline at 20 rounds, partly as a practical limit on context growth. The paper notes that stdout (`rₖ`) is capped to prevent context flooding.

### Our decision
**Mitigations applied at three levels:**

1. **stdout cap at 10 KB.** `rₖ` is truncated before being passed into any LLM call. The Coder's system prompt instructs it to print summaries and `head()` — not full DataFrames.

2. **Flash-tier LLM for 7 of 8 agents.** Flash models (Llama 3.2 11B in production) have larger context windows relative to their cost and latency profile. The 20-round cap fits comfortably.

3. **Plan step compression (if needed).** If the cumulative plan `{p₀..pₖ}` grows unwieldy, earlier steps can be summarized into a "completed steps summary" before being passed to the Planner. This is a post-MVP fallback; the 20-round cap makes it unlikely to be needed in practice.

---

## Q6: When the Router backtracks to step `l`, what happens to the code from discarded rounds?

**Date:** 2026-06-24

### What the paper says
When the Router returns index `l`, the plan is **truncated** to `{p₀,...,pₗ₋₁}`. The Planner then regenerates step `pₗ` from scratch. The Coder receives the truncated plan and produces a new `sₖ` — it does not inherit or patch the code from the discarded steps.

This is a deliberate design: **truncate-and-regenerate, not direct correction**. The paper explicitly states this relies on the LLM's random sampling to produce diverse candidate solutions. Correcting the existing code in place would likely produce a local variation of the same flawed approach. Regenerating from a clean truncation point gives the Planner and Coder a genuinely fresh attempt.

### Our decision
Follow the paper exactly. The Coder's prompt does not include `sₖ₋₁` when a backtrack has occurred — it starts from the truncated plan only.

### Implication for the container
When a backtrack occurs, the container does not need to be reset. The next round runs a new complete script that re-does everything from step 0 through the new `pₗ`. The fact that the container previously ran the discarded steps is irrelevant — the complete-script design guarantees clean execution.

---

## Q7: What happens if all 3 Debugger attempts fail?

**Date:** 2026-06-24

### What the paper says
The Debugger has a maximum of 3 attempts per round. If all 3 fail (exit_code ≠ 0 on all attempts), the paper says the Debugger "passes best-effort result forward" — meaning the last version of the (still-broken) script's stderr/traceback is passed to the Verifier as `rₖ`.

### Our decision and what happens next
1. Verifier receives the traceback as `rₖ`. It almost certainly returns `"insufficient"` — a Python traceback does not answer the user's query.
2. Router receives `(q, D, p₀..pₖ, rₖ=traceback)`. It sees that the last step has persistently failed to execute.
3. Router is likely to return index `k` (backtrack to before the failing step) so the Planner can try a different approach to that analysis step.
4. If the error is structural (e.g., the data column doesn't exist) the Router may backtrack further, to a step that made a wrong assumption about the data schema.

**Circuit breaker:** If the same step fails with the same traceback 2 rounds in a row (different plan path, same error), the task is marked `FAILED` and sent to DLQ. Analysts are notified with the error summary. This prevents infinite loop spending on an unanswerable query given the available data.

---

## Q8: What if `rₖ` is legitimately large — e.g., the analyst asks to "show all 50,000 transactions"?

**Date:** 2026-06-24

### What the paper says
The paper mentions stdout is capped but does not specify an exact byte limit. The implementation caps stdout before it is returned to the Executor, preventing large outputs from flooding LLM context windows.

### Our decision
**stdout capped at 10 KB.** Large outputs are handled via file output, not stdout:

1. **Coder system prompt** instructs the Coder to prefer printing summaries, aggregations, and `head(20)` for large DataFrames — not full dumps.
2. **File-output pattern:** For outputs that are inherently large (full tables, Excel files, charts), the Coder writes to a file in `/tmp` inside the container. The Executor copies the file to MinIO after execution. The Finalizer retrieves it for report generation.
3. **DLP enforcement:** The 10 KB stdout cap also prevents intentional or accidental bulk data exfiltration via print flooding — a security control for an air-gapped regulatory environment.

**Example:** "Show me all fraud transactions for Bank X in 2024" → Coder produces a DataFrame and saves it to `/tmp/fraud_transactions_bankx_2024.csv`. Prints: `"Saved 48,293 rows to fraud_transactions_bankx_2024.csv. Summary: Total loss AED 12.4M, top fraud type: card_fraud (61%)."` The Verifier sees the summary and file confirmation — sufficient to answer the query. The Finalizer attaches the full file to the report.

---

## Q9: Does the Verifier see the code (`sₖ`) or just the execution result (`rₖ`)?

**Date:** 2026-06-24

### What the paper says
The Verifier receives: `(q, p₀..pₖ, sₖ, rₖ)` — the **full context including the code**.

This is a meaningful design choice. The Verifier is not just checking "did the code run." It is performing LLM-as-judge evaluation: "Given the user's query `q`, the accumulated plan, the code that was written, and the output it produced — does this output actually answer `q`?"

Seeing the code allows the Verifier to:
- Detect cases where the code ran successfully but computed the wrong thing (e.g., filtered on the wrong date range)
- Catch cases where the output is a correct data structure but doesn't address the query's intent
- Identify when the plan is on the right track but one more step is needed

### Our decision
Follow the paper exactly. The Verifier's system prompt receives the full 4-tuple. This is what makes the Verifier meaningfully different from just checking `exit_code == 0`.

---

## Q10: Does the Analyzer re-run for each DS-STAR+ sub-question, or is its output `D` shared?

**Date:** 2026-06-24

### What the paper says
The DS-STAR+ pipeline runs the Analyzer once at the outer level (before sub-question decomposition) and passes `D` into each DS-STAR inner engine instance. The data files are the same for all sub-questions — the Analyzer's output is deterministic given the same files, so re-running it per sub-question would produce identical results at unnecessary cost.

### Our decision
**`D` is computed once and shared across all sub-questions.** It is passed as immutable context to each DS-STAR inner engine instance.

**Exception:** If a sub-question requires a different data source than the primary dataset (e.g., a benchmark comparison requiring a separate GCC reference file), the Analyzer re-runs only for that specific file and appends to `D`. This is handled by the Query Clarity Agent routing step.

---

## Q11: Does DS-STAR+ have a separate Evaluator agent, or does the Sub-Question Generator handle refinement?

**Date:** 2026-06-24  
**Source:** Paper confirmed — Algorithm 2 (page 20) + prompt listings (pages 80–82)

### What the paper says
The paper's Algorithm 2 contains **no separate Evaluator agent**. The refinement loop works as follows:

```
Round 0:  Generator(q, D) → initial sub-questions
          DS-STAR per sub-question → answers
          Writer(q, answers) → Report R

Round k:  Generator(q, D, R)  ← receives current R, identifies gaps
          DS-STAR per new sub-questions → new answers
          Writer(q, R, new answers) → updated R  ← refines, not rewrites
```

The Sub-Question Generator handles **both** initial decomposition **and** gap identification for refinement. It receives the current report `R` as additional context in refinement rounds and is prompted to "suggest supplementary questions that can strengthen the report" with "new information not included in the report." The Generator itself acts as its own quality assessor.

The paper ran K=1 refinement round in all experiments and found consistent quality improvement (+68% preference over no refinement).

### Our decision
**Remove the separate Evaluator agent from the architecture. Replace with Generator (refinement mode).**

For CBUAE production: expose K (number of refinement rounds) as a configurable parameter (default K=1 following paper; admin can increase for higher-stakes reports). An optional early-stop check can be added: if the Generator produces zero supplementary sub-questions at round k, refinement terminates early (the report is already complete).

---

## Q12: Does the Debugger receive only the traceback, or also the data descriptions D?

**Date:** 2026-06-24  
**Source:** Paper confirmed — Section 3.1, page 6

### What the paper says
The paper explicitly states this as a key design insight:

> *"Tracebacks alone are often insufficient for resolving errors in data-centric scripts, while `{dᵢ}` might include critical metadata such as column headers in a CSV file, sheet names in an Excel workbook, or database schema information."*

The Debugger's formal input is:
```
s ← Debugger(s, traceback, {dᵢ}ᴺᵢ₌₁)
```
It receives the broken script, the error traceback, AND the full data descriptions D.

### Why this matters
Without D, the Debugger can only fix syntactic errors. With D, it can fix semantic errors like:
- "Column 'fraud_type' not found" → checks D, finds the actual column is 'fraud_type_code', fixes the script
- "Sheet 'Data' not found" → checks D, finds the actual sheet is 'Q1_2025', fixes the script
- "JSON key 'lfi_id' missing" → checks D, finds the nested path, fixes the access pattern

### Our decision
**Debugger prompt must include D alongside the traceback.** This was missing from our earlier architecture description. Update all Debugger agent implementations and prompt designs to pass `(s, traceback, D)` — not just `(s, traceback)`.

---

## Q13: What structure does a DS-STAR+ report follow?

**Date:** 2026-06-24  
**Source:** Paper confirmed — Writer agent prompt (page 81) + example Report 1 (pages 25–29)

### What the paper says
The Writer agent's prompt specifies **no fixed section structure**. The instructions are:
> *"The report should have nice structure, good readability, and should be professional. Write a very comprehensive data science report."*

Sections emerge dynamically from the query and the collected evidence. Analysis of Report 1 (payment fee optimization) shows the Writer produced:
1. Executive Summary (key findings, cited inline with `[c]`, `[7]` etc.)
2. Introduction (methodology overview)
3. Data & Methodology (datasets used, enrichment steps)
4. Analysis & Key Drivers (findings sub-sectioned by theme)
5. Recommendations (per-entity actionable steps)

Citations are inline throughout, not in a separate annex.

### Our decision
**The Writer agent decides sections dynamically based on query content.** CBUAE templates control branding, header/footer, classification markings, and tone — not section structure. Fixed elements across all reports:
- Header (title, date, analyst name, classification)
- Executive Summary (always first)
- Query & Scope (always second)
- Methodology (always third)
- Dynamic findings sections (Writer decides)
- Recommendations (always last)
- Inline citations throughout (sub-question number → code reference)

---

## Summary Table

| # | Question | Paper's stance | Our decision |
|---|----------|----------------|--------------|
| Q1 | Container lifecycle | Not prescribed (stateless execution implied) | One container per task, rounds use docker exec |
| Q2 | When does Analyzer run? | Once per task, before Planner | Once per DS-STAR task; D shared across DS-STAR+ sub-questions |
| Q3 | How does Coder generate sₖ? | Incremental: Coder receives s_{k-1} as base code and extends it (Algorithm 1, line 26; Listing 51 confirmed) | Output sₖ is still a complete executable script, but Coder only implements the new step on top of base code — not a full rewrite |
| Q4 | DS-STAR+ sub-question parallelism | Not prescribed | Sequential by default; parallel behind config flag |
| Q5 | LLM context overflow across 20 rounds | 20-round cap + stdout cap | stdout capped at 10KB; Flash LLMs for 7 agents; plan compression as fallback |
| Q6 | What happens to code when Router backtracks? | Truncate-and-regenerate (not direct edit) | Follow paper exactly; container not reset (complete-script design handles it) |
| Q7 | Debugger: what if all 3 attempts fail? | Best-effort result passed to Verifier | Verifier → insufficient → Router likely backtracks; circuit breaker on repeat failure |
| Q8 | What if rₖ is legitimately large? | stdout capped (limit unspecified) | 10KB cap; large outputs written to file in /tmp and copied to MinIO |
| Q9 | Does Verifier see the code or just the result? | Full 4-tuple (q, plan, sₖ, rₖ) | Follow paper exactly |
| Q10 | Does Analyzer re-run per sub-question in DS-STAR+? | Once at outer level; D shared | D shared; re-run only for supplementary data sources |
| Q11 | Separate Evaluator agent in DS-STAR+? | No — Generator handles refinement (Algorithm 2) | Removed Evaluator; Generator runs in refinement mode receiving current R |
| Q12 | Debugger input: traceback only or also D? | Two-step: (1) Summarise raw traceback; (2) Fix code using (s, summarised_traceback, D) | Implement both steps — raw tracebacks can be too long; summariser condenses before fix |
| Q13 | DS-STAR+ report structure: fixed or dynamic? | Dynamic — Writer decides sections from query | Dynamic sections; fixed: header, exec summary, scope, methodology, recommendations |
| Q14 | Does Coder rewrite script from scratch each round? | No — Listing 51 confirmed: Coder receives base_code=s_k and extends it | Output is still a complete script; Coder implements only the new step on top — corrects Q3 framing |
| Q15 | Does Debugger have one step or two? | Two steps confirmed (Listings 55+56/57): (1) traceback summariser, (2) code fixer | Two separate LLM calls per debug attempt; summariser reduces traceback length before fixer uses it |
| Q16 | Does the Finalyzer just reformat text, or does it generate and run code? | Generates a NEW Python script (Listing 54) that is executed to produce formatted output | Finalyzer runs in the sandbox like every other code step — it is not a text-only formatting layer |
| Q17 | What does the paper say about 5-6 round default vs 20? | Hard tasks need avg 5.6 rounds; accuracy positively correlates with max rounds (Figure 2) | Our 5-6 round first-run default means ~50% of hard queries need extension — acceptable given extension mechanism; must be clearly communicated to analysts |
| Q18 | What does the Verifier output exactly? | 'Yes' or 'No' (Listing 52) — paper text says "sufficient/insufficient" but prompt uses Yes/No | Implementation must parse 'Yes'/'No'; framing in prompts and code should match paper |

---

## Paper's Own Future Direction — Confirmed Alignment

The paper's Conclusion (page 13) explicitly states:
> *"A compelling avenue for future research is to extend this framework to a human-in-the-loop setting. Investigating how to synergistically combine the automated capabilities of DS-STAR with the domain knowledge of a human expert presents a promising direction for significantly boosting performance and enhancing the system's practical utility."*

Our CBUAE enhancements — mid-analysis steering, analyst pause/resume, round extension, formatting control, and conversational follow-up — are precisely this. We are building the paper's own stated future direction, not deviating from it.

---

*This document is updated whenever a new architecture question is raised and resolved. Each entry should include a date so the evolution of thinking is traceable.*
