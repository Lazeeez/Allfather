#!/bin/bash
# All 23 fit rows, 16 controlled variants; one L40S. Downloads stay in node-local /tmp.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit from the Allfather repository}"
PYTHON="${ALLFATHER_PYTHON:-$PWD/.venv/bin/python}"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 GIT_TERMINAL_PROMPT=0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}" OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
"$PYTHON" scripts/development_assets.py --adapter-only
MODEL_TMP=$(mktemp -d "/tmp/allfather-text-views-${SLURM_JOB_ID:?run through sbatch}.XXXXXX")
trap 'rm -rf -- "$MODEL_TMP"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
export HF_HOME="$MODEL_TMP/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub" HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export HF_XET_CACHE="$HF_HOME/xet" HF_ASSETS_CACHE="$HF_HOME/assets"
export XDG_CACHE_HOME="$MODEL_TMP/cache" TORCH_HOME="$MODEL_TMP/torch"
export CUDA_CACHE_PATH="$MODEL_TMP/cuda" TRITON_CACHE_DIR="$MODEL_TMP/triton"
export TRANSFORMERS_CACHE="$HF_HUB_CACHE" SENTENCE_TRANSFORMERS_HOME="$HF_HOME/sentence-transformers"
export TMPDIR="$MODEL_TMP/tmp" TMP="$MODEL_TMP/tmp" TEMP="$MODEL_TMP/tmp"
mkdir -p "$TMPDIR"
echo "Downloading and verifying pinned weights in $HF_HOME (compute-node temporary storage)"
"$PYTHON" scripts/development_assets.py --store "$HF_HOME" --download
"$PYTHON" scripts/replay_text_views.py \
  --bundle "${VIEW_PARENT:-results/research/corrections/development-pilot-v1}" \
  --out "${VIEW_OUT:-results/research/corrections/fit-text-views-v1}"
