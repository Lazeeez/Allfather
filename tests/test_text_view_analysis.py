import copy
import io
import tarfile

import pytest

from scripts.analyze_text_views import (
    ACTIONS,
    issue_rows,
    read_archive,
    score_substitutions,
    summarize,
    validate_capture,
)
from scripts.text_views import DOC_VIEWS, QUERY_VIEWS, token_hash


def capture_fixture():
    prepared = {
        "pools": {p: [0, 1] for p in ("base", "wide")},
        "query_tokens_full": 2,
        "doc_tokens_full": {"0": 1, "1": 1},
        "queries": {q: {"ids": [1, 2], "sha256": token_hash([1, 2])} for q in QUERY_VIEWS},
        "views": {
            q: {
                str(r): {d: {"ids": [3], "sha256": token_hash([3])} for d in DOC_VIEWS}
                for r in (0, 1)
            }
            for q in QUERY_VIEWS
        },
    }
    action = {
        "read_rows": [0, 1],
        "ranked_rows": [0, 1],
        "raw_scores": [2.0, 1.0],
        "tokens_computed": 100,
        "seconds": 0.1,
    }
    parent = {"id": "repo#1", "universe": [{"row": 0}, {"row": 1}], "actions": {}}
    for pool, depth in (("base", 50), ("wide", 200)):
        parent["actions"][f"{pool}_local"] = {"ranked_rows": [0, 1]}
        parent["actions"][f"{pool}_ce{depth}"] = copy.deepcopy(action)
    record = {
        "id": parent["id"],
        "manifest_sha256": "manifest",
        "prepare_seconds": 1,
        "prepared": copy.deepcopy(prepared),
        "actions": {a: copy.deepcopy(action) for a in ACTIONS},
        "execution_order": list(ACTIONS),
        "parent_parity": {
            p: {"rankings_equal": True, "scores_max_abs_difference": 0.0} for p in ("base", "wide")
        },
    }
    return record, parent, prepared


def test_recomputes_parity_and_does_not_trust_reported_summary():
    record, parent, prepared = capture_fixture()
    assert validate_capture(record, parent, prepared, "manifest") == record["parent_parity"]
    record["actions"]["base_prefix_prefix"]["raw_scores"][0] += 1
    with pytest.raises(ValueError, match="reported parity"):
        validate_capture(record, parent, prepared, "manifest")
    record["parent_parity"]["base"]["scores_max_abs_difference"] = 1
    with pytest.raises(ValueError, match="baseline parity failed"):
        validate_capture(record, parent, prepared, "manifest")


def test_score_substitution_skips_unread_targets_and_keeps_unchanged_scores():
    record, parent, _ = capture_fixture()
    result = score_substitutions(
        record,
        parent,
        [
            {"id": "present", "retrieval_rows": [0]},
            {"id": "unread", "retrieval_rows": [99]},
        ],
    )
    assert len(result) == 6
    assert all(r["id"] == "present" for r in result)
    assert all(
        r["target_score_only_rank"]
        == r["other_candidate_scores_only_rank"]
        == r["baseline_rank"]
        == 1
        for r in result
    )


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("read_rows", [1, 0], "candidate read"),
        ("ranked_rows", [1, 0], "blend"),
        ("raw_scores", [float("nan"), 1], "raw scores"),
        ("tokens_computed", 101, "token budget"),
    ],
)
def test_rejects_action_drift(field, value, message):
    record, parent, prepared = capture_fixture()
    record["actions"]["wide_head_tail_lexical"][field] = value
    with pytest.raises(ValueError, match=message):
        validate_capture(record, parent, prepared, "manifest")


def test_rejects_changed_inputs_and_missing_actions():
    record, parent, prepared = capture_fixture()
    record["prepared"]["queries"]["prefix"]["ids"] = [9, 9]
    with pytest.raises(ValueError, match="token views differ"):
        validate_capture(record, parent, prepared, "manifest")
    record["prepared"] = prepared
    record["actions"].pop("base_head_tail_random")
    with pytest.raises(ValueError, match="missing/unexpected action"):
        validate_capture(record, parent, prepared, "manifest")


