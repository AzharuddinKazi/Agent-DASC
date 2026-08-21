"""Historical reference: the original hardcoded pack catalog, kept for its data — not
imported by any code path.

Until 2026-08-20 this was the live source of truth for GET /api/v1/domain_packs (a pack's
browsing metadata — name, description, tags, dataset generator, example question — lived
here in code, while its prompt config lived in the domain_pack_configs table). That split
meant wiping domain_pack_configs never actually emptied the Domain Packs page, since the
list still came from this file regardless of DB state. See
migrations/2026-08-20_domain_pack_catalog_columns.sql and main.py: GET /api/v1/domain_packs
now reads everything from domain_pack_configs — the catalog is entirely DB-backed.

Kept here as a template for seeding a new pack's row (INSERT INTO domain_pack_configs
with these same field values) — the equivalent role fraud_aml_example.py already plays
for a pack's persona/classification/dimensions.
"""

DOMAIN_PACKS = [
    {
        "id": "fraud-aml",
        "name": "Fraud & AML Compliance",
        "description": (
            "Supervisory risk-analysis pack for banks and regulators: fraud/"
            "transaction risk, KYC compliance, and institution risk-ranking "
            "dimensions, plus a synthetic dataset generator (institutions, "
            "transactions, users, cards)."
        ),
        "tags": ["Financial Services", "Compliance", "Risk"],
        "dataset_generator": "generate_synthetic_data.py",
        "example_question": "Which institutions have the highest KYC risk this quarter?",
    },
    {
        "id": "medicare-claims",
        "name": "Medicare Claims & Coding",
        "description": (
            "Program-integrity analysis pack for Medicare fee-for-service claims: "
            "HCPCS/procedure coding, improper-payment risk, and provider/beneficiary "
            "utilization dimensions, grounded in official CMS guidance and "
            "peer-reviewed Medicare fraud-detection research. Built on real CMS "
            "DE-SynPUF claims data — no synthetic generator."
        ),
        "tags": ["Healthcare", "Compliance", "Fraud"],
        "example_question": "Which HCPCS codes show the highest improper-payment risk this quarter?",
    },
]
