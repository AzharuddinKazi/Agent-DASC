"""
Synthetic UAE Fraud / AML dataset generator.

Everything here is fabricated data (no real customers, transactions, or institutions).
The *shape* of it — demographics, institution mix, thresholds, typologies — is grounded
in public UAE regulatory and statistical sources so the dataset is realistic enough to
exercise the pipeline meaningfully. Institution names are fictitious-but-plausible
(never real banks/exchange houses) precisely so no synthetic "high risk" or "fraud"
record can be misread as describing an actual institution.

Research grounding (checked August 2026):
  - Population / nationality mix: UAE is ~88.5% expatriate; largest groups are Indian
    (~38%), Pakistani (~17%), Bangladeshi (~7%), Filipino (~7%), Emirati (~11.5%),
    Iranian/Egyptian (~4-5% each). Sources: GMI UAE population stats 2026, UAE MOFA
    facts & figures, Wikipedia "Expatriates in the United Arab Emirates".
  - Cash/wire reporting trigger: AED 55,000 (single or linked transactions) per
    Cabinet Resolution No. 134 of 2025, Art. 7 — the CDD/CTR-style threshold licensed
    financial institutions must apply. Suspicious Transaction Reports (STR) have NO
    minimum threshold. Structuring below AED 55,000 to dodge the trigger is a named
    typology. Source: CBUAE Rulebook, UAEFIU public guidance.
  - Typologies UAEFIU has published strategic-analysis reports on: trade-based money
    laundering (TBML, often via gold/precious-metals and general trade — DMCC-adjacent),
    real estate money laundering (third parties/family members, legal-person/shell abuse,
    broker accounts), and abuse of legal persons for unlicensed hawala-style value
    transfer. Source: uaefiu.gov.ae Insights & Publications (TBML RSA 2024, Real Estate
    ML typology report, Financial Crime Typologies Jan 2024).
  - Remittance corridors: UAE outbound remittances (~AED 183bn/2024) are dominated by
    India, Pakistan and the Philippines, with Bangladesh and Egypt also material —
    concentration that makes remittance-structuring (many transfers just under the
    reporting trigger to the same corridor) a realistic UAE-specific pattern. Source:
    Gulf News / Visa-commissioned remittance study coverage, 2024-2025.
  - Seven emirates: Abu Dhabi, Dubai, Sharjah, Ajman, Umm Al Quwain, Ras Al Khaimah,
    Fujairah.
  - Institution landscape: UAE has ~50 CBUAE-licensed banks split national/foreign/
    Islamic, plus a distinct population of licensed exchange houses (money
    services/remittance, generally treated as higher inherent AML risk than banks
    under the risk-based approach) regulated separately under the Exchange Business
    Regulation (C 7/2025). We mirror that *mix* (bank tiers + a larger exchange-house
    population) without naming real institutions.
  - AED is pegged to USD at 3.6725 — used only as a plausibility anchor for amounts,
    not modelled explicitly since all ledger amounts here are already in AED.

Caveats (so this isn't oversold in a demo):
  - The ~9% overall "suspicious" rate below is deliberately far higher than real-world
    SAR/STR incidence (a small fraction of a percent) so every typology has enough
    labelled rows for the pipeline to actually find and report on. Say so if asked
    whether these are real base rates.
  - Emirates ID / IBAN values are format-realistic (784-YYYY-NNNNNNN-C, AE + check +
    bank code + account) but not checksum-valid — cosmetic only.
  - "Counterparty jurisdiction risk" is a generic Low/Medium/High label, not tied to
    any real, currently-sanctioned country, to avoid asserting real-world sanctions
    status inside synthetic data.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUTPUT_DIR = Path(os.getenv("DSSTAR")) / "data"

N_LFIS = 27
N_CUSTOMERS = 6_000
N_CARDS = 5_000
N_TRANSACTIONS = 250_000

EMIRATES = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain"]
EMIRATE_WEIGHTS = [0.42, 0.30, 0.15, 0.05, 0.04, 0.02, 0.02]

CTR_THRESHOLD_AED = 55_000  # Cabinet Resolution No. 134/2025, Art. 7

# ── LFIs (Licensed Financial Institutions) ──────────────────────────────────────────
# Fictitious names, real-world *category mix*: a handful of Tier-1 national/foreign
# banks, a larger population of exchange houses (money-services, higher inherent risk
# per the risk-based approach), a couple of finance companies and payment providers.
_lfi_catalog = [
    # (name, lfi_type, tier, base_risk)
    ("Gulf Horizon Bank", "Bank", "Tier 1", "Low"),
    ("Al Reem National Bank", "Bank", "Tier 1", "Low"),
    ("Falcon Trust Bank", "Bank", "Tier 1", "Low"),
    ("Corniche Commercial Bank", "Bank", "Tier 2", "Low"),
    ("Dana Gulf Bank", "Bank", "Tier 2", "Medium"),
    ("Union Coast Bank", "Bank", "Tier 2", "Medium"),
    ("Marjan Commercial Bank", "Bank", "Tier 3", "Medium"),
    ("Liwa National Bank", "Bank", "Tier 2", "Low"),
    ("Barakah Islamic Bank", "Islamic Bank", "Tier 1", "Low"),
    ("Al Noor Islamic Bank", "Islamic Bank", "Tier 2", "Low"),
    ("Marina Takaful Bank", "Islamic Bank", "Tier 2", "Medium"),
    ("Zam Zam Islamic Bank", "Islamic Bank", "Tier 3", "Medium"),
    ("Nakheel Islamic Bank", "Islamic Bank", "Tier 2", "Low"),
    ("Meridian International Bank (UAE Branch)", "Foreign Bank", "Tier 1", "Low"),
    ("Britannia Global Bank (UAE Branch)", "Foreign Bank", "Tier 1", "Low"),
    ("Continental Trust Bank (UAE Branch)", "Foreign Bank", "Tier 2", "Medium"),
    ("Al Waha Exchange", "Exchange House", "Tier 2", "Medium"),
    ("Desert Rose Exchange", "Exchange House", "Tier 3", "High"),
    ("Sindbad Money Exchange", "Exchange House", "Tier 3", "High"),
    ("Rostam Exchange", "Exchange House", "Tier 2", "Medium"),
    ("Fardan Bridge Exchange", "Exchange House", "Tier 3", "High"),
    ("Sahara Express Exchange", "Exchange House", "Tier 3", "High"),
    ("Cedar Gulf Exchange", "Exchange House", "Tier 2", "Medium"),
    ("Skyline Finance Co.", "Finance Company", "Tier 3", "Medium"),
    ("Palm Finance House", "Finance Company", "Tier 3", "Medium"),
    ("QuickPay UAE", "Payment Service Provider", "Tier 3", "High"),
    ("SwiftLink Payments", "Payment Service Provider", "Tier 3", "High"),
]
assert len(_lfi_catalog) == N_LFIS

lfis = pd.DataFrame(_lfi_catalog, columns=["lfi_name", "lfi_type", "lfi_tier", "risk_band"])
lfis.insert(0, "lfi_id", [f"LFI_{i:03d}" for i in range(1, N_LFIS + 1)])
lfis["emirate"] = rng.choice(EMIRATES, N_LFIS, p=EMIRATE_WEIGHTS)
lfis["is_free_zone_licensed"] = rng.choice(
    [True, False], N_LFIS, p=[0.25, 0.75]
)  # e.g. DIFC/ADGM/DMCC-style entities
lfis["cbuae_license_no"] = [f"CB-{rng.integers(10000, 99999)}" for _ in range(N_LFIS)]

banks_mask = lfis["lfi_type"].isin(["Bank", "Islamic Bank", "Foreign Bank"])
exchange_pool = lfis.loc[lfis["lfi_type"] == "Exchange House", "lfi_id"].to_numpy()
bank_pool = lfis.loc[banks_mask, "lfi_id"].to_numpy()
tier1_pool = lfis.loc[lfis["lfi_tier"] == "Tier 1", "lfi_id"].to_numpy()

# ── Customers ────────────────────────────────────────────────────────────────────────
NATIONALITIES = ["Indian", "Pakistani", "Emirati", "Bangladeshi", "Filipino",
                  "Egyptian", "Iranian", "British", "Other"]
NATIONALITY_WEIGHTS = [0.384, 0.167, 0.115, 0.074, 0.069, 0.042, 0.047, 0.020, 0.082]

OCCUPATIONS = ["Construction & Labour", "Domestic Work", "Trade & Retail",
               "Hospitality & Tourism", "Finance & Professional Services",
               "Government & Public Sector", "Real Estate",
               "Free Zone Trading Business", "Healthcare & Education",
               "Student / Not Employed"]
OCCUPATION_WEIGHTS = [0.18, 0.08, 0.15, 0.10, 0.12, 0.08, 0.05, 0.09, 0.08, 0.07]

# income band probabilities [Low, Mid, High, HNWI] conditioned on occupation sector
INCOME_BY_OCC = {
    "Construction & Labour":          [0.85, 0.14, 0.01, 0.00],
    "Domestic Work":                  [0.90, 0.09, 0.01, 0.00],
    "Trade & Retail":                 [0.30, 0.55, 0.14, 0.01],
    "Hospitality & Tourism":          [0.45, 0.45, 0.09, 0.01],
    "Finance & Professional Services":[0.05, 0.35, 0.50, 0.10],
    "Government & Public Sector":     [0.10, 0.45, 0.40, 0.05],
    "Real Estate":                    [0.05, 0.25, 0.45, 0.25],
    "Free Zone Trading Business":     [0.05, 0.25, 0.45, 0.25],
    "Healthcare & Education":         [0.10, 0.50, 0.35, 0.05],
    "Student / Not Employed":         [0.70, 0.25, 0.05, 0.00],
}
INCOME_BANDS = ["Low", "Mid", "High", "HNWI"]
PEP_RATE_BY_OCC = {
    "Government & Public Sector": 0.03,
    "Real Estate": 0.01,
    "Free Zone Trading Business": 0.01,
}
REMITTANCE_HEAVY_NATIONALITIES = {"Indian", "Pakistani", "Bangladeshi", "Filipino", "Egyptian"}

n = N_CUSTOMERS
occupation = rng.choice(OCCUPATIONS, n, p=OCCUPATION_WEIGHTS)
income_band = np.array([
    rng.choice(INCOME_BANDS, p=INCOME_BY_OCC[occ]) for occ in occupation
])
is_pep = np.array([
    rng.random() < PEP_RATE_BY_OCC.get(occ, 0.001) for occ in occupation
])
nationality = rng.choice(NATIONALITIES, n, p=NATIONALITY_WEIGHTS)
emirate_of_residence = rng.choice(EMIRATES, n, p=EMIRATE_WEIGHTS)
birth_year = rng.integers(1950, 2007, n)
age = 2026 - birth_year
residency_status = rng.choice(["Resident", "Non-Resident"], n, p=[0.92, 0.08])
account_tenure_months = rng.integers(0, 180, n)
kyc_status = rng.choice(["Verified", "Pending", "Expired"], n, p=[0.82, 0.10, 0.08])
onboarding_channel = rng.choice(["Branch", "Digital", "Agent"], n, p=[0.30, 0.60, 0.10])

corporate_occupations = {"Real Estate", "Free Zone Trading Business", "Finance & Professional Services"}
account_type = np.where(
    np.isin(occupation, list(corporate_occupations)) & (rng.random(n) < 0.5),
    "Corporate",
    rng.choice(["Current", "Savings"], n, p=[0.55, 0.45]),
)

# LFI assignment: low-income / remittance-heavy nationalities skew to exchange houses;
# HNWI skews to Tier-1 banks; everyone else uniform across the roster.
lfi_id = np.empty(n, dtype=object)
for i in range(n):
    if income_band[i] == "HNWI" and rng.random() < 0.6:
        lfi_id[i] = rng.choice(tier1_pool)
    elif income_band[i] == "Low" and nationality[i] in REMITTANCE_HEAVY_NATIONALITIES and rng.random() < 0.55:
        lfi_id[i] = rng.choice(exchange_pool)
    else:
        lfi_id[i] = rng.choice(lfis["lfi_id"].to_numpy())

emirates_id = [
    f"784-{by}-{rng.integers(1000000, 9999999)}-{rng.integers(0, 9)}" for by in birth_year
]  # format-realistic, not checksum-valid
iban = [
    f"AE{rng.integers(10, 99)}{rng.integers(100, 999):03d}{rng.integers(10**15, 10**16 - 1)}"
    for _ in lfi_id
]

customers = pd.DataFrame({
    "customer_id": [f"CUST_{i:05d}" for i in range(1, n + 1)],
    "emirates_id": emirates_id,
    "iban": iban,
    "lfi_id": lfi_id,
    "nationality": nationality,
    "residency_status": residency_status,
    "emirate_of_residence": emirate_of_residence,
    "age": age,
    "occupation_sector": occupation,
    "income_band": income_band,
    "is_pep": is_pep,
    "account_type": account_type,
    "kyc_status": kyc_status,
    "onboarding_channel": onboarding_channel,
    "account_tenure_months": account_tenure_months,
})

# ── Cards ────────────────────────────────────────────────────────────────────────────
income_rank = customers.set_index("customer_id")["income_band"].map(
    {"Low": 0, "Mid": 1, "High": 2, "HNWI": 3}
)
card_customers = rng.choice(customers["customer_id"], N_CARDS)
card_type = rng.choice(["Debit", "Credit", "Prepaid"], N_CARDS, p=[0.5, 0.35, 0.15])
limit_by_rank = {0: [0, 5000], 1: [5000, 15000], 2: [15000, 50000], 3: [50000, 200000]}
credit_limit = np.array([
    rng.integers(*limit_by_rank[income_rank[c]]) if ct == "Credit" else 0
    for c, ct in zip(card_customers, card_type)
])

cards = pd.DataFrame({
    "card_id": [f"CRD_{i:05d}" for i in range(1, N_CARDS + 1)],
    "customer_id": card_customers,
    "card_type": card_type,
    "card_network": rng.choice(["Visa", "Mastercard", "AMEX"], N_CARDS, p=[0.5, 0.4, 0.1]),
    "credit_limit_aed": credit_limit,
    "is_active": rng.choice([True, False], N_CARDS, p=[0.9, 0.1]),
})

# ── Transactions ─────────────────────────────────────────────────────────────────────
CUST = customers.set_index("customer_id")
DATE_RANGE = pd.date_range("2025-01-01", "2025-12-31 23:59:00", freq="min")

def pick_customers(mask, n):
    pool = customers.loc[mask, "customer_id"].to_numpy()
    if len(pool) == 0:
        pool = customers["customer_id"].to_numpy()
    return rng.choice(pool, n)

def random_times(n):
    return rng.choice(DATE_RANGE, n)

def base_frame(n, customer_ids, category, typology, str_filed_rate):
    cust = CUST.loc[customer_ids]
    return pd.DataFrame({
        "customer_id": customer_ids,
        "lfi_id": cust["lfi_id"].to_numpy(),
        "timestamp": random_times(n),
        "aml_category": category,
        "aml_typology": typology,
        "str_filed": rng.random(n) < str_filed_rate,
    })

blocks = []

# -- Normal (90.9%) -------------------------------------------------------------------
n_normal = int(N_TRANSACTIONS * 0.909)
cust_ids = rng.choice(customers["customer_id"], n_normal)
b = base_frame(n_normal, cust_ids, "Normal", None, 0.0)
b["channel"] = rng.choice(["POS", "Online", "ATM", "Mobile", "Branch"], n_normal, p=[0.35, 0.25, 0.15, 0.20, 0.05])
b["transaction_type"] = rng.choice(
    ["Card Payment", "ATM Withdrawal", "Bill Payment", "Salary Credit", "Retail Purchase"],
    n_normal, p=[0.35, 0.15, 0.15, 0.10, 0.25],
)
b["amount_aed"] = rng.exponential(300, n_normal).clip(5, 15_000).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = "Self"
b["mcc_category"] = rng.choice(
    ["Grocery", "Restaurants", "Retail Goods", "Fuel", "Utilities", "Telecom"], n_normal
)
b["counterparty_jurisdiction_risk"] = "Low"
blocks.append(b)

# -- Structuring / smurfing (1.2%) — cash just under the AED 55k CDD/CTR trigger ------
n_struct = int(N_TRANSACTIONS * 0.012)
struct_customers = rng.choice(customers["customer_id"], max(1, n_struct // 4))  # a small ring, reused
cust_ids = rng.choice(struct_customers, n_struct)
b = base_frame(n_struct, cust_ids, "Structuring / Smurfing", "structuring_below_ctr_threshold", 0.85)
b["channel"] = "Branch"
b["transaction_type"] = "Cash Deposit"
b["amount_aed"] = rng.uniform(40_000, 54_999, n_struct).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = "Self"
b["mcc_category"] = "Cash Handling"
b["counterparty_jurisdiction_risk"] = "Low"
blocks.append(b)

# -- Remittance structuring (1.5%) — repeat outbound transfers just under a personal
#    threshold, concentrated in the corridors that actually dominate UAE outflows -----
n_remit = int(N_TRANSACTIONS * 0.015)
remit_mask = customers["nationality"].isin(REMITTANCE_HEAVY_NATIONALITIES) & (customers["income_band"] == "Low")
remit_pool = customers.loc[remit_mask, "customer_id"].to_numpy()
remit_ring = rng.choice(remit_pool if len(remit_pool) else customers["customer_id"].to_numpy(), max(1, n_remit // 6))
cust_ids = rng.choice(remit_ring, n_remit)
b = base_frame(n_remit, cust_ids, "Remittance Structuring", "remittance_structuring", 0.35)
b["channel"] = "Exchange Counter"
b["transaction_type"] = "Outbound Remittance"
b["amount_aed"] = rng.uniform(8_000, 9_900, n_remit).round(2)
corridor_map = {"Indian": "India", "Pakistani": "Pakistan", "Bangladeshi": "Bangladesh",
                 "Filipino": "Philippines", "Egyptian": "Egypt"}
b["counterparty_country"] = [corridor_map.get(CUST.loc[c, "nationality"], "Other") for c in cust_ids]
b["counterparty_relationship"] = "Family / Beneficiary Abroad"
b["mcc_category"] = "Money Transfer"
b["counterparty_jurisdiction_risk"] = "Low"
blocks.append(b)

# -- Trade-based money laundering (0.6%) — over/under-invoiced trade payments, the
#    typology UAEFIU flags most (610 STR/SAR reports w/ explicit TBML patterns) -------
n_tbml = int(N_TRANSACTIONS * 0.006)
tbml_mask = customers["occupation_sector"].isin(["Free Zone Trading Business"]) & (customers["account_type"] == "Corporate")
cust_ids = pick_customers(tbml_mask, n_tbml)
b = base_frame(n_tbml, cust_ids, "Trade-Based Money Laundering", "tbml_invoice_mismatch", 0.9)
b["channel"] = "Wire Transfer"
b["transaction_type"] = "Trade Settlement"
b["amount_aed"] = rng.lognormal(mean=12.5, sigma=0.8, size=n_tbml).clip(100_000, 5_000_000).round(2)
b["counterparty_country"] = rng.choice(["China", "Hong Kong", "India", "Turkey"], n_tbml)
b["counterparty_relationship"] = "Trade Counterparty"
b["mcc_category"] = rng.choice(["Precious Metals & Stones", "General Trade Goods", "Electronics Wholesale"], n_tbml)
b["counterparty_jurisdiction_risk"] = "Medium"
blocks.append(b)

# -- Real estate money laundering (0.4%) — large lump sums, third-party payers, the
#    pattern UAEFIU's real-estate ML typology report calls out ----------------------
n_re = int(N_TRANSACTIONS * 0.004)
re_mask = customers["income_band"].isin(["High", "HNWI"])
cust_ids = pick_customers(re_mask, n_re)
b = base_frame(n_re, cust_ids, "Real Estate Money Laundering", "real_estate_third_party_funds", 0.9)
b["channel"] = "Wire Transfer"
b["transaction_type"] = "Property Payment"
b["amount_aed"] = rng.uniform(500_000, 10_000_000, n_re).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = rng.choice(["Third Party", "Family Member", "Corporate Nominee"], n_re)
b["mcc_category"] = "Real Estate"
b["counterparty_jurisdiction_risk"] = "Low"
blocks.append(b)

# -- Mule account / rapid layering (1.0%) — new digitally-onboarded accounts moving
#    money in and straight back out ---------------------------------------------------
n_mule = int(N_TRANSACTIONS * 0.010)
mule_mask = (customers["account_tenure_months"] < 3) & (customers["onboarding_channel"] == "Digital")
cust_ids = pick_customers(mule_mask, n_mule)
b = base_frame(n_mule, cust_ids, "Mule Account Layering", "rapid_in_out_layering", 0.6)
b["channel"] = "Mobile"
b["transaction_type"] = rng.choice(["Inbound Transfer", "Outbound Transfer"], n_mule)
b["amount_aed"] = rng.uniform(5_000, 50_000, n_mule).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = "Unrelated Third Party"
b["mcc_category"] = "Peer-to-Peer Transfer"
b["counterparty_jurisdiction_risk"] = "Medium"
blocks.append(b)

# -- Card-not-present / e-commerce fraud (1.5%) ----------------------------------------
n_cnp = int(N_TRANSACTIONS * 0.015)
cust_ids = rng.choice(customers["customer_id"], n_cnp)
b = base_frame(n_cnp, cust_ids, "Card-Not-Present Fraud", "cnp_ecommerce_fraud", 0.1)
b["channel"] = "Online"
b["transaction_type"] = "Card Payment"
b["amount_aed"] = rng.exponential(1500, n_cnp).clip(100, 20_000).round(2)
b["counterparty_country"] = rng.choice(["USA", "UK", "Singapore", "Unknown Merchant"], n_cnp)
b["counterparty_relationship"] = "Online Merchant"
b["mcc_category"] = "Overseas E-commerce"
b["counterparty_jurisdiction_risk"] = "Medium"
blocks.append(b)

# -- Account takeover (0.6%) ------------------------------------------------------------
n_ato = int(N_TRANSACTIONS * 0.006)
cust_ids = rng.choice(customers["customer_id"], n_ato)
b = base_frame(n_ato, cust_ids, "Account Takeover", "account_takeover", 0.5)
b["channel"] = "Online"
b["transaction_type"] = "Outbound Transfer"
b["amount_aed"] = rng.uniform(5_000, 50_000, n_ato).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = "New Payee"
b["mcc_category"] = "Peer-to-Peer Transfer"
b["counterparty_jurisdiction_risk"] = "Medium"
blocks.append(b)

# -- Identity theft / synthetic identity (0.5%) — brand-new account, immediate
#    high-value activity, KYC often still pending ---------------------------------------
n_id = int(N_TRANSACTIONS * 0.005)
id_mask = (customers["account_tenure_months"] < 1)
cust_ids = pick_customers(id_mask, n_id)
b = base_frame(n_id, cust_ids, "Identity Theft / Synthetic ID", "synthetic_identity", 0.7)
b["channel"] = "Digital"
b["transaction_type"] = "Outbound Transfer"
b["amount_aed"] = rng.uniform(10_000, 40_000, n_id).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = "Unrelated Third Party"
b["mcc_category"] = "Peer-to-Peer Transfer"
b["counterparty_jurisdiction_risk"] = "Medium"
blocks.append(b)

# -- PEP-linked suspicious activity (0.4%) -----------------------------------------------
n_pep = int(N_TRANSACTIONS * 0.004)
pep_mask = customers["is_pep"]
cust_ids = pick_customers(pep_mask, n_pep)
b = base_frame(n_pep, cust_ids, "PEP-Linked Suspicious Activity", "pep_unexplained_wealth", 0.8)
b["channel"] = "Branch"
b["transaction_type"] = "Wire Transfer"
b["amount_aed"] = rng.uniform(50_000, 2_000_000, n_pep).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = "Related Party / Offshore Entity"
b["mcc_category"] = "Wealth Management"
b["counterparty_jurisdiction_risk"] = "Medium"
blocks.append(b)

# -- Sanctions / high-risk jurisdiction nexus (0.5%) — generic risk label, no real
#    country named, to avoid asserting a real sanctions status in synthetic data -------
n_sanc = int(N_TRANSACTIONS * 0.005)
cust_ids = rng.choice(customers["customer_id"], n_sanc)
b = base_frame(n_sanc, cust_ids, "Sanctions / High-Risk Jurisdiction Nexus", "sanctions_screening_hit", 0.95)
b["channel"] = "Wire Transfer"
b["transaction_type"] = "Wire Transfer"
b["amount_aed"] = rng.uniform(20_000, 800_000, n_sanc).round(2)
b["counterparty_country"] = "FATF-Monitored Jurisdiction"
b["counterparty_relationship"] = "Unverified Counterparty"
b["mcc_category"] = "Cross-Border Wire"
b["counterparty_jurisdiction_risk"] = "High"
blocks.append(b)

# -- Crypto off-ramp conversion (0.8%) — cash-out at an exchange house shortly after
#    a virtual-asset platform transfer --------------------------------------------------
n_crypto = int(N_TRANSACTIONS * 0.008)
crypto_mask = customers["lfi_id"].isin(exchange_pool)
cust_ids = pick_customers(crypto_mask, n_crypto)
b = base_frame(n_crypto, cust_ids, "Crypto Off-Ramp Conversion", "crypto_offramp_cashout", 0.55)
b["channel"] = "Exchange Counter"
b["transaction_type"] = "Cash Withdrawal"
b["amount_aed"] = rng.uniform(20_000, 200_000, n_crypto).round(2)
b["counterparty_country"] = "UAE"
b["counterparty_relationship"] = "Self"
b["mcc_category"] = "Virtual Asset Service Provider"
b["counterparty_jurisdiction_risk"] = "Medium"
blocks.append(b)

transactions = pd.concat(blocks, ignore_index=True)

# top up / trim to exactly N_TRANSACTIONS with extra Normal rows (integer rounding)
shortfall = N_TRANSACTIONS - len(transactions)
if shortfall > 0:
    cust_ids = rng.choice(customers["customer_id"], shortfall)
    b = base_frame(shortfall, cust_ids, "Normal", None, 0.0)
    b["channel"] = rng.choice(["POS", "Online", "ATM", "Mobile", "Branch"], shortfall)
    b["transaction_type"] = "Card Payment"
    b["amount_aed"] = rng.exponential(300, shortfall).clip(5, 15_000).round(2)
    b["counterparty_country"] = "UAE"
    b["counterparty_relationship"] = "Self"
    b["mcc_category"] = "Retail Goods"
    b["counterparty_jurisdiction_risk"] = "Low"
    transactions = pd.concat([transactions, b], ignore_index=True)
elif shortfall < 0:
    transactions = transactions.iloc[:N_TRANSACTIONS].copy()

transactions = transactions.sample(frac=1, random_state=42).reset_index(drop=True)
transactions.insert(0, "transaction_id", [f"TXN_{i:07d}" for i in range(1, len(transactions) + 1)])
transactions["emirate"] = transactions["lfi_id"].map(lfis.set_index("lfi_id")["emirate"])
transactions["is_suspicious"] = transactions["aml_category"] != "Normal"
transactions["status"] = np.where(
    transactions["aml_category"] == "Card-Not-Present Fraud",
    rng.choice(["Declined", "Reversed", "Approved"], len(transactions), p=[0.5, 0.3, 0.2]),
    rng.choice(["Approved", "Declined", "Reversed"], len(transactions), p=[0.94, 0.03, 0.03]),
)
transactions = transactions.sort_values("timestamp").reset_index(drop=True)

# ── Write files ───────────────────────────────────────────────────────────────────────
# Deliberately spread across formats (Excel, JSON, CSV) so the Analyzer exercises its
# multi-format parsing. Transactions stays CSV since it's the largest table by far.
lfis.to_excel(OUTPUT_DIR / "lfi_data.xlsx", index=False, sheet_name="LFIs")
customers.to_excel(OUTPUT_DIR / "users_data.xlsx", index=False, sheet_name="Customers")
cards.to_json(OUTPUT_DIR / "cards_data.json", orient="records", indent=2)
transactions.to_csv(OUTPUT_DIR / "transactions_data.csv", index=False)

notes = f"""# UAE Fraud/AML synthetic dataset — assumptions & sources

