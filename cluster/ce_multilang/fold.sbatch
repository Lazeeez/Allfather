#!/bin/bash
set -euo pipefail
REPO="$HOME/scratch/Odin"
export HF_TOKEN_PATH="$HOME/.cache/huggingface/token" PYTHONUTF8=1
. "$REPO/cluster/stage_models.sh"
stamp() { echo "[$(date +%T)] $*"; }
nvidia-smi -L
FOLD="${FOLD:-$SLURM_ARRAY_TASK_ID}"
case "$CANDIDATE" in
  A|B|L|A-read2048) BASE=Qwen/Qwen3-Reranker-0.6B ;;
  C) BASE=Qwen/Qwen3-Reranker-4B ;;
esac
stage_models "$BASE"
cd "$REPO"
if [ "$CANDIDATE" != "A-read2048" ]; then
  stamp "training candidate $CANDIDATE, fold $FOLD"
  "$REPO/.venv/bin/python" scripts/ce_multilang.py train --candidate "$CANDIDATE" --fold "$FOLD"
fi
if [ "$FOLD" != "all" ]; then
  stamp "scoring the held-out fold"
  "$REPO/.venv/bin/python" scripts/ce_multilang.py score --candidate "$CANDIDATE" --fold "$FOLD"
fi
stamp "done"
