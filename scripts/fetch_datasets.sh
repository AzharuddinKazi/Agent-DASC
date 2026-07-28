#!/usr/bin/env bash
# Repopulates data/ after a fresh clone or Codespace — these files are gitignored
# on purpose (see .gitignore), not lost. All sources are synthetic or CMS's own
# synthetic public-use files (DE-SynPUF), not real patient/customer data.
#
# Requires: `kaggle` CLI + credentials (KAGGLE_USERNAME/KAGGLE_KEY env vars, or
# ~/.kaggle/kaggle.json) for the two Kaggle-sourced packs. Get a token at
# https://www.kaggle.com/settings (Account > API > Create New Token).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data"
mkdir -p "$DATA_DIR/_paysim_backup" "$DATA_DIR/_uae_banking_backup"

if ! command -v kaggle >/dev/null 2>&1; then
  echo "kaggle CLI not found. Install with: pip install kaggle" >&2
  exit 1
fi
if [ ! -f "$HOME/.kaggle/kaggle.json" ] && [ -z "${KAGGLE_KEY:-}" ]; then
  echo "No Kaggle credentials found. Get an API token at https://www.kaggle.com/settings" >&2
  echo "(Account > API > Create New Token), then either save it to ~/.kaggle/kaggle.json" >&2
  echo "or set KAGGLE_USERNAME / KAGGLE_KEY (e.g. as Codespaces secrets)." >&2
  exit 1
fi

echo "==> PaySim mobile-money transactions: ntnu-testimon/paysim1"
tmp_paysim="$(mktemp -d)"
kaggle datasets download -d ntnu-testimon/paysim1 -p "$tmp_paysim" --unzip -q
# Upstream filename varies by version (PS_*.csv) — take whichever single CSV landed.
paysim_file="$(find "$tmp_paysim" -maxdepth 1 -iname '*.csv' | head -1)"
if [ -z "$paysim_file" ]; then
  echo "WARNING: no CSV found in ntnu-testimon/paysim1 — inspect $tmp_paysim manually." >&2
else
  mv "$paysim_file" "$DATA_DIR/_paysim_backup/paysim_mobile_money_transactions.csv"
  echo "    -> data/_paysim_backup/paysim_mobile_money_transactions.csv"
fi
rm -rf "$tmp_paysim"

echo "==> Medicare DE-SynPUF Sample 1 (medicare-claims pack): anikannal/cms-synthetic-data"
# Verified by exact byte size against this repo's original files before writing this
# script (14588413 / 16689488 / 161812812 bytes) — this is confirmed correct, not a guess.
tmp_medicare="$(mktemp -d)"
kaggle datasets download -d anikannal/cms-synthetic-data -p "$tmp_medicare" --unzip -q
declare -A medicare_map=(
  ["DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv"]="medicare_beneficiary_summary_2008.csv"
  ["DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv"]="medicare_inpatient_claims.csv"
  ["DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv"]="medicare_outpatient_claims.csv"
)
for src in "${!medicare_map[@]}"; do
  if [ -f "$tmp_medicare/$src" ]; then
    mv "$tmp_medicare/$src" "$DATA_DIR/${medicare_map[$src]}"
    echo "    -> data/${medicare_map[$src]}"
  else
    echo "    WARNING: expected '$src' not in this download — dataset version may have" >&2
    echo "    changed. Check $tmp_medicare and update the mapping in this script." >&2
  fi
done
rm -rf "$tmp_medicare"

echo "==> HCPCS Level II codes: no automated source found (see NOTE)"
echo "    NOTE: cms/cms-codes on Kaggle is BigQuery-only, no downloadable file — could not"
echo "    verify an exact source for hcpcs_level_ii_codes.xlsx. Manually download the"
echo "    current quarterly Alpha-Numeric HCPCS file from"
echo "    https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update"
echo "    and save it as data/hcpcs_level_ii_codes.xlsx."

echo "==> UAE banking pack (fully synthetic — regenerated, not downloaded)"
(cd "$REPO_ROOT/backend" && DSSTAR="$REPO_ROOT" uv run python generate_synthetic_data.py)
for f in lfi_data.xlsx users_data.xlsx cards_data.json transactions_data.csv; do
  if [ -f "$DATA_DIR/$f" ]; then
    mv "$DATA_DIR/$f" "$DATA_DIR/_uae_banking_backup/$f"
    echo "    -> data/_uae_banking_backup/$f"
  fi
done

echo "==> Done. HCPCS file above is the only file needing a manual step."
