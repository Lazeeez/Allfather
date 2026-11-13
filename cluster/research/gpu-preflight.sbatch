#!/bin/bash
# One allocated NVIDIA GPU; no model downloads, training, or API calls.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit this job from the Allfather repository}"
PYTHON="${ALLFATHER_PYTHON:-$PWD/.venv/bin/python}"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
"$PYTHON" scripts/gpu_preflight.py \
  --out "results/research/corrections/pace-logs/gpu-preflight-${SLURM_JOB_ID:?}.json"
