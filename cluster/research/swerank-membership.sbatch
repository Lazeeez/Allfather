#!/bin/bash
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit from the project checkout}"
export PYTHONUTF8=1
export GIT_NO_LAZY_FETCH=1
SHORT_EXPORT="${SHORT_EXPORT:-$HOME/scratch/swerank/fresh}"
FULL_EXPORT="${FULL_EXPORT:-$HOME/scratch/swerank/fresh-full}"
AUDIT_OUT="${AUDIT_OUT:-results/research/corrections/swerank-membership-${SLURM_JOB_ID:?}}"
for export_dir in "$SHORT_EXPORT" "$FULL_EXPORT"; do
  test -f "$export_dir/index.json" || { echo "Saved export missing: $export_dir/index.json; do not rebuild it for this audit."; exit 1; }
done
"${PYTHON:-.venv/bin/python}" scripts/audit_swerank_membership.py \
  --short "$SHORT_EXPORT" --full "$FULL_EXPORT" --out "$AUDIT_OUT"
