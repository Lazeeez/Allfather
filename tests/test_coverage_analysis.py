import copy
import random

import pytest

from scripts.analyze_coverage_probe import ACTIONS, coverage, summarize, validate_capture
from scripts.coverage_probe import fuse, inject, query_fields


def fixture():
    parent = {
        "id": "repo#1",
        "repo": "repo",
        "base_commit": "abc",
        "text_sha256": "text",
        "universe": [{"id": f"a.py::{n}"} for n in range(80)],
        "actions": {f"{p}_local": {"ranked_rows": list(range(60))} for p in ("base", "wide")},
        "pools": {"base": {"rows": list(range(60))}},
    }
    orders = {name: [75, 3, 2, 1] for name in ("full", "title", "code", "quoted")}
    rrf, refs = fuse(list(orders.values())), [79, 78]
    record = {
        **{k: parent[k] for k in ("id", "repo", "base_commit", "text_sha256")},
        "universe_units": 80,
        "query_fields": query_fields("query"),
        "lexical_feature_parity": {
            f"{p}/{f}/{v}": 0
            for p in ("base", "wide")
            for f in ("full", "title", "code")
            for v in ("rel", "logrank")
        },
        "field_orders_top1000": orders,
        "rrf_order": rrf,
        "reference_order": refs,
        "actions": {},
    }
    shuffled = list(range(80))
    random.Random("37:repo#1").shuffle(shuffled)
    base = list(range(60))
    for k in (50, 200):
        for name, rows in {
            "base": base[:k],
            "wide": base[:k],
            "bm25_full": orders["full"][:k],
            "field_rrf": rrf[:k],
            "inject_rrf": inject(base, rrf, k),
            "inject_refs": inject(base, refs, k),
            "inject_random": inject(base, shuffled, k),
        }.items():
            record["actions"][f"{name}_{k}"] = {
                "rows": rows,
                "added_vs_base_read": sorted(set(rows) - set(base[:k])),
                "removed_vs_base_read": sorted(set(base[:k]) - set(rows)),
                "outside_base_pool": sorted(set(rows) - set(base)),
            }
    return parent, record


def test_verification_rebuilds_action_choices_and_rejects_drift():
    parent, record = fixture()
    validate_capture(record, parent, "query")
    record["actions"]["inject_refs_50"]["rows"][0] = 78
    with pytest.raises(ValueError, match="selection changed"):
        validate_capture(record, parent, "query")


@pytest.mark.parametrize("value", [float("nan"), -1.0, 1e-4])
def test_verification_rejects_invalid_lexical_parity(value):
    parent, record = fixture()
    record["lexical_feature_parity"]["base/full/rel"] = value
    with pytest.raises(ValueError, match="parity failed"):
        validate_capture(record, parent, "query")


def test_coverage_counts_unique_targets_and_keeps_unretrieved_denominator():
    units = [{"id": "A"}, {"id": "A"}, {"id": "B"}]
    result = coverage([0, 1], units, {"A", "B", "missing"})
    assert result == {"read_units": 2, "found": ["A"], "any": 1, "all": 0, "recall": 1 / 3}
    with pytest.raises(ValueError, match="duplicate"):
        coverage([0, 0], units, {"A"})


def test_followup_gate_requires_multi_project_gains_and_no_issue_losses():
    rows = [
        {
            "id": f"{repo}#{i}",
            "repo": repo,
            "actions": {name: coverage([], [{"id": "A"}], {"A"}) for name in ACTIONS},
        }
        for i, repo in enumerate(("a", "a", "b"))
    ]
    for row in rows:
        row["actions"]["inject_refs_50"] = coverage([0], [{"id": "A"}], {"A"})
    assert summarize(rows)["inject_refs_50"]["passes_necessary_followup_gate"]
    assert not summarize(rows[:2])["inject_refs_50"]["passes_necessary_followup_gate"]
    harm = copy.deepcopy(rows[0])
    harm["id"] = "a#harm"
    harm["actions"]["base_50"], harm["actions"]["inject_refs_50"] = (
        harm["actions"]["inject_refs_50"],
        harm["actions"]["base_50"],
    )
    assert not summarize([*rows, harm])["inject_refs_50"]["passes_necessary_followup_gate"]
