import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import frontier  # noqa: E402


def setup(tmp_path: Path, monkeypatch, answered: list[str]) -> Path:
    monkeypatch.setattr(frontier, "OUT", tmp_path)
    monkeypatch.setattr(frontier, "load_set", lambda name: (["a", "b", "c"], {}))
    with (tmp_path / "fresh-agents_sys.jsonl").open("w", encoding="utf-8") as f:
        for q in answered:
            f.write(json.dumps({"id": q, "answer": {"functions": []}}) + "\n")
    return tmp_path / "fresh_sys.jsonl"


def test_reuses_every_subsample_answer_once(tmp_path, monkeypatch):
    target = setup(tmp_path, monkeypatch, ["a", "b", "c"])
    assert frontier.reuse_subsample("fresh", "sys", target, {"b"}) == {"a", "c"}
    rows = [json.loads(line) for line in target.open(encoding="utf-8")]
    assert [r["id"] for r in rows] == ["a", "c"]
    assert all(r["reused_from"] == "fresh-agents_sys.jsonl" for r in rows)
    assert frontier.reuse_subsample("fresh", "sys", target, {"a", "b", "c"}) == set()


def test_refuses_an_unfinished_subsample(tmp_path, monkeypatch):
    target = setup(tmp_path, monkeypatch, ["a"])
    with pytest.raises(SystemExit):
        frontier.reuse_subsample("fresh", "sys", target, set())
    assert not target.exists()


def test_only_the_full_set_reuses(tmp_path, monkeypatch):
    target = setup(tmp_path, monkeypatch, ["a", "b", "c"])
    assert frontier.reuse_subsample("fresh-agents", "sys", target, set()) == set()
    assert frontier.reuse_subsample("fresh", "other", target, set()) == set()


def test_repeat_set_is_a_fixed_subset_of_the_agent_bugs():
    agents, _ = frontier.load_set("fresh-agents")
    first, _ = frontier.load_set("fresh-repeat50")
    again, _ = frontier.load_set("fresh-repeat50")
    assert len(first) == 50 and first == again and set(first) <= set(agents)
