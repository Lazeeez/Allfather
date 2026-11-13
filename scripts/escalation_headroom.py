"""Exploratory action complementarity; oracle outcomes are NOT a deployable policy.

Uses exposed fresh-full-agents data, never for confirmatory model selection. Scores
both legacy matching and exact-ID sensitivity; neither repairs candidate inventories.
No price is inferred from token totals or missing costs. No inference is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from correct_swerank import outcomes, read_rows  # noqa: E402
from frontier import OUT, load_set  # noqa: E402


def complementarity(cheap: dict, rerank: dict, agent: dict) -> dict:
    ids = sorted(set(cheap) & set(rerank) & set(agent))
    if not ids:
        raise ValueError("no common issues")
    states = {q: (int(cheap[q]), int(rerank[q]), int(agent[q])) for q in ids}
    counts = Counter("".join(map(str, value)) for value in states.values())
    return {
        "ids": ids,
        "issues": len(ids),
        "state_order": ["cheap", "rerank", "agent"],
        "joint_outcomes": {f"{i:03b}": counts[f"{i:03b}"] for i in range(8)},
        "cheap_hit": sum(c for c, _, _ in states.values()),
        "rerank_hit": sum(r for _, r, _ in states.values()),
        "agent_hit": sum(a for _, _, a in states.values()),
        "oracle_any_hit": sum(max(value) for value in states.values()),
        "rerank_only_rescues_cheap": [q for q, v in states.items() if v == (0, 1, 0)],
        "agent_only_rescues_cheap": [q for q, v in states.items() if v == (0, 0, 1)],
        "both_rescue_cheap": [q for q, v in states.items() if v == (0, 1, 1)],
        "both_damage_cheap": [q for q, v in states.items() if v == (1, 0, 0)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists; choose a new path")
    name = "fresh-full-agents"
    _, items = load_set(name)
    systems = ["website", "website-gpu", "codex-agent", "codex-agent-astra"]
    paths = [OUT / f"{name}_{s}.jsonl" for s in systems]
    report = {
        "status": "exploratory, exposed test data; no claim of learnability, mechanism, or cost benefit",
        "limitation": "Saved top-ten outputs cannot distinguish missing candidates from ranking failures.",
        "inputs_sha256": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
        "scoring": {},
    }
    for mode, legacy in (("legacy_gold_dependent", True), ("exact_id_sensitivity", False)):
        runs = {
            s: outcomes(read_rows(p), items, legacy) for s, p in zip(systems, paths, strict=True)
        }
        report["scoring"][mode] = {}
        for metric in ("hit@1", "hit@10", "all@10"):
            hit = {s: {q: v[metric] for q, v in run.items()} for s, run in runs.items()}
            report["scoring"][mode][metric] = {
                agent: complementarity(hit["website"], hit["website-gpu"], hit[agent])
                for agent in systems[2:]
            }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for agent, result in report["scoring"]["exact_id_sensitivity"]["hit@10"].items():
        print(
            agent,
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "issues",
                        "cheap_hit",
                        "rerank_hit",
                        "agent_hit",
                        "oracle_any_hit",
                        "joint_outcomes",
                    )
                }
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
