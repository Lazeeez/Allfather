"""Bring SweRank rankings for a set back into the shape scripts/frontier.py scores (ADR 0033, T1).

    uv run python scripts/swerank_import.py --set fresh --system swerank-embed-large --results results.json

The results file maps each issue id to SweRank document ids ("path/Class/method"), as written by
scripts/swerank_cached_retrieval.py with --prefix. Only the top 10 are kept. A run on a sealed set
is logged in results/test-evals.log.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from frontier import OUT, load_set, log_test_run  # noqa: E402

SOURCE = (".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rs")


def split_id(doc: str) -> dict[str, str]:
    parts = doc.split("/")
    for i, part in enumerate(parts):
        if part.endswith(SOURCE):
            return {"file": "/".join(parts[: i + 1]), "name": ".".join(parts[i + 1 :])}
    return {"file": doc, "name": ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--model", default="")
    args = ap.parse_args()
    ids, _ = load_set(args.set)
    ranked = json.loads(args.results.read_text(encoding="utf-8"))
    target = OUT / f"{args.set}_{args.system}.jsonl"
    if target.exists():
        sys.exit(f"{target} exists; results are never overwritten")
    log_test_run(args.set, args.system, args.model or args.system, target)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for q in ids:
            if q not in ranked:
                continue
            record = {
                "id": q,
                "system": args.system,
                "requested_model": args.model or args.system,
                "date": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": None,
                "answer": {"functions": [split_id(d) for d in ranked[q][:10]]},
                "cost_usd": None,
                "tools": [],
                "web_tool_used": False,
            }
            handle.write(json.dumps(record) + "\n")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
