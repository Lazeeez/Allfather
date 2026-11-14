import argparse
import json
import sys

import pytest

from allfather.eval.execution import bind_run, make_plan
from scripts import fresh_website, frontier


def inputs():
    return {
        f"org/project#{i}": {"repo": "org/project", "base_commit": "base", "text": f"report {i}"}
        for i in range(12)
    }


def test_order_is_seeded_not_sorted_and_ignores_gold_outcomes_and_input_order():
    items = inputs()
    ids = list(items)
    plan = make_plan(ids, items, {"model": "example"}, 37, 6)
    changed = {q: {**r, "gold": ["changed"], "hit@10": 1} for q, r in items.items()}
    assert make_plan(ids[::-1], changed, {"model": "example"}, 37, 6) == plan
    assert plan["ids"] != sorted(ids)[:6]
    assert make_plan(ids, items, {}, 38, 6)["ids"] != plan["ids"]


def test_resume_requires_exact_inputs_recipe_and_order(tmp_path):
    items = inputs()
    target = tmp_path / "run.jsonl"
    plan = make_plan(list(items), items, {"model": "example"}, 37, 6)
    identity, done = bind_run(target, plan)
    assert not done
    target.write_text(
        json.dumps({"id": plan["ids"][0], "execution_manifest_sha256": identity}) + "\n"
    )
    assert bind_run(target, plan) == (identity, {plan["ids"][0]})
    for changed in (plan | {"seed": 38}, plan | {"recipe": {"model": "other"}}):
        with pytest.raises(ValueError, match="changed"):
            bind_run(target, changed)
    items[plan["ids"][0]]["text"] += "edited"
    with pytest.raises(ValueError, match="changed"):
        bind_run(target, make_plan(list(items), items, {"model": "example"}, 37, 6))


def test_legacy_or_foreign_records_are_never_silently_adopted(tmp_path):
    items = inputs()
    plan = make_plan(list(items), items, {}, 37)
    legacy = tmp_path / "legacy.jsonl"
    legacy.write_text("")
    with pytest.raises(ValueError, match="historical run"):
        bind_run(legacy, plan)
    target = tmp_path / "new.jsonl"
    identity, _ = bind_run(target, plan)
    target.write_text(json.dumps({"id": "foreign", "execution_manifest_sha256": identity}) + "\n")
    with pytest.raises(ValueError, match="outside"):
        bind_run(target, plan)


def test_duplicate_results_and_negative_limit_fail(tmp_path):
    items = inputs()
    with pytest.raises(ValueError):
        make_plan(list(items), items, {}, 37, -1)
    plan = make_plan(list(items), items, {}, 37)
    target = tmp_path / "run.jsonl"
    identity, _ = bind_run(target, plan)
    line = json.dumps({"id": plan["ids"][0], "execution_manifest_sha256": identity}) + "\n"
    target.write_text(line * 2)
    with pytest.raises(ValueError, match="duplicate"):
        bind_run(target, plan)


def test_frontier_plan_only_never_calls_provider_or_billing_probe(tmp_path, monkeypatch):
    items = inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("provider/model must not be invoked")

    monkeypatch.setattr(frontier, "OUT", tmp_path)
    monkeypatch.setattr(frontier, "load_set", lambda _: (list(items), items))
    monkeypatch.setattr(frontier, "SYSTEMS", {"gemini-single": (forbidden, "example", False)})
    monkeypatch.setattr(frontier, "free_tier_only", forbidden)
    args = argparse.Namespace(
        set="synthetic",
        system="gemini-single",
        model=None,
        tag="new",
        errors_last=False,
        execution_seed=37,
        limit=3,
        plan_only=True,
    )
    assert frontier.cmd_run(args) == 0
    assert len(list(tmp_path.glob("*.execution.json"))) == 1
    assert not list(tmp_path.glob("*.jsonl"))


def test_website_execution_uses_no_gold_and_writes_matching_manifest(tmp_path, monkeypatch):
    items = inputs()
    for item in items.values():
        item["gold"] = object()  # cannot be iterated or JSON serialized
    monkeypatch.setattr(fresh_website, "OUT", tmp_path)
    monkeypatch.setattr(fresh_website, "load_set", lambda _: (list(items), items))
    config = tmp_path / "config.json"
    config.write_text("{}")
    monkeypatch.setattr(fresh_website, "RANKER", config)
    monkeypatch.setattr(fresh_website, "CONFIDENCE", config)
    monkeypatch.setattr(fresh_website, "log_test_run", lambda *a: None)
    calls = []

    class FakeSite:
        sha = "synthetic"
        last_semantic = None

        def rank(self, inst, gold, files):
            assert gold == files == set()
            calls.append(inst.instance_id)
            return [], [], 0

        def close(self):
            pass

    monkeypatch.setattr(fresh_website, "Site", FakeSite)
    monkeypatch.setattr(
        sys, "argv", ["fresh_website.py", "--set", "synthetic", "--tag", "new", "--limit", "3"]
    )
    assert fresh_website.main() == 0
    plan = json.loads((tmp_path / "synthetic_website-new.execution.json").read_bytes())
    assert calls == plan["ids"]
    assert len(calls) == 3
    assert fresh_website.main() == 0  # resume makes no additional ranking calls
    assert len(calls) == 3