@pytest.mark.parametrize(
    "names,message",
    [
        (["../summary.json"], "unsafe"),
        (["fit-text-views-v1/summary.json"] * 2, "duplicate"),
        (["fit-text-views-v1/other.json"], "unexpected"),
        ([], "missing"),
    ],
)
def test_archive_requires_exact_regular_members(tmp_path, names, message):
    archive = tmp_path / "input.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for name in names:
            member = tarfile.TarInfo(name)
            member.size = 2
            handle.addfile(member, io.BytesIO(b"{}"))
    with pytest.raises(ValueError, match=message):
        read_archive(archive, {"summary.json"})


def test_equal_aggregate_hits_still_exposes_rescue_and_harm():
    rows = []
    for i in range(2):
        actions = {}
        for action in ACTIONS:
            hit = i if action == "base_prefix_head_tail" else 1 - i
            actions[action] = {
                k: hit for k in ("hit@1", "hit@5", "hit@10", "recall@10", "all@10", "mrr@10")
            }
            actions[action].update(
                failure="success" if hit else "ranking_miss", tokens_computed=100, seconds=1
            )
        rows.append(
            {
                "id": str(i),
                "repo": "project" + str(i),
                "issue": i,
                "gold_count": 1,
                "modes": {"strict_symbol": actions},
            }
        )
    result = summarize(rows, "strict_symbol")
    view = result["actions"]["base_prefix_head_tail"]
    assert view["hits"] == 1 and view["rescues"] == ["1"] and view["harms"] == ["0"]
    assert result["oracle_hits"] == 2
    assert "project_sign_flip_p" not in view["paired_diagnostic"]["issue_weighted"]
    with pytest.raises(ValueError, match="duplicate underlying"):
        summarize([rows[0], rows[0]], "strict_symbol")


def test_issue_representative_is_frozen_before_outcomes_and_ignores_repo_case():
    rows = [
        {"id": "repo#2356", "repo": "Org/Repo", "issue": 2340, "hit": 1},
        {"id": "repo#2342", "repo": "org/repo", "issue": "2340", "hit": 0},
        {"id": "repo#2430", "repo": "org/repo", "issue": 2429, "hit": 1},
    ]
    assert [r["id"] for r in issue_rows(rows)] == ["repo#2342", "repo#2430"]
    for row in rows:
        row["hit"] = 1 - row["hit"]
    assert [r["id"] for r in issue_rows(rows[::-1])] == ["repo#2342", "repo#2430"]


def test_issue_pr_sensitivity_preserves_related_rows():
    actions = {
        a: {k: 1 for k in ("hit@1", "hit@5", "hit@10", "recall@10", "all@10", "mrr@10")}
        for a in ACTIONS
    }
    for v in actions.values():
        v.update(failure="success", tokens_computed=100, seconds=1)
    row = {
        "id": "repo#2",
        "repo": "org/repo",
        "issue": 1,
        "gold_count": 1,
        "modes": {"strict_symbol": actions},
    }
    related = {**copy.deepcopy(row), "id": "repo#3"}
    for v in related["modes"]["strict_symbol"].values():
        for key in ("hit@1", "hit@5", "hit@10", "recall@10", "all@10", "mrr@10"):
            v[key] = 0
        v["failure"] = "ranking_miss"
    primary = summarize(issue_rows([related, row]), "strict_symbol")
    sensitivity = summarize([related, row], "strict_symbol", allow_related_prs=True)
    assert primary["rows"] == 1 and primary["actions"]["base_prefix_prefix"]["hits"] == 1
    assert sensitivity["rows"] == 2 and sensitivity["actions"]["base_prefix_prefix"]["hits"] == 1


def test_validation_archive_cannot_be_read_as_fit(tmp_path):
    archive = tmp_path / "validation.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        member = tarfile.TarInfo("validation-text-views-v1/summary.json")
        member.size = 2
        handle.addfile(member, io.BytesIO(b"{}"))
    assert read_archive(archive, {"summary.json"}, "validation-text-views-v1") == {
        "summary.json": b"{}"
    }
    with pytest.raises(ValueError, match="unsafe archive path"):
        read_archive(archive, {"summary.json"})
