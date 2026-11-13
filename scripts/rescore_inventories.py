"""Exploratory inventory-based scoring of saved full-report predictions; no inference.

The strict and name-group modes are explicit sensitivities, not a finalized evaluator.
Gold never participates in prediction resolution. Missing runs are not scored as failures.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from audit_symbol_inventories import sha256  # noqa: E402

from allfather.eval.metrics import score  # noqa: E402
from allfather.eval.resolution import SymbolResolver, ranking_slots  # noqa: E402

VERSION = "inventory-rescore-v1-exploratory"
MODES = ("strict_symbol", "name_group")


def rows_by_id(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]
    result = {row["id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate result IDs: {path}")
    return result


def score_answer(resolver: SymbolResolver, answer: object, gold: list[str]) -> dict:
    resolutions = resolver.answer(answer, k=10)
    ranked = ranking_slots(resolutions)
    result = score(ranked, gold, [1, 5, 10])
    return {
        "metrics": {
            **{f"hit@{k}": result.hit[k] for k in (1, 5, 10)},
            "recall@10": result.recall[10],
            "all@10": result.full[10],
            "mrr@10": result.rr,
        },
        "slots": [asdict(r) for r in resolutions],
        "resolution_counts": dict(Counter(r.status for r in resolutions)),
        "answer_shape_valid": isinstance(answer, dict)
        and isinstance(answer.get("functions"), list),
    }


def aggregate(rows: list[dict], mode: str) -> dict:
    if not rows:
        return {"issues": 0, "metrics": None}
    metrics = rows[0]["modes"][mode]["metrics"]
    return {
        "issues": len(rows),
        "metrics": {
            key: sum(r["modes"][mode]["metrics"][key] for r in rows) / len(rows) for key in metrics
        },
    }


def summarize_run(rows: list[dict], expected: set[str]) -> dict:
    observed = {r["id"] for r in rows}
    return {
        "expected_instances": len(expected),
        "observed_instances": len(rows),
        "missing_ids": sorted(expected - observed),
        "scored_ids": sorted(observed),
        "projects": len({r["repo"].casefold() for r in rows}),
        "by_language": dict(Counter(r["language"] for r in rows)),
        "modes": {
            mode: {
                "all_observed": aggregate(rows, mode),
                "all_gold_unique": aggregate([r for r in rows if r["all_gold_unique"]], mode),
                "unique_gold_without_gold_file_parser_flags": aggregate(
                    [
                        r
                        for r in rows
                        if r["all_gold_unique"] and not r["gold_in_parser_error_files"]
                    ],
                    mode,
                ),
                "resolution_counts": dict(
                    sum((Counter(r["modes"][mode]["resolution_counts"]) for r in rows), Counter())
                ),
                "invalid_answer_shape": sum(
                    not r["modes"][mode]["answer_shape_valid"] for r in rows
                ),
                "resolved_aliases_in_parser_error_files": sum(
                    r["modes"][mode]["aliases_in_parser_error_files"] for r in rows
                ),
            }
            for mode in MODES
        },
    }


def verify_audit(directory: Path, audit: Path, gold_path: Path) -> tuple[dict, dict, dict]:
    summary = json.loads((audit / "summary.json").read_bytes())
    provenance = json.loads((audit / "provenance.json").read_bytes())
    if summary.get("integrity_ok") is not True or summary["failures"]:
        raise ValueError("inventory audit did not pass")
    for path, key in (
        (directory / "manifest.json", "manifest_sha256"),
        (directory / "index.json", "index_sha256"),
        (gold_path, "gold_sha256"),
        (audit / "instances.jsonl", "instances_sha256"),
    ):
        if sha256(path) != provenance[key]:
            raise ValueError(f"audit input changed: {path}")
    records = rows_by_id(audit / "instances.jsonl")
    if len(records) != summary["expected_instances"]:
        raise ValueError("audit instance count mismatch")
    return records, provenance, summary


def run(directory: Path, audit_dir: Path, out: Path, root: Path = ROOT) -> dict:
    gold_path = root / "data/fresh-full/gold.jsonl"
    audited, provenance, audit_summary = verify_audit(directory, audit_dir, gold_path)
    gold = {q: r for q, r in rows_by_id(gold_path).items() if r["full_text_status"] == "unchanged"}
    if set(gold) != set(audited):
        raise ValueError("gold/audit instance sets differ")
    index = json.loads((directory / "index.json").read_bytes())["instances"]
    if set(index) != set(gold):
        raise ValueError("index/gold instance sets differ")
    manifest_path = root / "data/fresh-full/manifest.json"
    agent_ids = set(json.loads(manifest_path.read_bytes())["agent_subsample"]) & set(gold)
    runs, input_hashes, expected = {}, {}, {}
    paths = sorted((root / "results/research/frontier").glob("fresh-full_*.jsonl"))
    paths += sorted((root / "results/research/frontier").glob("fresh-full-agents_*.jsonl"))
    if not paths:
        raise ValueError("no saved full-report runs")
    for original in paths:
        path = original
        if "_swerank-" in path.name:
            # Never silently fall back to the defective original import.
            path = root / "results/research/corrections/import-v1" / path.name
            if not path.exists():
                raise ValueError(f"corrected SweRank import missing: {path}")
            input_hashes[original.relative_to(root).as_posix()] = sha256(original)
        input_hashes[path.relative_to(root).as_posix()] = sha256(path)
        runs[original.stem] = rows_by_id(path)
        expected[original.stem] = (
            agent_ids if original.name.startswith("fresh-full-agents_") else set(gold)
        )
        if set(runs[original.stem]) - expected[original.stem]:
            raise ValueError(f"out-of-set prediction IDs: {path}")
    out.mkdir(parents=True, exist_ok=False)
    scored = {name: [] for name in runs}
    with (out / "scores.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for number, (qid, target) in enumerate(sorted(gold.items()), 1):
            entry = index[qid]
            filename = entry["file"]
            if Path(filename).name != filename or "/" in filename or "\\" in filename:
                raise ValueError("inventory filename must be a basename")
            path = directory / filename
            payload = path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if digest != entry["sha256"] or digest != provenance["snapshot_sha256"][filename]:
                raise ValueError(f"inventory changed since audit: {qid}")
            inventory = json.loads(gzip.decompress(payload))
            if (inventory["repo"], inventory["base_commit"]) != (
                target["repo"],
                target["base_commit"],
            ):
                raise ValueError(f"inventory/gold identity mismatch: {qid}")
            ids = [unit["id"] for unit in inventory["symbols"]]
            # These constructors see the whole inventory and never the gold list.
            resolvers = {
                "strict_symbol": SymbolResolver(ids),
                "name_group": SymbolResolver(list(dict.fromkeys(ids))),
            }
            errors = set(inventory["parser_error_files"])
            for name, predictions in runs.items():
                if qid not in predictions:
                    continue  # missing collection is reported, not scored as an observed failure
                row = {
                    "run": name,
                    "id": qid,
                    "repo": target["repo"],
                    "language": target["language"],
                    "all_gold_unique": audited[qid]["all_gold_unique"],
                    "gold_in_parser_error_files": audited[qid]["gold_in_parser_error_files"],
                    "modes": {},
                }
                for mode, resolver in resolvers.items():
                    result = score_answer(
                        resolver, predictions[qid].get("answer"), target["gold_functions"]
                    )
                    result["aliases_in_parser_error_files"] = sum(
                        r["status"] == "resolved" and r["canonical"].split("::", 1)[0] in errors
                        for r in result["slots"]
                    )
                    row["modes"][mode] = result
                handle.write(json.dumps(row) + "\n")
                # Keep small metrics/diagnostics in memory; full slots are persisted above.
                for value in row["modes"].values():
                    del value["slots"]
                scored[name].append(row)
            if number % 50 == 0:
                print(f"resolved {number}/{len(gold)} inventories", flush=True)
    report = {
        "schema": VERSION,
        "scope": "Descriptive exploratory sensitivities, not finalized metrics or significance tests. No inference or cost calculation.",
        "policies": {
            "strict_symbol": "Duplicate inventory IDs remain ambiguous and receive no credit; all gold targets stay in the denominator.",
            "name_group": "Each path/name group is one target even if it denotes multiple declarations; this is not occurrence-level correctness.",
            "slots": "At most the first ten submitted slots; invalid/ambiguous/duplicate slots consume rank positions; MRR is truncated at ten.",
            "missing_results": "Absent result rows are listed and not imputed; observed missing/malformed answers score as failures.",
        },
        "limitations": [
            "Unique IDs and aliases are unique among extracted symbols only; parser errors may hide declarations.",
            "Historical gold, inference access, costs and model exposure are not repaired by rescoring.",
            "Corrected SweRank imports are used, but membership in original exported corpora remains unverified.",
            "Subset sensitivities change the population; compare systems only on identical issue IDs.",
        ],
        "audit_counts": audit_summary["counts"],
        "runs": {name: summarize_run(rows, expected[name]) for name, rows in scored.items()},
    }
    review = [
        r for r in audited.values() if not r["all_gold_unique"] or r["gold_in_parser_error_files"]
    ]
    (out / "review-gold.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    sources = [
        Path(__file__),
        ROOT / "scripts/audit_symbol_inventories.py",
        ROOT / "src/allfather/eval/resolution.py",
        ROOT / "src/allfather/eval/metrics.py",
    ]
    evidence = {
        "input_sha256": input_hashes,
        "gold_sha256": sha256(gold_path),
        "dataset_manifest_sha256": sha256(manifest_path),
        "audit_sha256": {
            name: sha256(audit_dir / name)
            for name in ("summary.json", "provenance.json", "instances.jsonl")
        },
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in sources},
        "scores_sha256": sha256(out / "scores.jsonl"),
    }
    (out / "provenance.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    lines = [
        "Exploratory hit@10; compare only matching issue IDs. Strict/name-group are different target interpretations.",
        "run | observed/expected | strict all | name-group all | strict unique-gold | unique-gold n",
    ]
    for name, result in report["runs"].items():
        a = result["modes"]["strict_symbol"]["all_observed"]
        b = result["modes"]["name_group"]["all_observed"]
        c = result["modes"]["strict_symbol"]["all_gold_unique"]
        values = [f"{r['metrics']['hit@10']:.4f}" if r["issues"] else "NA" for r in (a, b, c)]
        lines.append(
            f"{name} | {result['observed_instances']}/{result['expected_instances']} | {' | '.join(values)} | {c['issues']}"
        )
    (out / "table.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventories", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inventories, args.audit, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
