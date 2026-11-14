import copy
import json

import pytest

from scripts.sample_task_audit import reviewer_files, sampling_frame


def records():
    return [
        {
            "id": f"{repo}#{i}",
            "repo": repo,
            "issue": i,
            "base_commit": "abc",
            "project_language": "python",
            "full_text_status": "unchanged",
            "text": f"Issue {i}",
        }
        for repo, n in (("Org/Large", 7), ("Org/Small", 1), ("Org/Excluded", 2))
        for i in range(n)
    ]


def test_selection_ignores_outcomes_labels_and_input_order():
    rows = records()
    before = sampling_frame(rows, {"org/excluded"})
    altered = [
        {**r, "gold_functions": ["different"], "hit@10": 1, "failure": "changed"}
        for r in reversed(rows)
    ]
    assert sampling_frame(altered, {"ORG/EXCLUDED"}) == before
    assert before["counts"]["selected_issues"] == 3
    assert before["counts"]["waves"] == {"1": 2, "2": 1}
    assert {r["project_key"] for r in before["instances"]} == {"org/large", "org/small"}
    assert next(r for r in before["instances"] if r["repo"] == "Org/Large")[
        "nominal_inclusion"
    ] == {"numerator": 2, "denominator": 7}


def test_related_prs_are_one_issue_with_outcome_independent_representative():
    rows = records()
    extra = {**rows[-1], "id": "Org/Excluded#other", "repo": "ORG/EXCLUDED"}
    plan = sampling_frame([*rows, extra], set())
    group = next(
        r for r in plan["instances"] if r["project_key"] == "org/excluded" and r["issue"] == 1
    )
    assert group["id"] == "Org/Excluded#1"
    assert group["related_pr_ids"] == ["Org/Excluded#1", "Org/Excluded#other"]
    assert plan["counts"]["eligible_issues"] == len(rows)


def test_duplicate_ids_and_mixed_project_languages_fail_closed():
    rows = records()
    with pytest.raises(ValueError, match="duplicate row"):
        sampling_frame([*rows, rows[0]], set())
    rows[0]["project_language"] = "go"
    with pytest.raises(ValueError, match="project language"):
        sampling_frame(rows, set())


def test_changed_reports_are_excluded_before_issue_selection():
    rows = records()
    rows[0]["full_text_status"] = "changed"
    plan = sampling_frame(rows, {"org/excluded"})
    assert plan["exclusions"] == {"changed_report_rows": 1, "development_project_rows": 2}
    assert plan["frame"]["org/large"]["eligible_issues"] == 6
    assert all(r["id"] != rows[0]["id"] for r in plan["instances"])


def test_packet_contains_only_original_report_fields_and_blank_review_sheets():
    rows = records()
    plan = sampling_frame(rows, {"org/excluded"})
    altered = [
        {**r, "gold_functions": ["SECRET_GOLD"], "predictions": ["SECRET_OUTPUT"]} for r in rows
    ]
    files = reviewer_files(plan, altered, b"rubric")
    for wave in (1, 2):
        for line in files[f"wave-{wave}/reports.jsonl"].splitlines():
            assert set(json.loads(line)) == {"case", "repo", "base_commit", "text_sha256", "text"}
    assert all(b"SECRET_" not in value for value in files.values())
    changed = copy.deepcopy(rows)
    changed[0]["text"] += "changed"
    chosen = next(r for r in plan["instances"])
    next(r for r in changed if r["id"] == chosen["id"])["text"] = "modified"
    with pytest.raises(ValueError, match="report changed"):
        reviewer_files(plan, changed, b"rubric")
