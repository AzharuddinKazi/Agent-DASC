"""Registry of browsable domain packs.

Metadata only (what a pack is, for browsing/activating) — the pack's actual prompt
config (persona, classification, dimensions) lives in the domain_pack_configs table,
switchable at runtime via the Domain Packs page. Adding a new pack means adding a new
dict here plus a row in domain_pack_configs — no other backend code changes.
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
    },
]


def get_pack(pack_id: str):
    return next((p for p in DOMAIN_PACKS if p["id"] == pack_id), None)


def public_catalog():
    return [
        {k: v for k, v in p.items() if k not in ("dataset_generator",)}
        for p in DOMAIN_PACKS
    ]
