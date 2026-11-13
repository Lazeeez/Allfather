"""Validate saved inventories and audit gold coverage without changing labels or scoring.

Reads one compressed snapshot at a time. No cloning, parsing, model inference or network.
Repository-wide parser/collision flags are distinguished from flags affecting gold IDs.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "symbol-inventory-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_snapshot(inventory: dict, gold: list[str]) -> dict:
    files = {f["path"]: f for f in inventory["files"]}
    if len(files) != len(inventory["files"]):
        raise ValueError("duplicate file paths")
    errors = {f["path"] for f in inventory["files"] if f["parser_has_error"]}
    if sorted(errors) != sorted(inventory["parser_error_files"]):
        raise ValueError("parser-error file list disagrees with file records")
    units = defaultdict(list)
    by_language = defaultdict(Counter)
    for f in files.values():
        by_language[f["language"]]["files"] += 1
        by_language[f["language"]]["parser_error_files"] += int(f["parser_has_error"])
    for unit in inventory["symbols"]:
        path, sep, name = unit["id"].partition("::")
        if not sep or not name or path not in files:
            raise ValueError(f"symbol has no matching file: {unit['id']}")
        if not 1 <= unit["start_line"] <= unit["end_line"]:
            raise ValueError(f"invalid source range: {unit['id']}")
        units[unit["id"]].append(unit)
        by_language[files[path]["language"]]["symbol_occurrences"] += 1
    collisions = {key: len(value) for key, value in units.items() if len(value) > 1}
    if collisions != inventory["colliding_ids"]:
        raise ValueError("collision counts disagree with symbol records")
    for key in collisions:
        language = files[key.split("::", 1)[0]]["language"]
        by_language[language]["colliding_ids"] += 1
    targets = []
    for key in sorted(set(gold)):
        occurrences = units.get(key, [])
        path = key.split("::", 1)[0]
        targets.append(
            {
                "id": key,
                "status": "unique"
                if len(occurrences) == 1
                else "ambiguous"
                if occurrences
                else "missing",
                "file_in_inventory": path in files,
                "file_has_parser_error": path in errors if path in files else None,
                "occurrences": occurrences,
            }
        )
    counts = Counter(target["status"] for target in targets)
    return {
        "files": len(files),
        "symbols": len(inventory["symbols"]),
        "colliding_ids": len(collisions),
        "parser_error_files": len(errors),
        "by_language": dict(by_language),
        "gold_count": len(targets),
        "duplicate_gold_entries": len(gold) - len(set(gold)),
        "gold_status_counts": dict(counts),
        "gold_in_parser_error_files": sum(t["file_has_parser_error"] is True for t in targets),
        "all_gold_unique": bool(targets) and counts["unique"] == len(targets),
        "any_gold_unique": bool(counts["unique"]),
        "gold": targets,
    }


def audit(directory: Path, gold_path: Path, out: Path) -> dict:
    # A new output directory avoids overwriting previous evidence or the input inventory.
    out.mkdir(parents=True, exist_ok=False)
    manifest_path, index_path = directory / "manifest.json", directory / "index.json"
    manifest = json.loads(manifest_path.read_bytes())
    index = json.loads(index_path.read_bytes())
    gold_rows = [json.loads(line) for line in gold_path.read_bytes().splitlines() if line.strip()]
    gold_rows = [r for r in gold_rows if r["full_text_status"] == "unchanged"]
    gold = {row["id"]: row for row in gold_rows}
    items = {row["id"]: row for row in manifest["instances"]}
    if len(items) != len(manifest["instances"]) or len(gold) != len(gold_rows):
        raise ValueError("duplicate instance IDs in manifest or gold")
    if manifest["schema"] != SCHEMA or index["schema"] != SCHEMA:
        raise ValueError("unsupported inventory schema")
    if set(items) != set(index["instances"]) or set(items) != set(gold) or index["failures"]:
        raise ValueError("expected complete fresh-full inventory matching the gold instance IDs")
    counts, languages, failures = Counter(), defaultdict(Counter), []
    snapshot_hashes = {}
    with (out / "instances.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for qid, item in sorted(items.items()):
            try:
                entry, target = index["instances"][qid], gold[qid]
                expected_file = (
                    hashlib.sha256(f"{item['repo']}@{item['base_commit']}".encode()).hexdigest()
                    + ".json.gz"
                )
                if entry["file"] != expected_file:
                    raise ValueError("unexpected inventory filename")
                if (item["repo"], item["base_commit"]) != (target["repo"], target["base_commit"]):
                    raise ValueError("gold and manifest identify different snapshots")
                path = directory / expected_file
                actual_sha = sha256(path)
                if actual_sha != entry["sha256"]:
                    raise ValueError("snapshot SHA256 mismatch")
                inventory = json.loads(gzip.decompress(path.read_bytes()))
                if (inventory["schema"], inventory["repo"], inventory["base_commit"]) != (
                    SCHEMA,
                    item["repo"],
                    item["base_commit"],
                ) or inventory["collection_complete"] is not True:
                    raise ValueError("snapshot identity/schema/completeness mismatch")
                report = inspect_snapshot(inventory, target["gold_functions"])
                for key in ("files", "symbols", "colliding_ids", "parser_error_files"):
                    if report[key] != entry[key]:
                        raise ValueError(f"index disagrees with snapshot: {key}")
                snapshot_hashes[expected_file] = actual_sha
                handle.write(
                    json.dumps(
                        {
                            "id": qid,
                            "repo": item["repo"],
                            "base_commit": item["base_commit"],
                            **report,
                        }
                    )
                    + "\n"
                )
                counts["validated_instances"] += 1
                for key in (
                    "files",
                    "symbols",
                    "colliding_ids",
                    "parser_error_files",
                    "gold_count",
                    "gold_in_parser_error_files",
                    "duplicate_gold_entries",
                ):
                    counts[key] += report[key]
                for key in ("all_gold_unique", "any_gold_unique"):
                    counts[f"instances_{key}"] += int(report[key])
                counts["instances_with_parser_error_files"] += bool(report["parser_error_files"])
                counts["instances_with_colliding_ids"] += bool(report["colliding_ids"])
                counts["instances_with_gold_in_parser_error_files"] += bool(
                    report["gold_in_parser_error_files"]
                )
                for status in ("unique", "ambiguous", "missing"):
                    n = report["gold_status_counts"].get(status, 0)
                    counts[f"gold_{status}"] += n
                    counts[f"instances_with_{status}_gold"] += bool(n)
                for language, values in report["by_language"].items():
                    languages[language].update(values)
            except Exception as exc:
                failures.append({"id": qid, "error": f"{type(exc).__name__}: {exc}"})
    summary = {
        "schema": "inventory-gold-audit-v1",
        "expected_instances": len(items),
        "integrity_ok": not failures and counts["validated_instances"] == len(items),
        "counts": dict(counts),
        "by_language": dict(languages),
        "failures": failures,
        "scope": "Gold identity coverage only; no predictions rescored and no labels removed or repaired.",
        "limitations": [
            "File/symbol totals count instance snapshots, not distinct files/blobs across the dataset.",
            "Parser error flags indicate at least one error in a file, not necessarily at the gold symbol.",
            "Unique means unique among extracted symbols; parser errors can hide other declarations.",
            "Ambiguous IDs can reflect overloads, declarations, or extraction defects; manual diagnosis remains necessary.",
            "Integrity validates saved artifacts against their manifest/index, not tree completeness against Git.",
        ],
    }
    provenance = {
        "manifest_sha256": sha256(manifest_path),
        "index_sha256": sha256(index_path),
        "gold_sha256": sha256(gold_path),
        "audit_script_sha256": sha256(Path(__file__)),
        "inventory_source_sha256": manifest["source_sha256"],
        "parser_versions": manifest["parser_versions"],
        "snapshot_sha256": snapshot_hashes,
        "instances_sha256": sha256(out / "instances.jsonl"),
    }
    for name, value in (("summary.json", summary), ("provenance.json", provenance)):
        (out / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventories", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=ROOT / "data/fresh-full/gold.jsonl")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = audit(args.inventories, args.gold, args.out)
    print(json.dumps(summary, indent=2))
    return 0 if summary["integrity_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
