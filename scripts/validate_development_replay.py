"""Validate saved replay traces without model loading, gold scoring or network access."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "development-stage-replay-v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordered(rows: list[int], scores: list[float]) -> list[int]:
    require(len(rows) == len(scores), "score/row length mismatch")
    require(np.isfinite(scores).all(), "nonfinite score")
    return [rows[i] for i in np.argsort(-np.asarray(scores), kind="stable")]


def valid_rows(rows: list, n: int) -> None:
    require(all(type(r) is int and 0 <= r < n for r in rows), "invalid row index")
    require(len(set(rows)) == len(rows), "duplicate row index")


def nonnegative(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_trace(trace: dict, item: dict, manifest_hash: str) -> dict:
    require(trace["schema"] == SCHEMA, "trace schema mismatch")
    require(trace["manifest_sha256"] == manifest_hash, "trace manifest hash mismatch")
    for key in ("id", "repo", "base_commit", "text_sha256"):
        require(trace[key] == item[key], f"trace {key} mismatch")
    universe = trace["universe"]
    n = len(universe)
    require([u["row"] for u in universe] == list(range(n)), "noncontiguous universe rows")
    for unit in universe:
        require(isinstance(unit["id"], str) and "::" in unit["id"], "invalid unit ID")
        require(len(bytes.fromhex(unit["text_key"])) == 16, "invalid content key")
    files = trace["files"]
    require(len({f["path"] for f in files}) == len(files), "duplicate file path")
    paths = {f["path"] for f in files}
    require(all(u["id"].split("::", 1)[0] in paths for u in universe), "unit file absent")
    for file in files:
        require(len(bytes.fromhex(file["blob"])) in (20, 32), "invalid Git blob ID")
    require(set(trace["pools"]) == {"base", "wide"}, "unexpected pools")
    expected_actions = {
        f"{pool}_{stage}" for pool in ("base", "wide") for stage in ("local", "ce50", "ce200")
    }
    require(set(trace["actions"]) == expected_actions, "missing or unexpected action")
    execution = trace["ce_execution_order"]
    require(
        len(execution) == 4 and set(execution) == {a for a in expected_actions if "_ce" in a},
        "invalid CE execution order",
    )
    for key in ("snapshot_prepare_seconds", "shared_signals_seconds", "total_seconds"):
        require(nonnegative(trace[key]), f"invalid {key}")
    features_by_pool = {}
    for label, pool in trace["pools"].items():
        rows = pool["rows"]
        valid_rows(rows, n)
        require(rows == sorted(rows), "candidate rows not in index order")
        require(len(pool["features"]) == len(rows), "feature row count mismatch")
        require(
            all(
                len(f) == len(trace["feature_names"]) and np.isfinite(f).all()
                for f in pool["features"]
            ),
            "invalid feature matrix",
        )
        features_by_pool[label] = dict(zip(rows, pool["features"], strict=True))
        semantic = ordered(rows, pool["semantic_scores"])
        require(pool["semantic_ranked_rows"] == semantic, "semantic ranking mismatch")
        selected = pool["minilm_rows"]
        require(selected == semantic[:20], "MiniLM prefix mismatch")
        local = ordered(selected, pool["minilm_ranker_scores"]) + [
            r for r in semantic if r not in set(selected)
        ]
        require(
            trace["actions"][f"{label}_local"]["ranked_rows"] == local, "local ranking mismatch"
        )
        for stage in ("local", "ce50", "ce200"):
            action = trace["actions"][f"{label}_{stage}"]
            ranked = action["ranked_rows"]
            valid_rows(ranked, n)
            require(set(ranked) == set(rows), "action is not a permutation of its pool")
            require(nonnegative(action["seconds"]), "invalid action time")
            if stage == "local":
                continue
            depth = int(stage[2:])
            read = local[:depth]
            raw = action["raw_scores"]
            require(action["read_rows"] == read, "CE read prefix mismatch")
            require(len(raw) == len(read) and np.isfinite(raw).all(), "invalid CE scores")
            require(
                type(action["tokens_computed"]) is int
                and action["tokens_computed"] >= int(bool(read)),
                "invalid CE token count",
            )
            require(action["weight"] == 1.0, "unexpected blend weight")

            def z(values):
                values = np.asarray(values, dtype=float)
                return (
                    (values - values.mean()) / values.std()
                    if len(values) and values.std() > 0
                    else np.zeros_like(values)
                )

            combined = z(-np.log1p(np.arange(1, len(read) + 1))) + z(raw)
            expected = ordered(read, combined.tolist()) + local[len(read) :]
            require(ranked == expected, "CE blend or untouched tail mismatch")
    base, wide = features_by_pool["base"], features_by_pool["wide"]
    require(set(base).issubset(wide), "wide pool does not contain base pool")
    require(
        all(features == wide[row] for row, features in base.items()),
        "shared candidate features changed",
    )
    require(
        trace["pools"]["wide"]["budgets"]
        == {k: v * 4 for k, v in trace["pools"]["base"]["budgets"].items()},
        "wide budgets mismatch",
    )
    return {
        "id": item["id"],
        "universe": n,
        "base_pool": len(base),
        "wide_pool": len(wide),
        "total_seconds": trace["total_seconds"],
        "actions": {
            k: {"seconds": v["seconds"], "tokens_computed": v.get("tokens_computed")}
            for k, v in trace["actions"].items()
        },
    }


def validate_bundle(bundle: Path) -> dict:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    index = json.loads((bundle / "index.json").read_bytes())
    summary = json.loads((bundle / "summary.json").read_bytes())
    require(manifest["schema"] == SCHEMA, "manifest schema mismatch")
    plan_path = ROOT / "data/research/development-pilot-v1.json"
    require(manifest["plan_sha256"] == digest(plan_path), "pilot plan hash mismatch")
    plan = json.loads(plan_path.read_bytes())
    selected = manifest["instances"]
    require(
        bool(selected) and selected == plan["instances"][: len(selected)],
        "selection is not the frozen plan prefix",
    )
    ids = [item["id"] for item in selected]
    require(len(set(ids)) == len(ids), "duplicate selected ID")
    require(not summary["failures"] and not index["failures"], "run contains failures")
    require(
        summary["expected"] == summary["completed"] == len(ids), "completion denominator mismatch"
    )
    require(set(index["completed"]) == set(ids), "index IDs mismatch")
    manifest_hash = digest(manifest_path)
    records, failures = [], []
    for item in selected:
        try:
            entry = index["completed"][item["id"]]
            filename = hashlib.sha256(item["id"].encode()).hexdigest() + ".json.gz"
            require(entry["file"] == filename, "unexpected trace filename")
            path = bundle / filename
            require(digest(path) == entry["sha256"], "trace checksum mismatch")
            trace = json.loads(gzip.decompress(path.read_bytes()))
            record = validate_trace(trace, item, manifest_hash)
            for key in ("universe", "base_pool", "wide_pool"):
                require(entry[key] == record[key], f"index {key} mismatch")
            records.append(record)
        except (ValueError, KeyError, TypeError, OSError, EOFError) as exc:
            failures.append({"id": item["id"], "error": str(exc)})
    return {
        "schema": "development-replay-integrity-v1",
        "ok": not failures,
        "expected": len(ids),
        "validated": len(records),
        "failures": failures,
        "summary": summary,
        "manifest_sha256": manifest_hash,
        "records": records,
        "scope": "Saved-trace integrity and internal stage consistency only; no gold scoring, model recomputation, Git-tree completeness or scientific claim validation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        report = validate_bundle(args.bundle)
    except (ValueError, KeyError, TypeError, OSError, EOFError) as exc:
        report = {
            "schema": "development-replay-integrity-v1",
            "ok": False,
            "failures": [{"error": str(exc)}],
        }
    if args.out:
        with args.out.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    print(json.dumps(report, indent=2))
    return int(not report["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
