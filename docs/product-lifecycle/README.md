# Product Lifecycle Documentation

This directory tracks the full pre-code and post-code lifecycle for any new feature or product initiative in this repository. It mirrors the structured process used at large tech companies (Google, Microsoft) before a single line of production code is written.

## Document Index

| Stage | Folder | Document | Status |
|-------|--------|----------|--------|
| 0 | `00-discovery/` | 1-Pager / PRFAQ — Why build this? | ✅ Complete |
| 1 | `00-discovery/` | Research Summary — What do users actually need? | ✅ Complete |
| 2 | `01-prd/` | PRD / Functional Spec — What are we building? | 🔄 Draft v0.2 — 2 open questions pending CBUAE IT input (OQ-1 auth, OQ-7 GPU specs) |
| 3 | `02-ux-design/` | UX Design Spec — How does it look and feel? | ✅ Complete — 14-slide consulting-grade HTML presentation |
| 4 | `03-tdd/` | TDD / Tech Spec — How do we build it? | 🔄 Draft v0.1 — In Review (2 pending sections: §15 auth, §18–19 deployment/perf) |
| 5 | `04-security-privacy/` | Security & Privacy Review — Is it safe and compliant? | 🔄 Draft v0.1 — In Review (16 open security questions; 5 block build start) |
| 6 | `05-test-strategy/` | Test Strategy Doc — How do we know it works? | ⏳ Not started — **next step** |
| 7 | `06-work-breakdown/` | Work Breakdown / Sprint Plan — Who does what, when? | ⏳ Not started |
| 8 | `07-launch-plan/` | Launch Plan — How do we ship it safely? | ⏳ Not started |
| 9 | `08-post-launch/` | Post-Launch Review — Did it work? What's next? | ⏳ Not started |

---

## Process Overview

### How a new idea moves through the lifecycle

```
Idea / Problem Statement
        ↓
   1-Pager / PRFAQ          ← "Why build this? Why now? Why us?"
        ↓
  Project Intake Review      ← Go / No-Go gate
        ↓
  Discovery & Research       ← User interviews, competitive analysis, data
        ↓
       PRD                   ← What + Why, signed off by PM + Eng + Design
        ↓
   UX Design Spec            ← Wireframes → hi-fi → user tested
        ↓
       TDD                   ← Architecture, data model, APIs, rollout plan
        ↓
Cross-Functional Reviews     ← Security, Legal, Privacy, SRE, QA
        ↓
  Work Breakdown             ← Epics → Stories → Tasks → Sprint plan
        ↓
  *** CODE STARTS HERE ***
        ↓
    Launch Plan              ← Phased rollout, feature flags, killswitches
        ↓
  Post-Launch Review         ← Metrics vs KPIs, retrospective, iteration plan
```

---

## Branch

All lifecycle documentation lives on branch: `docs/product-lifecycle`

This branch is never merged into `main`. It exists solely as a persistent, version-controlled record of research, proposals, discussions, and decisions across sessions.

---

## How to Use This Across Sessions

Each document in this folder captures the state of thinking at a point in time. Commit messages describe what was discussed or decided. To resume work in a new chat:

1. Check out `docs/product-lifecycle`
2. Read the relevant stage document(s)
3. Continue from where the last session left off

---

*Last updated: 2026-07-02*
