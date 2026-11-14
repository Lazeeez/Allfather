import copy
import hashlib
import io
import tarfile

import pytest

from scripts.analyze_development_replay import (
    ACTIONS,
    diagnose,
    score_rows,
    summaries,
    verify_transfer,
)


def test_scoring_keeps_duplicate_and_ambiguous_slots_and_truncates_mrr():
    universe = [{"id": "a::duplicate"}] * 10 + [{"id": "a::target"}]
    result = score_rows(list(range(11)), universe, {"a::target"}, {"a::target"})
    assert result["hit@10"] == result["mrr@10"] == 0
    result = score_rows([0, 1, 10], universe, {"a::target"}, {"a::target"})
    assert result["mrr@10"] == 1 / 3
    universe = [{"id": "a::ambiguous"}, {"id": "a::target"}, {"id": "a::target"}]
    result = score_rows([0, 1, 2], universe, {"a::ambiguous", "a::target"}, {"a::target"})
    assert result["mrr@10"] == result["recall@10"] == 0.5
    assert result["all@10"] == 0


def fixture_diagnosis():
    gold = {
        "id": "q",
        "repo": "org/repo",
        "base_commit": "abc",
        "text": "report",
        "issue": 1,
        "gold_functions": ["a::target"],
    }
    item = {**gold, "split": "fit", "language": "python"}
    audited = {
        **gold,
        "gold_in_parser_error_files": 0,
        "gold": [{"id": "a::target", "status": "unique", "file_has_parser_error": False}],
    }
    trace = {
        **gold,
        "text_sha256": hashlib.sha256(b"report").hexdigest(),
        "universe": [{"id": f"a::other{i}", "row": i} for i in range(11)]
        + [{"id": "a::target", "row": 11}],
        "snapshot_prepare_seconds": 1,
        "shared_signals_seconds": 1,
        "total_seconds": 10,
        "pools": {},
        "actions": {},
    }
    for label, n in (("base", 11), ("wide", 12)):
        trace["pools"][label] = {"rows": list(range(n)), "minilm_rows": list(range(n))}
        for stage in ("local", "ce50", "ce200"):
            value = {"ranked_rows": list(range(n)), "seconds": 1}
            if stage != "local":
                value.update(
                    read_rows=list(range(10 if stage == "ce50" else n)), tokens_computed=10
                )
            trace["actions"][f"{label}_{stage}"] = value
    return trace, gold, audited, item


def test_diagnosis_separates_candidate_read_and_ranking_misses():
    trace, gold, audited, item = fixture_diagnosis()
    row = diagnose(trace, gold, audited, item)
    actions = row["modes"]["strict_symbol"]["actions"]
    assert actions["base_local"]["failure"] == "candidate_miss"
    assert actions["wide_local"]["failure"] == "ranking_miss"
    assert actions["wide_ce50"]["failure"] == "read_prefix_miss"
    assert actions["wide_ce200"]["failure"] == "ranking_miss"
    trace["actions"]["wide_ce200"]["ranked_rows"] = [11, *range(11)]
    assert (
        diagnose(trace, gold, audited, item)["modes"]["strict_symbol"]["actions"]["wide_ce200"][
            "failure"
        ]
        == "success"
    )


def test_identity_uses_complete_audit_not_filtered_universe():
    trace, gold, audited, item = fixture_diagnosis()
    audited["gold"][0]["status"] = "ambiguous"
    trace["actions"]["wide_ce200"]["ranked_rows"] = [11, *range(11)]
    row = diagnose(trace, gold, audited, item)
    strict = row["modes"]["strict_symbol"]["actions"]["wide_ce200"]
    grouped = row["modes"]["name_group"]["actions"]["wide_ce200"]
    assert strict["failure"] == "identity_unresolved" and strict["hit@10"] == 0
    assert grouped["hit@10"] == 1
    audited["gold"][0]["status"] = "unique"
    trace["universe"][11]["id"] = "a::something_else"
    row = diagnose(trace, gold, audited, item)
    assert row["modes"]["strict_symbol"]["actions"]["wide_ce200"]["failure"] == "universe_miss"


def test_duplicate_issue_sensitivity_is_outcome_independent():
    row = diagnose(*fixture_diagnosis())
    row["id"] = "z-pr"
    earlier = copy.deepcopy(row)
    earlier["id"] = "a-pr"
    for mode in earlier["modes"].values():
        for action in ACTIONS:
            mode["actions"][action]["hit@10"] = 1
    summary = summaries([row, earlier])
    assert summary["all/issue_pr/strict_symbol"]["rows"] == 2
    assert summary["all/issue_deduplicated/strict_symbol"]["ids"] == ["a-pr"]
    assert summary["all/issue_deduplicated/strict_symbol"]["actions"]["base_local"]["hits"] == 1


def test_archive_verification_rejects_changed_files_and_path_escape(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "file.json").write_bytes(b"original")
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(bundle / "file.json", arcname="file.json")
    assert verify_transfer(bundle, archive)["original_bundle_files_sha256"] == {
        "file.json": hashlib.sha256(b"original").hexdigest()
    }
    (bundle / "file.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="extracted file differs"):
        verify_transfer(bundle, archive)
    unsafe = tmp_path / "unsafe.tar.gz"
    with tarfile.open(unsafe, "w:gz") as handle:
        member = tarfile.TarInfo("../escape.json")
        member.size = 1
        handle.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(ValueError, match="unsafe archive path"):
        verify_transfer(bundle, unsafe)
