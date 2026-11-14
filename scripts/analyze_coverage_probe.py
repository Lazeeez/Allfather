"""Verify fit-only retrieval controls and score candidate coverage, not localization."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from analyze_development_replay import diagnose  # noqa: E402
from analyze_inventory_scores import verify_bundle  # noqa: E402
from coverage_probe import (  # noqa: E402
    KINDS,
    PARENT_PROTOCOL,
    PROTOCOL,
    digest,
    fuse,
    inject,
    inputs,
    query_fields,
    require,
    validate_protocol,
    write_json,
)

ACTIONS = tuple(f"{name}_{k}" for k in (50, 200) for name in KINDS)


def validate_capture(record: dict, parent: dict, query: str) -> None:
    for key in ("id", "repo", "base_commit", "text_sha256"):
        require(record[key] == parent[key], f"trace join mismatch: {key}")
    n = len(parent["universe"])
    require(record["universe_units"] == n, "universe size mismatch")
    require(record["query_fields"] == query_fields(query), "query fields changed")
    parity = record["lexical_feature_parity"]
    expected_parity = {
        f"{pool}/{field}/{feature}"
        for pool in ("base", "wide")
        for field in ("full", "title", "code")
        for feature in ("rel", "logrank")
    }
    require(set(parity) == expected_parity, "incomplete lexical parity")
    require(
        all(math.isfinite(v) and 0 <= v <= 2e-6 for v in parity.values()), "lexical parity failed"
    )
    orders = record["field_orders_top1000"]
    require(list(orders) == ["full", "title", "code", "quoted"], "field list changed")
    for rows in [*orders.values(), record["rrf_order"], record["reference_order"]]:
        require(
            len(rows) == len(set(rows)) and all(type(r) is int and 0 <= r < n for r in rows),
            "invalid candidate row identity",
        )
    require(all(len(r) <= 1000 for r in orders.values()), "field depth exceeded")
    rrf = fuse(list(orders.values()))
    require(record["rrf_order"] == rrf, "fusion changed")
    shuffled = list(range(n))
    random.Random(f"37:{parent['id']}").shuffle(shuffled)
    base, wide = (parent["actions"][f"{p}_local"]["ranked_rows"] for p in ("base", "wide"))
    require(set(record["actions"]) == set(ACTIONS), "action set changed")
    for k in (50, 200):
        expected = {
            "base": base[:k],
            "wide": wide[:k],
            "bm25_full": orders["full"][:k],
            "field_rrf": rrf[:k],
            "inject_rrf": inject(base, rrf, k),
            "inject_refs": inject(base, record["reference_order"], k),
            "inject_random": inject(base, shuffled, k),
        }
        for name, rows in expected.items():
            action = record["actions"][f"{name}_{k}"]
            require(
                action
                == {
                    "rows": rows,
                    "added_vs_base_read": sorted(set(rows) - set(base[:k])),
                    "removed_vs_base_read": sorted(set(base[:k]) - set(rows)),
                    "outside_base_pool": sorted(set(rows) - set(parent["pools"]["base"]["rows"])),
                },
                f"candidate selection changed: {name}_{k}",
            )


def coverage(rows: list[int], universe: list[dict], targets: set[str]) -> dict:
    require(bool(targets), "empty targets")
    require(len(rows) == len(set(rows)), "duplicate read rows")
    require(all(type(r) is int and 0 <= r < len(universe) for r in rows), "invalid read rows")
    found = targets & {universe[r]["id"] for r in rows}
    return {
        "read_units": len(rows),
        "found": sorted(found),
        "any": int(bool(found)),
        "all": int(found == targets),
        "recall": len(found) / len(targets),
    }


def summarize(rows: list[dict]) -> dict:
    result = {}
    for action in ACTIONS:
        budget = int(action.rsplit("_", 1)[1])
        base = f"base_{budget}"
        new = [r for r in rows if r["actions"][action]["any"] and not r["actions"][base]["any"]]
        lost = [r for r in rows if not r["actions"][action]["any"] and r["actions"][base]["any"]]
        projects = sorted({r["repo"] for r in new})
        target_changes = {
            label: [
                {"id": r["id"], "targets": sorted(delta)}
                for r in rows
                if (delta := set(r["actions"][a]["found"]) - set(r["actions"][b]["found"]))
            ]
            for label, a, b in (("added", action, base), ("lost", base, action))
        }
        result[action] = {
            "any_covered": sum(r["actions"][action]["any"] for r in rows),
            "all_covered": sum(r["actions"][action]["all"] for r in rows),
            "mean_target_recall": sum(r["actions"][action]["recall"] for r in rows) / len(rows),
            "targets_covered": sum(len(r["actions"][action]["found"]) for r in rows),
            "read_units": sum(r["actions"][action]["read_units"] for r in rows),
            "newly_covered_issues": [r["id"] for r in new],
            "lost_covered_issues": [r["id"] for r in lost],
            "newly_covered_projects": projects,
            "target_changes": target_changes,
            "passes_necessary_followup_gate": len(projects) >= 2 and not lost,
        }
    return result


def analyze(bundle: Path, parent_dir: Path, historical: Path, out: Path) -> dict:
    require(not out.exists(), "use a new analysis directory")
    protocol = json.loads(PROTOCOL.read_bytes())
    validate_protocol(protocol)
    require(
        digest(PARENT_PROTOCOL) == protocol["parent_protocol_sha256"], "parent protocol changed"
    )
    selected = inputs(parent_dir, json.loads(PARENT_PROTOCOL.read_bytes()))
    require([x[0]["id"] for x in selected] == protocol["fit_ids"], "fit cohort changed")
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    require(
        manifest["protocol"] == protocol and manifest["protocol_sha256"] == digest(PROTOCOL),
        "protocol changed",
    )
    require(
        manifest["parent_manifest_sha256"] == digest(parent_dir / "manifest.json"), "parent changed"
    )
    for name, sha in manifest["source_sha256"].items():
        require(digest(ROOT / name) == sha, f"capture source changed: {name}")
    index = json.loads((bundle / "index.json").read_bytes())
    require(
        not index["failures"] and set(index["completed"]) == set(protocol["fit_ids"]),
        "incomplete probe",
    )
    summary = json.loads((bundle / "summary.json").read_bytes())
    require(
        summary == {"expected": len(selected), "completed": len(selected), "failures": []},
        "summary mismatch",
    )
    # Verify audit and label provenance only after the complete inference capture exists.
    _, gold, audit_verification = verify_bundle(historical)
    audit_path = historical / "inventory-audit-7012218/instances.jsonl"
    audit = {r["id"]: r for r in map(json.loads, audit_path.read_bytes().splitlines())}
    rows, files, max_parity, total_seconds, seen_issues = [], {}, 0.0, 0.0, set()
    for item, query, parent in selected:
        qid = item["id"]
        entry = index["completed"][qid]
        filename = hashlib.sha256(qid.encode()).hexdigest() + ".json.gz"
        require(
            entry["file"] == filename and digest(bundle / filename) == entry["sha256"],
            "capture checksum mismatch",
        )
        files[filename] = entry["sha256"]
        record = json.loads(gzip.decompress((bundle / filename).read_bytes()))
        require(record["manifest_sha256"] == digest(bundle / "manifest.json"), "manifest mismatch")
        require(
            record["parent_trace_sha256"] == protocol["trace_sha256"][qid], "trace parent mismatch"
        )
        validate_capture(record, parent, query)
        max_parity = max(max_parity, *record["lexical_feature_parity"].values())
        total_seconds += record["timing"]["total_seconds"]
        diagnostic = diagnose(parent, gold[qid], audit[qid], item)
        require(
            diagnostic["all_gold_unique"], "nonunique fit gold needs an explicit identity policy"
        )
        issue_key = (item["repo"].casefold(), str(gold[qid]["issue"]))
        require(issue_key not in seen_issues, "related PRs need outcome-independent deduplication")
        seen_issues.add(issue_key)
        targets = set(gold[qid]["gold_functions"])
        rows.append(
            {
                "id": qid,
                "repo": item["repo"],
                "issue": gold[qid]["issue"],
                "language": item["language"],
                "gold": sorted(targets),
                "all_gold_unique": True,
                "gold_in_parser_error_files": diagnostic["gold_in_parser_error_files"],
                "baseline_ce50_hit_at_10": diagnostic["modes"]["strict_symbol"]["actions"][
                    "base_ce50"
                ]["hit@10"],
                "actions": {
                    name: coverage(action["rows"], parent["universe"], targets)
                    for name, action in record["actions"].items()
                },
            }
        )
    result = {
        "schema": "fit-coverage-analysis-v1",
        "scope": "Exploratory original fit cases only; coverage is an upper bound on reranking success, not localization accuracy or a novelty claim.",
        "issues": len(rows),
        "projects": len({r["repo"] for r in rows}),
        "gold_count": sum(len(r["gold"]) for r in rows),
        "actions": summarize(rows),
        "verification": {
            "protocol_sha256": digest(PROTOCOL),
            "probe_source_sha256": manifest["source_sha256"],
            "analysis_source_sha256": {
                p: digest(ROOT / p)
                for p in (
                    "scripts/analyze_coverage_probe.py",
                    "scripts/analyze_development_replay.py",
                    "scripts/analyze_inventory_scores.py",
                )
            },
            "probe_files_sha256": {
                **files,
                **{p: digest(bundle / p) for p in ("manifest.json", "index.json", "summary.json")},
            },
            "max_lexical_feature_difference": max_parity,
            "capture_seconds_sum": total_seconds,
            "audit": audit_verification,
        },
        "limitations": [
            "Count limits do not equalize token budgets or total retrieval/reranking cost.",
            "These fit cases and failure descriptions were inspected before protocol selection.",
            "Lexical name references can match comments/literals and are not typed call edges.",
            "One deterministic random control does not estimate a random-policy distribution.",
            "Verification rebuilds action selection from saved field/reference orders; it does not independently recompute those orders from source.",
            "No labels were removed and no validation rows were used in this probe.",
        ],
    }
    lines = [
        "Fit-only candidate read coverage; this is NOT hit@10 or a confirmatory comparison.",
        f"action | any/{len(rows)} | all/{len(rows)} | targets/{result['gold_count']} | mean target recall | added/lost issues",
    ]
    for name, value in result["actions"].items():
        lines.append(
            f"{name} | {value['any_covered']} | {value['all_covered']} | {value['targets_covered']} | {value['mean_target_recall']:.4f} | {len(value['newly_covered_issues'])}/{len(value['lost_covered_issues'])}"
        )
    out.mkdir(parents=True)
    write_json(out / "analysis.json", result)
    (out / "rows.jsonl").write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8"
    )
    (out / "table.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--historical", type=Path, default=ROOT / "reports/pace-7012506")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.bundle, args.parent, args.historical, args.out)
    print((args.out / "table.txt").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
