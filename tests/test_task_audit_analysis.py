import copy

import pytest

from allfather.index.snapshot import unit_key, unit_text
from scripts.analyze_task_audit import ACTIONS, summarize, verify_annotation


def fixture():
    uid = "a.py::f"
    context = {"id": uid, "text": "def f():\n    return 1"}
    parent = {
        "id": "repo#1",
        "universe": [{"id": uid, "text_key": unit_key(unit_text("f", context["text"])).hex()}],
    }
    capture = {
        "id": "repo#1",
        "gold_functions": [uid],
        "changes": [{"path": "a.py", "patch_sha256": "patch", "gold_base_context": [context]}],
    }
    annotation = {
        "id": "repo#1",
        "alignment": "direct",
        "targets": [
            {
                "id": uid,
                "role": "behavioral",
                "reason": "Changes return value",
                "patch_sha256": "patch",
            }
        ],
    }
    return annotation, capture, parent


def test_frozen_target_context_matches_original_retrieval_content():
    annotation, capture, parent = fixture()
    verify_annotation(annotation, capture, parent)
    capture["changes"][0]["gold_base_context"][0]["text"] += "\n# changed"
    with pytest.raises(ValueError, match="base target differs"):
        verify_annotation(annotation, capture, parent)


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("remove", "incomplete target"),
        ("duplicate", "duplicate annotated"),
        ("role", "invalid target role"),
        ("evidence", "evidence changed"),
    ],
)
def test_annotation_drift_is_rejected(mutation, message):
    annotation, capture, parent = fixture()
    if mutation == "remove":
        annotation["targets"] = []
    elif mutation == "duplicate":
        annotation["targets"].append(copy.deepcopy(annotation["targets"][0]))
    elif mutation == "role":
        annotation["targets"][0]["role"] = "correct"
    else:
        annotation["targets"][0]["patch_sha256"] = "other patch"
    with pytest.raises(ValueError, match=message):
        verify_annotation(annotation, capture, parent)


def test_unclear_and_incidental_only_cases_stay_in_original_denominators():
    rows = [
        {
            "id": "repo#1",
            "repo": "repo",
            "task_kind": "feature",
            "alignment": "unclear",
            "actions": {a: {"hit@10": 1, "incidental_only_hit": True} for a in ACTIONS},
        },
        {
            "id": "repo#2",
            "repo": "repo",
            "task_kind": "bug",
            "alignment": "direct",
            "actions": {a: {"hit@10": 0, "incidental_only_hit": False} for a in ACTIONS},
        },
    ]
    result = summarize(rows)
    assert result["all"]["issues"] == 2
    assert result["all"]["original_hit_at_10"]["base_local"] == 1
    assert result["all"]["incidental_only_hits"]["base_local"] == ["repo#1"]
    assert result["alignment/unclear"]["issues"] == 1
