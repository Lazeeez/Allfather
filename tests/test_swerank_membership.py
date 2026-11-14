import json

import pytest

from scripts import audit_swerank_membership as membership
from scripts.correct_swerank import recover


def test_streamed_membership_distinguishes_duplicates_and_absence(tmp_path):
    path = tmp_path / "corpus.jsonl"
    raw = b'{"_id":"a.py/f","text":"x"}\n{"_id":"a.py/f","text":"y"}\n{"_id":"a.py/g","text":"z"}\n'
    path.write_bytes(raw)
    result = membership.scan_corpus(path, {"a.py/f", "a.py/g", "missing"})
    assert result["requested_counts"] == {"a.py/f": 2, "a.py/g": 1, "missing": 0}
    assert result["colliding_ids"] == 1
    assert result["sha256"] == membership.digest(raw)
    path.write_text('{"text":"no ID"}\n')
    with pytest.raises(ValueError, match="document ID"):
        membership.scan_corpus(path, set())


@pytest.mark.parametrize("missing", [False, True])
def test_end_to_end_audit_preserves_all_slots_and_missing_corpora(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(membership, "ROOT", tmp_path)
    short, full, corrections = (tmp_path / name for name in ("short", "full", "corrections"))
    q, run = "org/project#1", "fresh-full_swerank-embed-small"
    for root in (short, full):
        (root / "folder").mkdir(parents=True)
        (root / "index.json").write_text(json.dumps({"folder": q}))
        if not missing:
            (root / "folder/corpus.jsonl").write_text(
                "".join(
                    json.dumps({"_id": s}) + "\n"
                    for s in ("a.mjs/Thing/run", "a.mjs/Thing/run", "a.py/f")
                )
            )
    original = [
        {
            "id": q,
            "answer": {
                "functions": [
                    {"file": "a.mjs/Thing/run", "name": ""},
                    {"file": "a.py", "name": "f"},
                    {"file": "a.py", "name": "g"},
                ]
            },
        }
    ]
    corrected, changes = recover(original)
    source = tmp_path / "results/research/frontier" / (run + ".jsonl")
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(original[0]) + "\n")
    corrections.mkdir()
    (corrections / (run + ".jsonl")).write_text(json.dumps(corrected[0]) + "\n")
    (corrections / "audit.json").write_text(
        json.dumps(
            {
                "runs": {run: {"set": "fresh-full", "expected_instances": 1, "changes": changes}},
                "inputs_sha256": {
                    source.relative_to(tmp_path).as_posix(): membership.digest(source.read_bytes())
                },
            }
        )
    )
    for name in ("audit_swerank_membership", "correct_swerank", "swerank_import", "swerank_export"):
        path = tmp_path / "scripts" / (name + ".py")
        path.parent.mkdir(exist_ok=True)
        path.write_text("# synthetic source fingerprint fixture\n")
    out = tmp_path / "audit"
    result = membership.audit(short, full, corrections, out)
    assert result["integrity_ok"] is not missing
    summary = result["runs"][run]
    assert summary["slots"] == 3 and summary["issues"] == 1
    if missing:
        assert summary["unavailable"] == 3 and summary["recovered_unavailable"] == 1
        assert not result["all_recovered_present"]
    else:
        assert summary["unique"] == summary["ambiguous"] == summary["missing"] == 1
        assert summary["recovered_ambiguous"] == 1
        assert result["all_recovered_present"] and not result["all_predictions_present"]
    # The exact saved correction is required, not merely plausible identifiers.
    (corrections / (run + ".jsonl")).write_text(json.dumps({**corrected[0], "extra": True}) + "\n")
    with pytest.raises(ValueError, match="cannot be reproduced"):
        membership.audit(short, full, corrections, tmp_path / "second")


def test_export_index_rejects_path_traversal_and_duplicate_issue_mapping(tmp_path):
    index = tmp_path / "index.json"
    for bad in ({"../escape": "q"}, {"one": "q", "two": "q"}):
        index.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            membership.corpus_index(tmp_path)
