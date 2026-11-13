import gzip
import hashlib
import json

import pytest

from allfather.eval.resolution import SymbolResolver
from scripts.audit_symbol_inventories import audit
from scripts.rescore_inventories import rows_by_id, run, score_answer


def test_invalid_and_duplicate_predictions_cannot_promote_correct_answer():
    resolver = SymbolResolver(["a.py::wrong", "a.py::right"])
    answer = {
        "functions": [
            None,
            {"file": "a.py", "name": "wrong"},
            {"file": "a.py", "name": "wrong"},
            {"file": "a.py", "name": "right"},
        ]
    }
    result = score_answer(resolver, answer, ["a.py::right"])
    assert result["metrics"]["mrr@10"] == 0.25
    assert result["metrics"]["hit@1"] == 0
    assert result["resolution_counts"] == {"invalid": 1, "exact": 2, "duplicate": 1}


def test_ambiguous_gold_stays_in_denominator_in_both_modes():
    ids = ["a.py::overload", "a.py::overload", "a.py::unique"]
    answer = {"functions": [{"file": "a.py", "name": "overload"}]}
    strict = score_answer(SymbolResolver(ids), answer, ["a.py::overload", "a.py::unique"])
    groups = score_answer(
        SymbolResolver(list(dict.fromkeys(ids))), answer, ["a.py::overload", "a.py::unique"]
    )
    assert strict["metrics"]["hit@10"] == 0
    assert groups["metrics"]["hit@10"] == 1
    assert groups["metrics"]["recall@10"] == 0.5
    assert groups["metrics"]["all@10"] == 0


def test_resolution_does_not_change_when_gold_changes():
    resolver = SymbolResolver(["a.py::A.run", "a.py::B.run"])
    answer = {"functions": [{"file": "a.py", "name": "run"}]}
    a = score_answer(resolver, answer, ["a.py::A.run"])
    b = score_answer(resolver, answer, ["a.py::B.run"])
    assert a["slots"] == b["slots"]
    assert a["slots"][0]["status"] == "ambiguous"


def test_malformed_answer_is_failure_and_only_ten_slots_count():
    resolver = SymbolResolver(["a.py::right"])
    assert score_answer(resolver, None, ["a.py::right"])["metrics"]["hit@10"] == 0
    answer = {"functions": [None] * 10 + [{"file": "a.py", "name": "right"}]}
    result = score_answer(resolver, answer, ["a.py::right"])
    assert len(result["slots"]) == 10
    assert result["metrics"]["mrr@10"] == 0


def test_duplicate_result_rows_are_rejected(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text((json.dumps({"id": "q"}) + "\n") * 2)
    with pytest.raises(ValueError, match="duplicate result"):
        rows_by_id(path)


def test_rescore_end_to_end_and_stale_audit_rejection(tmp_path):
    root = tmp_path / "repo"
    data = root / "data/fresh-full"
    data.mkdir(parents=True)
    gold = {
        "id": "q",
        "repo": "org/repo",
        "base_commit": "abc",
        "language": "python",
        "full_text_status": "unchanged",
        "gold_functions": ["a.py::run"],
    }
    (data / "gold.jsonl").write_text(json.dumps(gold) + "\n")
    (data / "manifest.json").write_text(json.dumps({"agent_subsample": ["q"]}))
    inventory = {
        "schema": "symbol-inventory-v1",
        "repo": "org/repo",
        "base_commit": "abc",
        "collection_complete": True,
        "files": [{"path": "a.py", "language": "python", "parser_has_error": False}],
        "symbols": [{"id": "a.py::run", "kind": "function", "start_line": 1, "end_line": 2}],
        "colliding_ids": {},
        "parser_error_files": [],
    }
    directory = root / "inventories"
    directory.mkdir()
    filename = hashlib.sha256(b"org/repo@abc").hexdigest() + ".json.gz"
    payload = gzip.compress(json.dumps(inventory).encode())
    (directory / filename).write_bytes(payload)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "symbol-inventory-v1",
                "instances": [{"id": "q", "repo": "org/repo", "base_commit": "abc"}],
                "source_sha256": {},
                "parser_versions": {},
            }
        )
    )
    (directory / "index.json").write_text(
        json.dumps(
            {
                "schema": "symbol-inventory-v1",
                "failures": [],
                "instances": {
                    "q": {
                        "file": filename,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "files": 1,
                        "symbols": 1,
                        "colliding_ids": 0,
                        "parser_error_files": 0,
                    }
                },
            }
        )
    )
    audit_dir = root / "audit"
    audit(directory, data / "gold.jsonl", audit_dir)
    predictions = root / "results/research/frontier"
    predictions.mkdir(parents=True)
    (predictions / "fresh-full_website.jsonl").write_text(
        json.dumps({"id": "q", "answer": {"functions": [None, {"file": "a.py", "name": "run"}]}})
        + "\n"
    )
    (predictions / "fresh-full-agents_empty.jsonl").write_text("")
    result = run(directory, audit_dir, root / "scored", root)
    scored = result["runs"]["fresh-full_website"]
    assert scored["modes"]["strict_symbol"]["all_observed"]["metrics"]["mrr@10"] == 0.5
    empty = result["runs"]["fresh-full-agents_empty"]
    assert empty["missing_ids"] == ["q"] and empty["observed_instances"] == 0
    assert empty["modes"]["strict_symbol"]["all_observed"]["metrics"] is None
    assert (root / "scored/provenance.json").exists()
    (data / "gold.jsonl").write_text(json.dumps({**gold, "gold_functions": ["a.py::other"]}) + "\n")
    with pytest.raises(ValueError, match="audit input changed"):
        run(directory, audit_dir, root / "stale", root)
