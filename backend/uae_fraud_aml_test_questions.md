# Test questions — UAE Fraud/AML sample dataset

Paired with `generate_synthetic_data.py` (run it first — see that file's docstring for
what's in `data/lfi_data.xlsx`, `users_data.xlsx`, `cards_data.json`,
`transactions_data.csv`, and `DATA_NOTES.md`).

Every question below is grounded in an actual column or category the generator
produces, so the pipeline should be able to answer it without guessing at schema.
Split into **Insight** (`task_type: "qa"` — one focused answer) and **Research**
(`task_type: "report"` — multi-sub-question report with a Writer/Evaluator pass). A
handful of these (marked ⭐) are wired into the frontend's "Try these" list in
`frontend/src/config/brand.js`.

---

## Insight (QA)

### Fraud / transaction risk
- ⭐ Which LFIs have the highest share of suspicious transactions relative to their total volume?
- Which AML typology accounts for the largest total AED value moved, and how does that compare to its transaction count?
- What's the fraud/suspicious rate by channel (Branch, Online, Mobile, ATM, Exchange Counter)?
- Which emirates have the highest concentration of suspicious transactions?

### Structuring & remittances
- ⭐ Show me structuring transactions clustered just under the AED 55,000 reporting threshold.
- ⭐ Which customer segments (nationality, income band) are most associated with remittance structuring?
- Which outbound remittance corridors (counterparty_country) carry the most structuring activity?
- Are remittance-structuring customers concentrated at a small number of exchange houses?

### Trade & real estate laundering
- Which corporate customers in the Free Zone Trading Business sector show trade-settlement amounts consistent with invoice mismatch patterns?
- What share of Real Estate Money Laundering transactions involve a third-party or corporate-nominee payer rather than the account holder?
- Which MCC categories (Precious Metals & Stones, Real Estate, General Trade Goods) carry the highest average transaction value?

### Account integrity / mules
- Which customers opened an account in the last 3 months and immediately show mule-account-layering activity?
- What's the average time-to-first-suspicious-transaction for digitally onboarded customers vs. branch-onboarded ones?
- Which cards/customers show a pattern of card-not-present fraud concentrated in overseas e-commerce MCCs?
- Which customers had an account-takeover-flagged transaction — what do their KYC status and onboarding channel look like?

### PEP / sanctions / crypto
- ⭐ Which PEP-flagged customers have unusually large or irregular wire transfers?
- What share of transactions tagged "High" counterparty jurisdiction risk actually resulted in an STR being filed?
- ⭐ Which exchange houses show the highest concentration of crypto off-ramp cash withdrawals?
- Compare average transaction size for PEP-linked activity vs. the general customer base.

### Compliance / KYC
- What percentage of customers have an Expired or Pending KYC status, broken down by LFI?
- ⭐ Compare STR filing rates across AML typologies — which categories are under-reported relative to their risk?
- Which LFIs have the biggest gap between their declared risk_band and their actual suspicious-transaction rate?

### Segmentation
- Break down suspicious-transaction rate by occupation sector and income band.
- How does account_type (Current/Savings/Corporate) correlate with typology of suspicious activity?
- Which nationality groups are over-represented in Trade-Based Money Laundering vs. their share of the customer base?

---

## Research (Report)

- ⭐ Produce a supervisory report on trade-based money laundering exposure across free-zone corporate accounts.
- ⭐ Generate a thematic analysis of fraud and AML typology trends across institutions and emirates in 2025.
- ⭐ Assess KYC and onboarding-channel risk gaps across the customer base and recommend remediation priorities.
- Produce a sector-wide AML risk assessment of exchange houses vs. banks, covering structuring, remittance structuring, and crypto off-ramp exposure.
- Draft a report on PEP and sanctions-nexus exposure suitable for a supervisory briefing, including which institutions carry the most concentrated risk.
- Generate a report comparing declared LFI risk bands against measured behavior (suspicious rate, STR filing rate, typology mix) and flag any institutions where the two diverge materially.
- Produce a report on customer segmentation risk — which combinations of nationality, income band, and onboarding channel carry the highest AML exposure — with recommendations for enhanced due diligence triggers.

---

## Notes for testers

- The dataset over-samples suspicious activity (~9%) so every typology has enough rows
  to be found — don't read the *rates* below as real-world base rates (see
  `data/DATA_NOTES.md`).
- `aml_category` is the human-readable label; `aml_typology` is the machine-readable
  slug (e.g. `remittance_structuring`) — either is a valid thing to ask about.
- Institution and customer identifiers are fully synthetic (`LFI_001`, `CUST_00042`,
  fictitious bank names) — nothing here maps to a real UAE entity.
