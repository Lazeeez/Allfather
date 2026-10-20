#!/bin/bash
set -euo pipefail
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1
RETRIEVER=ltr-ce-more-data-notests
record() { git -c user.name="allfather job" -c user.email="job@localhost" commit -q -m "$1"; }
for LEVEL in function file; do
  allfather eval --dataset holdout --unseal --config allfather-fast --retriever "$RETRIEVER" --level "$LEVEL"
  git add -f "results/holdout/allfather-fast_$LEVEL.json" results/test-evals.log
  record "holdout $LEVEL"
done
mkdir -p results/frozen
for LEVEL in function file; do
  OUT="results/frozen/allfather-fast_${LEVEL}_lite.json"
  allfather eval --dataset lite --retriever "$RETRIEVER" --level "$LEVEL" --out "$OUT"
  echo "$(date -u +%F) | lite | allfather-fast ($RETRIEVER) | $LEVEL | $OUT | ADR 0032's one Lite run of the frozen configuration; nothing decided" >> results/test-evals.log
  git add -f "$OUT" results/test-evals.log
  record "lite $LEVEL"
done
echo "all four runs finished"
