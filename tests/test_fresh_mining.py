import hashlib

import pytest

from allfather.eval.ground_truth import GoldEntry
from scripts import fresh_set as mining


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"data": None},
        {"data": {"repository": None}},
        {"data": {"repository": {"issue": None}}},
        {"data": {"repository": {"issue": {}}}},
    ],
)
def test_absent_edit_history_is_not_no_edit(payload):
    with pytest.raises(ValueError):
        mining.checked_last_edit(payload)


def payload(value):
    return {"data": {"repository": {"issue": {"lastEditedAt": value}}}}


def test_null_is_valid_only_with_complete_success_response():
    assert mining.checked_last_edit(payload(None)) is None
    assert mining.checked_last_edit(payload("2026-11-15T10:20:30Z")) == "2026-11-15T10:20:30Z"
    with pytest.raises(ValueError, match="returned errors"):
        mining.checked_last_edit({**payload(None), "errors": [{"message": "partial data"}]})
    with pytest.raises(mining.RateLimited):
        mining.checked_last_edit({"errors": [{"type": "RATE_LIMITED"}]})


@pytest.mark.parametrize("value", [False, 1, "", "invalid", "2026-11-15", "2026-11-15T10:20:30"])
def test_edit_timestamp_must_be_valid_and_timezone_aware(value):
    with pytest.raises(ValueError):
        mining.checked_last_edit(payload(value))


@pytest.mark.parametrize("errors", [[], ["src/missing.py: blob unavailable"]])
def test_mining_preserves_extraction_evidence_and_rejects_partial_gold(monkeypatch, errors):
    patch = "a pinned diff\n"
    issue = {"title": "Broken behavior", "body": "Steps", "created_at": "2026-11-01T00:00:00Z"}
    pr = {"merge_commit_sha": "merge", "merged_at": "2026-11-03T00:00:00Z"}
    responses = {
        "/repos/a/b/issues/1": issue,
        "/repos/a/b/pulls/2": pr,
        "/repos/a/b/commits/merge": {"parents": [{"sha": "base"}, {"sha": "head"}]},
        "/repos/a/b/compare/base...merge": patch,
    }
    monkeypatch.setattr(mining, "github", lambda path, **kw: responses[path])
    monkeypatch.setattr(mining, "last_body_edit", lambda *a: None)
    gold = GoldEntry(
        "a/b#2", "a/b", "base", files=["src/a.py"], functions=["src/a.py::f"], errors=errors
    )
    monkeypatch.setattr(mining, "gold_for_instance", lambda *a: gold)
    result = mining.mined(
        "a/b",
        1,
        {"number": 2, "created_at": "2026-11-02T00:00:00Z"},
        "2026-11-01",
        None,
        frozenset({"python"}),
    )
    assert result["gold_extraction"]["errors"] == errors
    assert result["provenance"]["merge_parents"] == ["base", "head"]
    assert result["provenance"]["patch_text_sha256"] == hashlib.sha256(patch.encode()).hexdigest()
    assert bool(result.get("skipped")) == bool(errors)
    assert result["gold_functions"] == [
        "src/a.py::f"
    ]  # retain partial evidence, never silently repair
