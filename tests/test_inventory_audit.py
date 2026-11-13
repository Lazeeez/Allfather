import gzip
import hashlib
import json

import pytest

from scripts.audit_symbol_inventories import audit, inspect_snapshot


def snapshot():
    return {
        "schema": "symbol-inventory-v1",
        "repo": "org/repo",
        "base_commit": "abc",
        "collection_complete": True,
        "files": [
            {"path": "a.py", "language": "python", "parser_has_error": False},
            {"path": "b.py", "language": "python", "parser_has_error": True},
        ],
        "symbols": [
            {"id": "a.py::run", "kind": "function", "start_line": 1, "end_line": 2},
            {"id": "b.py::overload", "kind": "function", "start_line": 1, "end_line": 2},
            {"id": "b.py::overload", "kind": "function", "start_line": 3, "end_line": 4},
        ],
        "colliding_ids": {"b.py::overload": 2},
        "parser_error_files": ["b.py"],
    }


def test_repository_flags_do_not_make_unrelated_gold_ambiguous():
    report = inspect_snapshot(snapshot(), ["a.py::run"])
    assert report["all_gold_unique"]
    assert report["colliding_ids"] == 1 and report["parser_error_files"] == 1
    assert report["gold_in_parser_error_files"] == 0


def test_ambiguous_and_missing_gold_are_retained_with_source_ranges():
    report = inspect_snapshot(snapshot(), ["b.py::overload", "c.py::absent"])
    assert report["gold_status_counts"] == {"ambiguous": 1, "missing": 1}
    assert len(report["gold"][0]["occurrences"]) == 2
    assert report["gold"][1]["file_has_parser_error"] is None
    assert not report["any_gold_unique"]


def test_inconsistent_collision_summary_is_rejected():
    value = snapshot()
    value["colliding_ids"] = {}
    with pytest.raises(ValueError, match="collision counts"):
        inspect_snapshot(value, [])


def fixture_files(tmp_path):
    source = tmp_path / "inventories"
    source.mkdir()
    name = hashlib.sha256(b"org/repo@abc").hexdigest() + ".json.gz"
    payload = gzip.compress(json.dumps(snapshot()).encode())
    (source / name).write_bytes(payload)
    manifest = {
        "schema": "symbol-inventory-v1",
        "instances": [{"id": "q", "repo": "org/repo", "base_commit": "abc"}],
        "source_sha256": {},
        "parser_versions": {},
    }
    index = {
        "schema": "symbol-inventory-v1",
        "failures": [],
        "instances": {
            "q": {
                "file": name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "files": 2,
                "symbols": 3,
                "colliding_ids": 1,
                "parser_error_files": 1,
            }
        },
    }
    (source / "manifest.json").write_text(json.dumps(manifest))
    (source / "index.json").write_text(json.dumps(index))
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        json.dumps(
            {
                "id": "q",
                "repo": "org/repo",
                "base_commit": "abc",
                "full_text_status": "unchanged",
                "gold_functions": ["a.py::run"],
            }
        )
        + "\n"
    )
    return source, gold, name


def test_audit_checks_hashes_and_keeps_failures_in_denominator(tmp_path):
    source, gold, name = fixture_files(tmp_path)
    good = audit(source, gold, tmp_path / "good")
    assert good["integrity_ok"] and good["counts"]["instances_all_gold_unique"] == 1
    (source / name).write_bytes(b"corrupted")
    bad = audit(source, gold, tmp_path / "bad")
    assert not bad["integrity_ok"] and bad["expected_instances"] == 1
    assert len(bad["failures"]) == 1 and "SHA256 mismatch" in bad["failures"][0]["error"]


def test_snapshot_mismatch_fails_even_with_intact_inventory(tmp_path):
    source, gold, _ = fixture_files(tmp_path)
    row = json.loads(gold.read_text())
    row["base_commit"] = "different"
    gold.write_text(json.dumps(row))
    result = audit(source, gold, tmp_path / "mismatch")
    assert not result["integrity_ok"]
    assert "different snapshots" in result["failures"][0]["error"]
