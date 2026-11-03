#!/bin/bash
HF_STORE="${HF_STORE:-$HOME/scratch/odin-cache/huggingface}"
HF_CLI="${HF_CLI:-$HOME/scratch/Odin/.venv/bin/hf}"

stage_models() {
  local dest="${TMPDIR:-/tmp}/hf-$USER-${SLURM_JOB_ID:-$$}" need=0 dir id free online=0 fetch=()
  mkdir -p "$dest/hub"
  trap "rm -rf '$dest'" EXIT
  curl -sS -m 10 -o /dev/null https://huggingface.co 2>/dev/null && online=1
  for id in "$@"; do
    dir="models--${id//\//--}"
    if [ -d "$HF_STORE/hub/$dir" ]; then
      need=$((need + $(du -skL "$HF_STORE/hub/$dir" | cut -f1)))
    elif [ "$online" = 1 ]; then
      fetch+=("$id")
    else
      echo "MISSING $id in $HF_STORE and this node is offline: download it on the login node first (cluster/RUNBOOK.md)" >&2
      return 1
    fi
  done
  free=$(df -Pk "$dest" | awk 'NR==2 {print $4}')
  if [ "$free" -lt $((need + 10485760)) ]; then
    echo "not enough node-local disk in $dest: need $((need / 1048576)) GB plus 10 GB, have $((free / 1048576)) GB" >&2
    return 1
  fi
  for id in "$@"; do
    [ -d "$HF_STORE/hub/models--${id//\//--}" ] && cp -a "$HF_STORE/hub/models--${id//\//--}" "$dest/hub/"
  done
  for id in "${fetch[@]}"; do
    HF_HOME="$dest" "$HF_CLI" download "$id" ${REVISION:+--revision "$REVISION"} >/dev/null || return 1
  done
  export HF_HOME="$dest" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  echo "staged $* in $dest ($(du -sh "$dest" | cut -f1)); downloaded on the node: ${fetch[*]:-none}"
}