Generated by `backend/generate_synthetic_data.py`. See that file's module docstring for
the full research grounding (population/nationality mix, CBUAE AED {CTR_THRESHOLD_AED:,}
reporting trigger, UAEFIU-published typologies, remittance corridors). Institution names
are fictitious; nationality/emirate/typology statistics are modelled on public UAE sources
checked August 2026, not live/current data.

Files:
- `lfi_data.xlsx`         — {len(lfis):,} licensed financial institutions (fictitious names)
- `users_data.xlsx`       — {len(customers):,} customers
- `cards_data.json`       — {len(cards):,} cards
- `transactions_data.csv` — {len(transactions):,} transactions across 12 categories:
  Normal + 11 AML/fraud typologies (see `aml_category` / `aml_typology` columns).

Caveat: ~9.1% of transactions are tagged suspicious — far above real-world SAR/STR
incidence — so every typology has enough rows for the pipeline to detect and report on.
"""
(OUTPUT_DIR / "DATA_NOTES.md").write_text(notes)

print(f"✓ lfi_data.xlsx         — {len(lfis):,} rows")
print(f"✓ users_data.xlsx       — {len(customers):,} rows")
print(f"✓ cards_data.json       — {len(cards):,} rows")
print(f"✓ transactions_data.csv — {len(transactions):,} rows")
print(transactions['aml_category'].value_counts())
print(f"\nAll files written to {OUTPUT_DIR}")
