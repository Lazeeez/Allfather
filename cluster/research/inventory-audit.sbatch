#!/bin/bash
# Reads existing compressed inventories only; no Git fetches, parsing or inference.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit this job from the Allfather repository}"
PYTHON="${ALLFATHER_PYTHON:-$PWD/.venv/bin/python}"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
"$PYTHON" scripts/audit_symbol_inventories.py \
  --inventories "${INVENTORY_OUT:-results/research/corrections/inventories-fresh-v1}" \
  --out "results/research/corrections/inventory-audit-${SLURM_JOB_ID:?}"
