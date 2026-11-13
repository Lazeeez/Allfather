import copy
import gzip
import hashlib
import json
import math

import pytest

from scripts import validate_development_replay as audit


def fixture_trace():
    item = json.loads((audit.ROOT / "data/research/development-pilot-v1.json").read_bytes())[
        "instances"
    ][0]
    trace = {
        **{k: item[k] for k in ("id", "repo", "base_commit", "text_sha256")},
        "schema": audit.SCHEMA,
        "manifest_sha256": "manifest",
        "universe": [
            {"row": i, "id": "a.py::same_name", "text_key": f"{i:032x}"} for i in range(210)
        ],
        "files": [{"path": "a.py", "blob": "a" * 40}],
        "feature_names": ["feature"],
        "pools": {},
        "actions": {},
        "ce_execution_order": ["wide_ce200", "base_ce50", "base_ce200", "wide_ce50"],
        "snapshot_prepare_seconds": 1.0,
        "shared_signals_seconds": 1.0,
        "total_seconds": 8.0,
    }
    for label, n, scale in (("base", 60, 1), ("wide", 210, 4)):
        rows = list(range(n))
        trace["pools"][label] = {
            "rows": rows,
            "features": [[i] for i in rows],
            "semantic_scores": [-i for i in rows],
            "semantic_ranked_rows": rows,
            "minilm_rows": rows[:20],
            "minilm_ranker_scores": [-i for i in rows[:20]],
            "budgets": {"signal": 60 * scale},
        }
        trace["actions"][f"{label}_local"] = {"ranked_rows": rows, "seconds": 1.0}
        for depth in (50, 200):
            read = rows[:depth]
            trace["actions"][f"{label}_ce{depth}"] = {
                "ranked_rows": rows,
                "read_rows": read,
                "raw_scores": [-math.log1p(i + 1) for i in range(len(read))],
                "tokens_computed": len(read) * 10,
                "seconds": 1.0,
                "weight": 1.0,
            }
    return trace, item


def test_trace_validation_preserves_same_name_rows():
    trace, item = fixture_trace()
    report = audit.validate_trace(trace, item, "manifest")
    assert (report["universe"], report["base_pool"], report["wide_pool"]) == (210, 60, 210)


@pytest.mark.parametrize(
    "defect",
    ["duplicate_row", "changed_feature", "read_prefix", "tail", "missing_action", "nonfinite"],
)
def test_trace_validation_rejects_stage_corruption(defect):
    original, item = fixture_trace()
    trace = copy.deepcopy(original)
    if defect == "duplicate_row":
        trace["pools"]["base"]["rows"][1] = 0
    elif defect == "changed_feature":
        trace["pools"]["wide"]["features"][0] = [99]
    elif defect == "read_prefix":
        trace["actions"]["wide_ce50"]["read_rows"] = list(reversed(range(50)))
    elif defect == "tail":
        rows = list(range(210))
        rows[-1], rows[-2] = rows[-2], rows[-1]
        trace["actions"]["wide_ce50"]["ranked_rows"] = rows
    elif defect == "missing_action":
        del trace["actions"]["base_local"]
    else:
        trace["pools"]["base"]["semantic_scores"][0] = float("nan")
    with pytest.raises(ValueError):
        audit.validate_trace(trace, item, "manifest")


def test_bundle_validates_hashes_and_completion_denominator(tmp_path):
    trace, item = fixture_trace()

    def write(name, data):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")

    write(
        "manifest.json",
        {
            "schema": audit.SCHEMA,
            "instances": [item],
            "plan_sha256": audit.digest(audit.ROOT / "data/research/development-pilot-v1.json"),
        },
    )
    trace["manifest_sha256"] = audit.digest(tmp_path / "manifest.json")
    filename = hashlib.sha256(item["id"].encode()).hexdigest() + ".json.gz"
    (tmp_path / filename).write_bytes(gzip.compress(json.dumps(trace).encode()))
    write(
        "index.json",
        {
            "failures": [],
            "completed": {
                item["id"]: {
                    "file": filename,
                    "sha256": audit.digest(tmp_path / filename),
                    "universe": 210,
                    "base_pool": 60,
                    "wide_pool": 210,
                }
            },
        },
    )
    write("summary.json", {"expected": 1, "completed": 1, "failures": []})
    assert audit.validate_bundle(tmp_path)["ok"]
    (tmp_path / filename).write_bytes(b"corrupt")
    report = audit.validate_bundle(tmp_path)
    assert not report["ok"] and "checksum" in report["failures"][0]["error"]
    write("summary.json", {"expected": 2, "completed": 1, "failures": []})
    with pytest.raises(ValueError, match="denominator"):
        audit.validate_bundle(tmp_path)
