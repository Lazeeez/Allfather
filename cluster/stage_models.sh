#!/bin/bash
HF_STORE="${HF_STORE:-$HOME/scratch/odin-cache/huggingface}"

stage_models() {
  local dest="${TMPDIR:-/tmp}/hf-$USER-${SLURM_JOB_ID:-$$}" need=0 dir id free
  mkdir -p "$dest/hub"
  for id in "$@"; do
    dir="models--${id//\//--}"
    if [ ! -d "$HF_STORE/hub/$dir" ]; then
      echo "MISSING $id in $HF_STORE: download it on the login node first (cluster/RUNBOOK.md)" >&2
      return 1
    fi
    need=$((need + $(du -skL "$HF_STORE/hub/$dir" | cut -f1)))
  done
  free=$(df -Pk "$dest" | awk 'NR==2 {print $4}')
  if [ "$free" -lt $((need + 10485760)) ]; then
    echo "not enough node-local disk in $dest: need $((need / 1048576)) GB plus 10 GB, have $((free / 1048576)) GB" >&2
    return 1
  fi
  for id in "$@"; do
    cp -a "$HF_STORE/hub/models--${id//\//--}" "$dest/hub/"
  done
  export HF_HOME="$dest" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  echo "staged $* ($((need / 1048576)) GB) in $dest"
}
