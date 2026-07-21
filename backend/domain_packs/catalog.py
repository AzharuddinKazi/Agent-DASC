"""Registry of downloadable domain packs.

Each entry points at an existing domain_pack.py-shaped config file and an
optional synthetic dataset generator. Adding a new pack means adding a new
dict here — no other backend code changes.
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
        "config_file": "domain_packs/fraud_aml_example.py",
        "dataset_generator": "generate_synthetic_data.py",
    },
]


def get_pack(pack_id: str):
    return next((p for p in DOMAIN_PACKS if p["id"] == pack_id), None)


def public_catalog():
    return [
        {k: v for k, v in p.items() if k not in ("config_file", "dataset_generator")}
        for p in DOMAIN_PACKS
    ]
