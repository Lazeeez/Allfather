#!/bin/bash
# Submit from the repository root; CPU-only, no inference or paid API calls.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit this job from the Allfather repository}"
PYTHON="${ALLFATHER_PYTHON:-$PWD/.venv/bin/python}"
OUT="${INVENTORY_OUT:-$PWD/results/research/corrections/inventories-fresh-v1}"
LIMIT="${INVENTORY_LIMIT:-0}"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
export GIT_TERMINAL_PROMPT=0
"$PYTHON" scripts/build_symbol_inventories.py --set fresh-full --limit "$LIMIT" --out "$OUT"
