# Requirements Discovery Log

**Stage**: Discovery — Stage 0  
**Date**: 2026-06-24  
**Session**: Initial requirements Q&A  
**Participants**: Fraud Prevention Supervision (CBUAE)  

---

## Summary

This document records the confirmed requirements captured through a structured Q&A session during the discovery phase. These decisions feed directly into the PRD and TDD.

---

## Confirmed Requirements

### 1. Data Sources

**Decision**: All four data types

The system must handle data from all four categories present in the Financial Crime & Market Conduct vertical:

| Data Type | Description | Primary Consumer |
|-----------|-------------|-----------------|
| **Transaction Monitoring Alerts** | LFI-submitted alert queues, risk scores, AML system exports (SWIFT fields, typology labels) | AML/CFT Supervision |
| **SAR / STR Reports** | Suspicious Activity / Transaction Report database — filed cases, narratives, typologies, involved entities | AML/CFT Supervision |
| **KYC / CDD Data** | Customer risk profiles, risk band assignments, PEP/sanctions screening results, onboarding data | AML/CFT Supervision, Fraud Prevention |
| **Market Surveillance Data** | Trade records, order books, volume patterns, communications data for market abuse detection | Market Conduct & FCPS |

Additionally, the Fraud Prevention Supervision department works with LFI-submitted fraud loss reports as a primary data source:

| Data Type | Description |
|-----------|-------------|
| **LFI Fraud Loss Reports** | Fraud_type, channel, amount_aed, detection_method, lfi_id, reporting_period — submitted periodically by all LFIs |
| **LFI Fraud Control Assessments** | Qualitative and quantitative assessment data from supervisory examinations |
| **Industry Benchmarking Datasets** | Peer comparison data; GCC/international fraud loss benchmarks |

---

### 2. Deployment Model

**Decision**: On-premise only — fully air-gapped

No data leaves CBUAE infrastructure. The system runs entirely within the CBUAE data centre. There is no cloud component — no API calls to external services, no data sent to third-party LLM providers.

**Implication**: The LLM inference layer must support local model deployment. The architecture uses a **provider-agnostic adapter** so the LLM backend can be configured without changing any agent code:

```
config.yaml:
  llm_provider: "ollama"           # or "gemini" (dev) or "azure_openai" (hybrid option)
  llm_endpoint: "http://localhost:11434"
  llm_model_flash: "llama3.1:70b"  # placeholder — actual model TBD by CBUAE IT
  llm_model_pro: "llama3.3:70b"    # placeholder — highest quality local model
```

The actual LLM model procured and deployed is a CBUAE IT decision, made separately from this design. The system is designed to accept any OpenAI-compatible API endpoint.

---

### 3. Target Users

**Decision**: All five departments under Financial Crime & Market Conduct

The primary department is **Fraud Prevention Supervision** (where the initiating team works). The system is designed to serve all five departments.

| Department | Role | Representative Queries |
|------------|------|----------------------|
| **Fraud Prevention Supervision** ⭐ | Supervises LFI fraud prevention frameworks, benchmarks fraud loss data | "Which LFIs have the highest card fraud loss rate vs. peer median?", "Show fraud typology trends by LFI over the past 12 months", "Which LFIs are statistical outliers in social engineering fraud detection?" |
| **AML / CFT Supervision** | Supervises LFI AML/CFT compliance obligations | "Which LFIs have declining STR filing rates?", "Show cross-LFI typology distribution vs. FATF benchmarks", "Which LFIs have gaps in beneficial ownership reporting?" |
| **Market Conduct & FCPS** | Monitors consumer complaints, market behaviour, mis-selling | "Show complaint volumes by LFI and product category", "Which LFIs have materially more complaints than peers?", "Identify potential mis-selling patterns from complaint data" |
| **Enforcement** | Takes regulatory action against violations | "Pull all fraud loss data for LFI X across the last 3 years", "Generate an evidence data summary for case #XXXX", "Show the historical pattern of LFI Y's compliance failures" |
| **Policy & Research** | Develops regulatory frameworks, conducts sector research | "What is the UAE-wide fraud loss trend by channel (card, digital, wire)?", "Compare UAE fraud rates against GCC/MENA benchmarks", "Generate a thematic report on APP fraud growth across the sector" |

**User persona**: Non-technical. The target user can articulate what they want to know but cannot write Python or SQL to extract it. They understand the domain deeply (regulatory frameworks, LFI behaviour, financial crime typologies) but rely on technical colleagues or manual Excel for data analysis today.

---

### 4. Output Requirements

**Decision**: Both standalone reports AND a REST API

| Output Type | Description | Use Case |
|-------------|-------------|----------|
| **Standalone reports** | PDF and Excel export, formatted to CBUAE reporting standards | Supervisory letters, leadership briefings, thematic reviews, FATF submissions |
| **REST API** | Programmatic query submission and result retrieval | Integration with future case management systems, automated reporting pipelines, dashboard feeds |
| **WebSocket streaming** | Real-time step-by-step progress as the agent runs | Frontend UI, keeping analysts informed during longer analyses |

---

### 5. LLM Inference

**Decision**: Provider-agnostic adapter — model decided by CBUAE IT

The system is built with a clean abstraction layer between agents and LLM providers. Switching providers requires only a config file change — zero changes to agent code.

| Provider | Use Case |
|----------|----------|
| Local Ollama / vLLM | Air-gapped production deployment (primary target) |
| Gemini API | Development, testing, and benchmarking (requires internet) |
| Azure OpenAI (UAE North) | Optional hybrid — data stays in UAE but not fully air-gapped |

The agent-to-model tier mapping (Flash for most agents, Pro for Report Writer) is preserved in the adapter and mapped to whatever local models CBUAE IT procures.

---

## Organisational Context

- **Initiating department**: Fraud Prevention Supervision, CBUAE Financial Crime & Market Conduct
- **Data custodian**: CBUAE (data submitted by LFIs under regulatory obligation)
- **IT infrastructure**: CBUAE internal data centre (on-premise)
- **Regulatory sensitivity**: High — outputs may be used in supervisory actions and enforcement proceedings; audit trail and data governance are non-negotiable requirements
- **Current state**: Analysis done manually in Excel; technical reports require IT involvement; thematic reviews take weeks

---

## Open Questions (to be resolved in PRD phase)

| # | Question | Needed For |
|---|----------|-----------|
| 1 | How do analysts authenticate today? (Active Directory, CBUAE SSO?) | Security Review, RBAC design |
| 2 | What is the largest dataset an analyst would query in a single session? (rows / GB) | Infrastructure sizing, Executor memory limits |
| 3 | Are there existing report templates used for supervisory letters? (Word/PDF formats) | Finalizer template design |
| 4 | Does output need to integrate with an existing case management system? (NICE Actimize, Oracle FCCM, ServiceNow?) | API contract design |
| 5 | What is the data freshness requirement? (Can the system query data that is 24 hours old, or does it need real-time?) | Data ingestion pipeline design |
| 6 | Who has authority to approve what an analyst can query? (Sensitivity tiers for data access) | RBAC policy design |

---

## Next Step

Write the PRD → `01-prd/01-prd-cbuae-fip.md`

*Resume on branch `docs/product-lifecycle` in any future session.*
