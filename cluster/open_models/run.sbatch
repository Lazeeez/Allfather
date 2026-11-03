#!/bin/bash
set -euo pipefail
REPO="$HOME/scratch/Odin"
export HF_TOKEN_PATH="$HOME/.cache/huggingface/token" PYTHONUTF8=1
. "$REPO/cluster/stage_models.sh"
stamp() { echo "[$(date +%T)] $*"; }
nvidia-smi -L
stage_models "$MODEL"
export FRONTIER_WORK="${TMPDIR:-/tmp}/frontier-${SLURM_JOB_ID:-$$}"
mkdir -p "$FRONTIER_WORK"
PORT=$((20000 + ${SLURM_JOB_ID:-$$} % 20000))
LOG="$HOME/scratch/odin-cache/logs/vllm-${SLURM_JOB_ID:-$$}.log"
mkdir -p "$(dirname "$LOG")"
stamp "starting vLLM for $MODEL on ${GPUS:-1} GPU(s), port $PORT"
"${VLLM_ENV:-$HOME/scratch/vllm-env}/bin/vllm" serve "$MODEL" --revision "$REVISION" \
  --tensor-parallel-size "${GPUS:-1}" --max-model-len "${CONTEXT:-65536}" \
  --enable-auto-tool-choice --tool-call-parser "$PARSER" --served-model-name "$MODEL" \
  --host 127.0.0.1 --port "$PORT" > "$LOG" 2>&1 &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true' EXIT
for _ in $(seq 1 180); do
  curl -sf "http://127.0.0.1:$PORT/health" > /dev/null && break
  kill -0 "$SERVER" 2>/dev/null || { stamp "vLLM exited"; tail -40 "$LOG"; exit 1; }
  sleep 10
done
curl -sf "http://127.0.0.1:$PORT/health" > /dev/null || { stamp "vLLM did not become healthy in 30 minutes"; tail -40 "$LOG"; exit 1; }
export OPEN_MODEL_URL="http://127.0.0.1:$PORT"
cd "$REPO"
for SYSTEM in ${SYSTEMS:-open-agent open-single}; do
  stamp "running $SYSTEM ($TAG) on $SET"
  "$REPO/.venv/bin/python" scripts/frontier.py run --set "$SET" --system "$SYSTEM" --model "$MODEL" --tag "$TAG"
done
stamp "done; results in $REPO/results/research/frontier/${SET}_open-*-$TAG.jsonl"
