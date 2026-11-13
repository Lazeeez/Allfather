#!/bin/bash
# One L40S; pinned base weights downloaded only into compute-node temporary storage.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit from the Allfather repository}"
PYTHON="${ALLFATHER_PYTHON:-$PWD/.venv/bin/python}"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 GIT_TERMINAL_PROMPT=0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}" OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
"$PYTHON" scripts/development_assets.py --adapter-only
MODEL_TMP=$(mktemp -d "${TMPDIR:-/tmp}/allfather-models-${SLURM_JOB_ID:?run through sbatch}.XXXXXX")
trap 'rm -rf -- "$MODEL_TMP"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
export HF_HOME="$MODEL_TMP/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub" HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export HF_XET_CACHE="$HF_HOME/xet" HF_ASSETS_CACHE="$HF_HOME/assets"
export XDG_CACHE_HOME="$MODEL_TMP/cache" TORCH_HOME="$MODEL_TMP/torch"
export TRANSFORMERS_CACHE="$HF_HUB_CACHE" SENTENCE_TRANSFORMERS_HOME="$HF_HOME/sentence-transformers"
export TMPDIR="$MODEL_TMP/tmp" TMP="$MODEL_TMP/tmp" TEMP="$MODEL_TMP/tmp"
mkdir -p "$TMPDIR"
echo "Downloading and verifying pinned base weights in $HF_HOME (temporary compute-node storage)"
"$PYTHON" scripts/development_assets.py --store "$HF_HOME" --download
# The downloader enables network access only in its own process. Inference stays offline.
"$PYTHON" scripts/development_replay.py \
  --limit "${PILOT_LIMIT:-6}" \
  --out "${PILOT_OUT:-results/research/corrections/development-smoke-v1}"
