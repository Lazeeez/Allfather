"""Bring an `allfather eval` result file into the shape scripts/frontier.py scores (ADR 0033, T0).

    uv run allfather eval --dataset fresh --gold data/fresh/gold_eval_python.jsonl \
        --retriever ltr-ce-more-data-notests --level function --out results/research/frontier/fresh_eval.json
    uv run python scripts/eval_import.py --set fresh --system allfather-fast --results results/research/frontier/fresh_eval.json

Keeps each issue's top 10; the result file has no per-issue latency.
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    ids, _ = load_set(args.set)
    data = json.loads(args.results.read_text(encoding="utf-8"))
    rows = {r["instance_id"]: r for r in data["per_instance"]}
    target = OUT / f"{args.set}_{args.system}.jsonl"
    if target.exists():
        sys.exit(f"{target} exists; results are never overwritten")
    log_test_run(args.set, args.system, args.system, target)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for q in ids:
            if q not in rows:
                continue
            top = [
                {"file": u.split("::", 1)[0], "name": u.split("::", 1)[1]}
                for u in rows[q]["ranked"][:10]
            ]
            record = {
                "id": q,
                "system": args.system,
                "requested_model": args.system,
                "date": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": None,
                "answer": {"functions": top},
                "cost_usd": None,
                "tools": [],
                "web_tool_used": False,
            }
            handle.write(json.dumps(record) + "\n")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
