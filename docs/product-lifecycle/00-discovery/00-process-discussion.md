# Session Log: Process Discussion

**Date:** 2026-06-24  
**Branch:** docs/product-lifecycle  
**Topic:** Understanding the full pre-code lifecycle at large tech companies

---

## What Was Discussed

The user requested a full explanation of how companies like Google and Microsoft take a software idea from conception to code — every document, gate, and review that happens before development begins.

## Process Agreed Upon

The following 10-stage lifecycle was established as the framework for this project:

1. **1-Pager / PRFAQ** — Problem statement, hypothesis, "why now"
2. **Discovery & Research** — User research, competitive analysis, data investigation
3. **PRD (Product Requirements Document)** — What to build and why; owned by PM
4. **UX Design Spec** — Wireframes, hi-fidelity mockups, user-tested prototypes
5. **TDD (Technical Design Document)** — Architecture, APIs, data model, rollout plan
6. **Security & Privacy Review** — Threat model, compliance, data handling
7. **Test Strategy Document** — How correctness is verified
8. **Work Breakdown / Sprint Plan** — Epics → Stories → Tasks
9. **Launch Plan** — Phased rollout, feature flags, killswitches
10. **Post-Launch Review** — KPI measurement, retrospective, v2 planning

## Key Principles Noted

- **No code before clarity.** Each stage produces a document that resolves ambiguity before the next stage begins.
- **Explicit non-goals matter.** The PRD must state what is out of scope to prevent scope creep.
- **Alternatives considered.** TDD must document what was rejected and why.
- **Cross-functional sign-off.** Security, Legal, Privacy, and SRE all review before code starts.
- **DRI model.** A single Directly Responsible Individual owns each document and its outcomes.

## Next Steps

- Decide on the specific product/feature idea to work on
- Begin the 1-Pager / PRFAQ (Stage 0)

---

*Session ended. Resume on branch `docs/product-lifecycle` in any future chat.*
