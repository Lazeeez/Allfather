#!/bin/bash
set -euo pipefail
REPO="$HOME/scratch/Odin"
SW="$HOME/scratch/swerank"
stamp() { echo "[$(date +%T)] $*"; }
cd "$REPO"
stamp "writing SweRank's per-issue corpora, resuming any already written"
"$REPO/.venv/bin/python" scripts/swerank_export.py --set fresh --out "$SW/fresh.partial"
rm -rf "$SW/fresh"
mv "$SW/fresh.partial" "$SW/fresh"
stamp "done: $(ls "$SW/fresh" | wc -l) entries, $(du -sh "$SW/fresh" | cut -f1)"
