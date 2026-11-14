"""Inventory recorded cost evidence without pricing guesses or rewriting historical outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from allfather.eval.costs import record_cost, summarize  # noqa: E402


def audit() -> dict:
    runs = {}
    for set_name in ("fresh", "fresh-agents", "fresh-full", "fresh-full-agents"):
        for path in sorted((ROOT / "results/research/frontier").glob(f"{set_name}_*.jsonl")):
            if path.name.endswith(".errors.jsonl"):
                continue
            rows = [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]
            ids = [r["id"] for r in rows]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate IDs: {path.name}")
            system = path.stem[len(set_name) + 1 :]
            costs = [record_cost({"system": system, **r}) for r in rows]
            runs[path.stem] = {
                "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "ids": ids,
                **summarize(costs),
            }
    return {
        "schema": "research-cost-audit-v1",
        "scope": "Recorded run charges only; not total compute cost, marginal agent benefit, or matched accuracy-cost comparison.",
        "limitations": [
            "Recorded amounts are harness reports, not independently verified bills.",
            "Aggregate tokens cannot determine request-level long-context pricing tiers.",
            "Historical GPU counts, exclusive allocation time and setup/retry attribution are insufficient for monetary reconstruction.",
            "Missing and local placeholder costs remain unknown. No current price or rental rate is assumed.",
        ],
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("src/allfather/eval/costs.py", "scripts/audit_research_costs.py")
        },
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("use a new output path")
    result = audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(
        json.dumps(
            {
                name: {k: run[k] for k in ("rows", "states", "mean_usd")}
                for name, run in result["runs"].items()
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
