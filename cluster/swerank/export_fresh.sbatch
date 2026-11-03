#!/bin/bash
set -euo pipefail
REPO="$HOME/scratch/Odin"
SW="$HOME/scratch/swerank"
stamp() { echo "[$(date +%T)] $*"; }
cd "$REPO"
stamp "fetching every repository and blob fresh-2026 needs"
"$REPO/.venv/bin/python" scripts/frontier.py prepare --set fresh
rm -rf "$SW/fresh.partial"
stamp "writing SweRank's per-issue corpora"
"$REPO/.venv/bin/python" scripts/swerank_export.py --set fresh --out "$SW/fresh.partial"
rm -rf "$SW/fresh"
mv "$SW/fresh.partial" "$SW/fresh"
stamp "done: $(ls "$SW/fresh" | wc -l) entries, $(du -sh "$SW/fresh" | cut -f1)"
