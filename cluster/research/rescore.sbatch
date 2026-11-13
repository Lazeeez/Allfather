#!/bin/bash
# Saved predictions and validated inventories only; CPU, no inference or downloads.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit this job from the Allfather repository}"
PYTHON="${ALLFATHER_PYTHON:-$PWD/.venv/bin/python}"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
"$PYTHON" scripts/rescore_inventories.py \
  --inventories "${INVENTORY_OUT:-results/research/corrections/inventories-fresh-v1}" \
  --audit "${INVENTORY_AUDIT:?set INVENTORY_AUDIT to the successful audit directory}" \
  --out "results/research/corrections/inventory-rescore-${SLURM_JOB_ID:?}"
