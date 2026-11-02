#!/bin/bash
set -euo pipefail
SW="$HOME/scratch/swerank"
REPO="$HOME/scratch/Odin"
export HF_HOME="$HOME/scratch/odin-cache/huggingface" HF_TOKEN_PATH="$HOME/.cache/huggingface/token"
export HF_HUB_OFFLINE=1 PYTHONUTF8=1
PY="$SW/env/bin/python"
OUT="$SW/out/fresh-$TAG"
mkdir -p "$OUT"
stamp() { echo "[$(date +%T)] $*"; }
nvidia-smi -L
stamp "retrieving with $MODEL over $DATA"
"$PY" "$REPO/scripts/swerank_cached_retrieval.py" --dataset_dir "$SW/$DATA" --prefix fresh-function_ \
  --model "$MODEL" --revision "$REVISION" --batch_size "${BATCH:-32}" --cache "$SW/cache/$(basename "$MODEL")" \
  --results_file "$OUT/results.json"
stamp "done: $OUT/results.json; bring it back and run scripts/swerank_import.py"
