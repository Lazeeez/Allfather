"""Make SweRank's fresh-full data from its fresh data: the same corpora, the full bug reports as queries.

    uv run python scripts/swerank_full_queries.py --source $HOME/scratch/swerank/fresh --out $HOME/scratch/swerank/fresh-full

Every bug folder of the source keeps its corpus and answer key, linked rather than copied, and gets a
new queries.jsonl holding the bug's text from data/fresh-full (ADR 0033, full-report condition). It
refuses to run if a folder's current query is not the start of the full report, so the two conditions
can differ only in the report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from frontier import load_set  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    _, full = load_set("fresh-full")
    index = json.loads((args.source / "index.json").read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for folder, q in index.items():
        src, dst = args.source / folder, args.out / folder
        old = json.loads((src / "queries.jsonl").read_text(encoding="utf-8").splitlines()[0])
        if not full[q]["text"].startswith(old["text"]):
            sys.exit(f"{q}: the sealed query is not the start of the full report")
        (dst / "qrels").mkdir(parents=True, exist_ok=True)
        for name in ("corpus.jsonl", "qrels/test.tsv"):
            if not (dst / name).exists():
                os.symlink((src / name).resolve(), dst / name)
        (dst / "queries.jsonl").write_text(
            json.dumps({"_id": q, "text": full[q]["text"]}) + "\n", encoding="utf-8", newline="\n"
        )
    (args.out / "index.json").write_text(
        json.dumps(index, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {len(index)} folders to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
