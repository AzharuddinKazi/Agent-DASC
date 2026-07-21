# Agent Spec: Writer (DS-STAR+ only)

## Role (paper-faithful — Appendix M.2)
Synthesises sub-question answers into a comprehensive data science report. Has two prompts:
- **Init** — writes the initial report using numbered citations `[1]`, `[2]`, ...
- **Refine** — supplements the existing report with new sub-question answers using alphabet citations `[a]`, `[b]`, ...

The init/refine loop is the paper's mechanism for iterative report improvement and hallucination prevention (all claims must cite a sub-question answer).

## Position in Graph
```
[SubquestionGenerator_init] → sub_questions_round_1
[DS-STAR × N] → subquestion_answers_round_1
    → [Writer_init] → draft_report (numbered citations)
    → [refine_round_review CP] → human chooses "Refine further" or "Finalize"
    → "Refine further":
        [SubquestionGenerator_refine] → sub_questions_round_k
        → [DS-STAR × M] → subquestion_answers_round_k
        → [Writer_refine] → updated report (alphabet citations for new additions)
        → back to [refine_round_review CP]
    → "Finalize" → [CP3: approve / save / export PDF]
```
[LOCKED] No automatic refinement rounds — see `specs/agents/subquestion-generator.md` and
`specs/features/checkpoints-hitl.md`.

## Paper Prompts (verbatim — Appendix M.2)

### Init prompt
Uses numbered citations: `[1]` through `[{num_subquestions}]`
```
You are an expert data analysist.
Your task is to write a **comprehensive data science report** to the given question by
using the data and some relevant informations listed below.
# Relevant informations:
{Sub-Question #1}
{Answer #1}
...
{Sub-Question #M_0}
{Answer #M_0}
# Question that you have to write a comprehensive data science report:
{question}
# Your task:
- The report should be grounded to the given relevant informations.
- For the citation, use the Sub-Question number as a citation number which is in
  1 - {num_subquestions}.
- The data science report should be relevant to given question, should be comprehensive,
  and should be insightful.
- The data science report should have nice structure, good readability, and should be
  professional.
- Write a very comprehensive data science report to the given above question.
```

### Refine prompt
Uses alphabet citations: `[a]`, `[b]`, ... for NEW supplementary sub-questions only.
Existing numbered citations `[1]`, `[2]` from init remain unchanged.
```
You are an expert data analysist.
Your task is to complement the given data science report of the given question by using
the some relevant informations listed below.
Relevant informations:
{Sub-Question #1}
{Answer #1}
...
{Sub-Question #M_k}
{Answer #M_k}
# Given data science report:
{report}
# Question that you have to write a comprehensive data science report:
{question}
# Your task:
- Do not modify the given report a lot. Just try to add new information.
- The report should be grounded to the given relevant informations.
- Cite with alphabet. For the citation, use the Sub-Question number as a citation
  alphabet (e.g., cite with [a] for the Sub-Question 1).
- The data science report should be relevant to given question, should be comprehensive,
  and should be insightful.
- The data science report should have nice structure, good readability, and should be
  professional.
- Complement the given data science report to the given above question.
```

## Template Variables

### Init
| Variable | Value |
|---|---|
| `{subquestion_answer_pairs}` | Formatted as `{Sub-Question #1}\n{Answer #1}\n...` |
| `{question}` | User's original open-ended query |
| `{num_subquestions}` | Integer count of sub-questions in this round |

### Refine
| Variable | Value |
|---|---|
| `{subquestion_answer_pairs}` | Formatted pairs for SUPPLEMENTARY sub-questions only |
| `{report}` | Draft report from Writer_init (complete text) |
| `{question}` | User's original open-ended query |

## Outputs
```python
class WriterOutput(BaseModel):
    report_content: str             # full report text (paper does not specify HTML)
    round: Literal["init", "refine"]
    citation_style: Literal["numeric", "alphabetic"]  # numeric for init, alphabetic for refine
```

## Report Format (Extension — paper does not specify HTML)
The paper specifies "nice structure, good readability, professional" — format is not prescribed.

Our extension: Writer produces **HTML with Tailwind CSS** for the web UI, plus PDF export via Playwright.

[LOCKED] Keeping the Tailwind CDN for v1 (cloud deployment). This is a known contradiction
with "self-contained/standalone" below — Tailwind via CDN requires internet access. Revisit
and inline the CSS when on-prem deployment work starts (`AUTH_PROVIDER=keycloak` path);
tracked as a known gap, not forgotten.

HTML requirements (our extension):
- Self-contained — no external CDN except Tailwind CSS CDN
- Sections in order: Executive Summary → Methodology → Findings → Conclusions
- Inline citations: `[1]`, `[2]` from init round; `[a]`, `[b]` from refine round
- Charts embedded as base64 `<img>` tags or referenced by filename
- `<title>` tag set to an auto-generated report title
- Standalone readable without the DS-STAR application

## Citation Rules (paper-defined)
- **Init citations**: Numbered `[1]` through `[N]` mapping to sub-question index
- **Refine citations**: Alphabetic `[a]`, `[b]`, ... mapping to supplementary sub-question index
- Both citation types coexist in the final refined report
- Every factual claim MUST have a citation — uncited claims are hallucinations (paper's anti-hallucination mechanism)
- "Do not modify the given report a lot" — refine adds, not rewrites

## Must NOT Do
- Introduce facts not present in `{subquestion_answer_pairs}`
- Modify existing numbered citations `[1]`, `[2]` during the refine round
- Rewrite large sections of the init report during refine (paper: "just try to add new information")
- Make uncited factual claims

## Extension: PDF Export
After Writer produces HTML, the API layer triggers Playwright for HTML → PDF:
- PDF saved to `OUTPUT_DIR/report_{session_id}.pdf`
- Path stored in `reports.pdf_file_path` in PostgreSQL
- PDF export is user-triggered at CP3, not automatic

## Test Scenarios

### Unit (mocked LLM)
- Init output contains numbered citations `[1]`, `[2]`...
- Refine output contains alphabet citations `[a]`, `[b]`... for new content
- Refine does not alter existing numbered citations from init
- Every numeric/factual claim in output has a citation (regex check)
- No facts introduced that aren't in subquestion_answer_pairs

### Integration (real LLM + real sub-question answers)
- Init report correctly attributes facts to source sub-questions
- Refine report adds new information without significantly restructuring init report
- HTML is valid and renders correctly as standalone file
- Playwright PDF export produces readable PDF from HTML output
- Citations are traceable back to the correct sub-question/answer pair
