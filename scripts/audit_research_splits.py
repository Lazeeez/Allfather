"""Audit pilot/fresh overlap with declared ranker pools and available CE records.

Offline metadata audit only: does not select a confirmation set or establish absence
of foundation-model pretraining exposure. Original datasets and weights are untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def identity(row: dict) -> str:
    return row.get("instance_id") or row.get("qid") or row["id"]


def overlap(candidates: list[dict], reference: list[dict]) -> dict:
    ids = {identity(row) for row in reference}
    repos = {row["repo"].casefold() for row in reference}
    snapshots = {
        (row["repo"].casefold(), row["base_commit"]) for row in reference if row.get("base_commit")
    }
    hits = {
        "same_id": lambda r: identity(r) in ids,
        "same_project": lambda r: r["repo"].casefold() in repos,
        "same_snapshot": lambda r: (
            bool(r.get("base_commit")) and (r["repo"].casefold(), r["base_commit"]) in snapshots
        ),
    }
    return {
        "reference_rows": len(reference),
        "reference_projects": len(repos),
        "reference_rows_with_snapshot": sum(bool(r.get("base_commit")) for r in reference),
        **{
            label: sorted(identity(row) for row in candidates if match(row))
            for label, match in hits.items()
        },
        "projects_absent_from_reference": sorted(
            {r["repo"].casefold() for r in candidates} - repos
        ),
    }


def repeated_issues(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        if row.get("issue") is not None:
            groups[row["repo"].casefold(), str(row["issue"])].append(identity(row))
    return [
        {"repo": repo, "issue": issue, "ids": sorted(ids)}
        for (repo, issue), ids in sorted(groups.items())
        if len(ids) > 1
    ]


def build(root: Path) -> dict:
    hashes = {}

    def read(name: str, jsonl: bool = False):
        data = (root / name).read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        if jsonl:
            return [json.loads(line) for line in data.splitlines() if line.strip()]
        return json.loads(data)

    lite = {identity(r) for r in read("data/gold/swebench_lite_test.jsonl", True)}
    full = read("data/gold/swebench_full_test.jsonl", True)
    rebench = read("data/gold/swebench_rebench_train.jsonl", True)
    multi = read("data/gold/multilang_train.jsonl", True)
    # Mirrors the declared sources and label eligibility in browser_ltr.items_of.
    # Cached query availability and historical training execution are not certified.
    browser = [
        r
        for r in [*[r for r in full if identity(r) not in lite], *rebench, *multi]
        if r["functions"] or r["classes"]
    ]
    pilot_ids = read("results/research/frontier/pilot_issues.json")["issues"]
    verified = {identity(r): r for r in read("data/gold/swebench_verified_test.jsonl", True)}
    pilot = [verified[q] for q in pilot_ids]
    fresh = [
        r for r in read("data/fresh-full/gold.jsonl", True) if r["full_text_status"] == "unchanged"
    ]
    ce_path = "results/website-rerank/work/ce_records.jsonl"
    ce = None
    if (root / ce_path).exists():
        ce = [r for r in read(ce_path, True) if r["pos"] and r["neg"]]
        # CE records omit commits. Join only unambiguous ID/commit mappings.
        commits = defaultdict(set)
        for row in [*full, *rebench, *multi]:
            commits[identity(row), row["repo"].casefold()].add(row["base_commit"])
        ce = [
            dict(r, base_commit=next(iter(values)) if len(values) == 1 else None)
            for r in ce
            for values in [commits[identity(r), r["repo"].casefold()]]
        ]
    for name in (
        "scripts/audit_research_splits.py",
        "scripts/browser_ltr.py",
        "scripts/website_rerank.py",
        "scripts/ce_multilang.py",
        "results/website-rerank/gpu_config.json",
        "models/ce_multi/A/foldall/training.json",
        "web/src/assets/ranker.json",
    ):
        hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    return {
        "schema": "research-split-audit-v1",
        "limitations": [
            "Browser reference is a reconstructed declared pool, not proof of exact trained rows.",
            "CE reference is the currently available eligible records, not a historical training manifest.",
            "No upstream foundation-model exposure, repository rename/fork, or semantic duplicate audit.",
            "Fresh results are already exposed; none of these rows are a new confirmation set.",
            "An empty snapshot match list is incomplete when reference snapshots are missing.",
        ],
        "input_sha256": hashes,
        "sets": {
            name: {
                "rows": len(rows),
                "projects": len({r["repo"].casefold() for r in rows}),
                "ids": [identity(r) for r in rows],
                "duplicate_ids": {k: n for k, n in Counter(map(identity, rows)).items() if n > 1},
                "repeated_underlying_issues": repeated_issues(rows),
                "browser_declared_pool": overlap(rows, browser),
                "ce_available_records": overlap(rows, ce) if ce is not None else None,
            }
            for name, rows in (("historical_pilot", pilot), ("fresh_full_exploratory", fresh))
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build(ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    for name, value in report["sets"].items():
        print(f"{name}: {value['rows']} rows, {value['projects']} projects")
        for reference in ("browser_declared_pool", "ce_available_records"):
            found = value[reference]
            print(
                reference,
                {k: len(found[k]) for k in ("same_id", "same_project", "same_snapshot")}
                if found
                else "unavailable",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
