"""
Example domain pack: the original financial-crime-compliance (CBUAE/AML) deployment
this app was first built for.

Not active by default — nothing imports this file. Copy these values into
backend/domain_pack.py to use them, or use this file as a template for a different
domain's own pack.
"""

REPORT_PERSONA = "You are a senior regulatory analyst at a central bank writing an official supervisory report."

REPORT_CLASSIFICATION = "SUPERVISORY — CONFIDENTIAL"

SUBQUESTION_DIMENSIONS = [
    "FRAUD / TRANSACTION RISK — fraud rates, volumes, types, hotspots",
    "COMPLIANCE / KYC RISK — KYC status gaps, expired verifications, pending reviews",
    "ENTITY / LFI RANKING — which institutions are highest risk overall, composite scores",
    "BEHAVIOURAL PATTERNS — transaction patterns, peak times, reversal/decline rates",
    "CUSTOMER SEGMENTATION — risk by account type, nationality, customer tier",
    "TEMPORAL TRENDS — how key metrics have changed over time (if date columns exist)",
    "CROSS-ENTITY COMPARISON — risk band vs actual behaviour mismatch, declared vs measured",
]
