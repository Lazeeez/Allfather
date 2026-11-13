from scripts.audit_research_splits import overlap, repeated_issues


def test_project_overlap_is_case_insensitive_and_distinct_from_issue_overlap():
    reference = [{"qid": "old", "repo": "Org/Repo", "base_commit": "abc"}]
    candidates = [
        {"id": "new", "repo": "org/repo", "base_commit": "abc"},
        {"id": "other", "repo": "else/where", "base_commit": "abc"},
    ]
    result = overlap(candidates, reference)
    assert result["same_id"] == []
    assert result["same_project"] == ["new"]
    assert result["same_snapshot"] == ["new"]
    assert result["projects_absent_from_reference"] == ["else/where"]


def test_missing_commits_do_not_count_as_snapshot_matches():
    row = {"id": "issue", "repo": "org/repo"}
    result = overlap([row], [row])
    assert result["same_id"] == ["issue"]
    assert result["same_snapshot"] == []
    assert result["reference_rows_with_snapshot"] == 0


def test_multiple_prs_for_one_issue_are_retained_and_flagged():
    rows = [
        {"id": "pr1", "repo": "Org/Repo", "issue": 10},
        {"id": "pr2", "repo": "org/repo", "issue": 10},
        {"id": "pr3", "repo": "other/repo", "issue": 10},
        {"id": "pr4", "repo": "other/repo"},
    ]
    assert repeated_issues(rows) == [{"repo": "org/repo", "issue": "10", "ids": ["pr1", "pr2"]}]
