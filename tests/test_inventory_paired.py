import numpy as np
import pytest

from scripts.analyze_inventory_scores import cluster_p, paired_clusters, select_ids


def test_projects_are_the_resampling_unit_and_estimands_differ():
    # Duplicating one project's wins changes micro weights, not its macro contribution.
    r = paired_clusters([0, 0, 0, 1], [1, 1, 1, 0], ["a", "a", "a", "b"], draws=1000)
    assert r["issue_weighted"]["delta_b_minus_a"] == 0.5
    assert r["project_weighted"]["delta_b_minus_a"] == 0
    assert r["issue_weighted"]["project_bootstrap_ci95"] == [-1, 1]
    assert r["b_rescues_a"] == 3 and r["b_harms_a"] == 1
    assert r["issue_weighted"]["project_sign_flip_p"] == 1


def test_no_difference_and_small_exact_project_sign_flip():
    assert cluster_p(np.array([0, 0]), 10, 0) == 1
    assert cluster_p(np.array([1, 1, 1]), 10, 0) == 0.25
    r = paired_clusters([1, 0], [1, 0], ["a", "b"], draws=10)
    assert r["project_weighted"]["project_bootstrap_ci95"] == [0, 0]
    with pytest.raises(ValueError):
        paired_clusters([], [], [])


def test_issue_deduplication_uses_identity_not_outcomes():
    gold = {
        "pr2": {"repo": "Org/Repo", "issue": 5},
        "pr1": {"repo": "org/repo", "issue": 5},
        "pr3": {"repo": "other/repo", "issue": 5},
    }
    assert select_ids(list(gold), "issue_deduplicated", {}, gold) == ["pr1", "pr3"]
