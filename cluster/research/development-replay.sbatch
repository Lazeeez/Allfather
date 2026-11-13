#!/bin/bash
# One L40S; existing cached weights only. Submit the six-issue smoke job first.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit from the Allfather repository}"
PYTHON="${ALLFATHER_PYTHON:-$PWD/.venv/bin/python}"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1 GIT_TERMINAL_PROMPT=0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}" OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export HF_STORE="${HF_STORE:-$HOME/scratch/odin-cache/huggingface}"
MODELS=(minishlab/potion-code-16M sentence-transformers/all-MiniLM-L6-v2 Qwen/Qwen3-Reranker-0.6B)
for model in "${MODELS[@]}"; do
  if [[ ! -d "$HF_STORE/hub/models--${model//\//--}" ]]; then
    echo "Existing model cache missing: $model in $HF_STORE; set HF_STORE to its existing location." >&2
    exit 1
  fi
done
# This helper stages only these existing caches, and the Python job pins their resolved revisions.
source cluster/stage_models.sh
stage_models "${MODELS[@]}"
"$PYTHON" scripts/development_replay.py \
  --limit "${PILOT_LIMIT:-6}" \
  --out "${PILOT_OUT:-results/research/corrections/development-smoke-v1}"
