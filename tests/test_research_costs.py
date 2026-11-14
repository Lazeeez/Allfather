import pytest

from allfather.eval.costs import Cost, record_cost, selected_costs, summarize
from scripts import fresh_analysis, paper_tables


@pytest.mark.parametrize("value", [None, -1, float("nan"), float("inf"), True, "1.0"])
def test_missing_or_invalid_cost_is_not_free(value):
    cost = record_cost({"cost_usd": value})
    assert cost.usd is None and cost.state == "unknown"


def test_local_placeholder_and_unattributed_tokens_are_unknown():
    assert record_cost({"system": "website-gpu", "cost_usd": 0}).usd is None
    assert record_cost({"system": "codex-agent", "usage": {"input_tokens": 1_000_000}}).usd is None
    assert record_cost({"system": "open-agent", "usage": {"gpu_seconds": 40}}).usd is None
    assert record_cost({"system": "claude-single", "cost_usd": 0}).usd == 0


def test_explicit_estimate_keeps_basis_and_scope_and_rejects_invalid_states():
    explicit = {
        "schema": "run-cost-v1",
        "state": "estimated",
        "usd": 2,
        "basis": "synthetic test estimate",
        "scope": "run_charge",
    }
    assert record_cost({"cost_accounting": explicit}).state == "estimated"
    with pytest.raises(ValueError):
        record_cost({"cost_accounting": {**explicit, "basis": ""}})
    with pytest.raises(ValueError):
        record_cost({"cost_accounting": {**explicit, "state": "unknown"}})


def test_incomplete_mean_and_mixed_scopes_cannot_be_reported_as_complete():
    known = Cost(4, "recorded", "test", "run_charge")
    unknown = Cost(None, "unknown", "missing", "run_charge")
    result = summarize([known, unknown])
    assert result["mean_usd"] is None and result["known_subtotal_usd"] == 4
    assert result["states"] == {"recorded": 1, "unknown": 1}
    assert summarize([known, Cost(1, "estimated", "test", "total_compute")])["mean_usd"] is None
    assert summarize([])["mean_usd"] is None


def test_cascade_ignores_unselected_unknown_agent_cost_but_requires_selected_cost():
    ref = {"a": {"cost": 1}, "b": {"cost": 1}}
    other = {"a": {"cost": 10}, "b": {"cost": None}}
    selected = selected_costs(ref, other, ["a", "b"], [True, False])
    assert selected["mean_usd"] == 6 and selected["selected_ids"] == ["a"]
    assert selected_costs(ref, other, ["a", "b"], [False, True])["mean_usd"] is None
    with pytest.raises(ValueError):
        selected_costs(ref, other, ["a", "a"], [True, False])


def test_analysis_and_paper_use_identical_paired_costs(monkeypatch):
    items = {q: {"gold": ["file.py::f"]} for q in ("a", "b", "unpaired")}
    reference = [
        {"id": "a", "cost_usd": 1, "confidence": 0.1},
        {"id": "b", "cost_usd": 1, "confidence": 0.9},
        {"id": "unpaired", "cost_usd": 100, "confidence": 0.1},
    ]
    agent = [{"id": "a", "cost_usd": 10}, {"id": "b", "cost_usd": 100}]
    monkeypatch.setattr(paper_tables, "load_set", lambda _: (None, items))
    monkeypatch.setattr(
        paper_tables, "rows", lambda _, system: reference if system == "ref" else agent
    )
    paper = paper_tables.cascade_cost("example", "ref", "agent", 0.5)
    ref = fresh_analysis.per_issue(reference, items)
    other = fresh_analysis.per_issue(agent, items)
    analysis = fresh_analysis.escalation(ref, other, ["a", "b"], 0.5)["chosen"]
    assert paper == analysis["cost_accounting"]
    assert paper["mean_usd"] == analysis["cost"] == 6
    assert paper_tables.cost_per_bug("example", "agent") == 55
    assert paper_tables.median_seconds("example", "agent") is None


def test_analysis_preserves_missing_cost_and_time_and_rejects_duplicate_ids():
    items = {"a": {"gold": ["f.py::f"]}}
    row = {"id": "a", "cost_usd": None, "seconds": None}
    result = fresh_analysis.per_issue([row], items)["a"]
    assert result["cost"] is None and result["seconds"] is None
    with pytest.raises(ValueError, match="duplicate result"):
        fresh_analysis.per_issue([row, row], items)


def test_cost_frontiers_do_not_compare_different_issues_or_scopes():
    runs = {"a": {"one": {}}, "b": {"two": {}}, "c": {"one": {}}, "d": {"one": {}}}
    systems = {
        s: {"cost_usd": 1, "hit@10": 1, "cost_accounting": {"scopes": ["run_charge"]}} for s in runs
    }
    systems["c"]["cost_accounting"]["scopes"] = ["total_compute"]
    systems["d"]["cost_usd"] = None
    frontiers = fresh_analysis.cost_frontiers(runs, systems)
    assert len(frontiers) == 3
    assert all(len(f["eligible_systems"]) == 1 for f in frontiers)


def test_missing_confidence_is_not_silently_replaced_by_zero():
    with pytest.raises(ValueError, match="observed confidence"):
        fresh_analysis.escalation({"a": {"confidence": None}}, {"a": {}}, ["a"], 0.5)
