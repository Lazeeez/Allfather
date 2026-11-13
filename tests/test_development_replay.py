from collections import Counter
from types import SimpleNamespace

import numpy as np
import pytest

from allfather.index.chunker import MODULE, chunk_file
from allfather.index.snapshot import SnapshotIndexer, unit_key, unit_text
from allfather.rank.browser import POOL, extract
from allfather.rank.mentions import Mentions
from allfather.search.retriever import Query
from scripts import development_replay as replay
from scripts.prepare_development_pilot import plan


def test_source_lookup_keeps_distinct_same_name_definitions_and_cache():
    source = b"if condition:\n    def run():\n        return 1\nelse:\n    def run():\n        return 2\n"
    chunks = [c for c in chunk_file(source, "a.py") if c.kind != MODULE]
    texts = [unit_text(c.qualname, c.text) for c in chunks]
    assert len(texts) == 2 and chunks[0].qualname == chunks[1].qualname
    reads = []

    def read(oid):
        reads.append(oid)
        return source

    indexer = SimpleNamespace(
        _reader=SimpleNamespace(read=read), _python_only=lambda: False, _text_cache={}
    )
    index = SimpleNamespace(
        oids=["blob"],
        file_of_doc=[0, 0],
        files=["a.py"],
        ids=["a.py::run"] * 2,
        unit_keys=list(map(unit_key, texts)),
    )
    assert SnapshotIndexer.unit_texts(indexer, index, [1, 0]) == [texts[1], texts[0]]
    assert SnapshotIndexer.unit_texts(indexer, index, [0, 1]) == texts
    assert reads == ["blob"]
    index.unit_keys[0] = b"wrong"
    with pytest.raises(KeyError):
        SnapshotIndexer.unit_texts(indexer, index, [0])


def fake_snapshot(n=240):
    return SimpleNamespace(
        ids=[f"f{i}.py::run" for i in range(n)],
        files=[f"f{i}.py" for i in range(n)],
        file_of_doc=np.arange(n),
        index=SimpleNamespace(lengths=np.ones(n)),
        unit_keys=[bytes(str(i), "ascii") for i in range(n)],
        oids=[str(i) for i in range(n)],
    )


def test_default_pool_unchanged_and_expansion_contains_it():
    fn = fake_snapshot()
    signal = np.arange(len(fn.ids), dtype=float)
    args = (
        fn,
        signal,
        signal,
        signal,
        Mentions.parse("unrelated"),
        Counter(run=len(fn.ids)),
        signal,
        signal,
    )
    a, x = extract(*args)
    b, y = extract(*args, budgets=dict(POOL))
    wide, wx = extract(*args, budgets={k: v * 4 for k, v in POOL.items()})
    np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(x, y)
    assert set(a) < set(wide)
    lookup = {row: i for i, row in enumerate(wide)}
    np.testing.assert_array_equal(x, wx[[lookup[row] for row in a]])


def test_pilot_selection_ignores_labels_and_groups_related_prs():
    rows = [
        {
            "id": f"r{p}#{i}",
            "repo": f"org/r{p}",
            "issue": i,
            "base_commit": "abc",
            "project_language": "python",
            "full_text_status": "unchanged",
            "text": "report",
            "gold_functions": ["answer"],
        }
        for p in range(4)
        for i in range(2)
    ]
    rows.append({**rows[0], "id": "r0#extra-pr"})
    a = plan(rows)
    b = plan([{**r, "gold_functions": ["different"]} for r in rows])
    assert a == b
    picked = {r["id"]: r for r in a["instances"]}
    assert picked["r0#0"]["split"] == picked["r0#extra-pr"]["split"]
    assert len(a["projects"]) == 4 and len(a["instances"]) == 9


def test_capture_runs_all_actions_and_preserves_row_identity(monkeypatch):
    fn = fake_snapshot(3)
    fn.ids = ["a.py::overload", "a.py::overload", "b.py::third"]
    signal = np.array([1.0, 2.0, 3.0])
    requested = []

    def texts(index, rows):
        requested.extend(rows)
        return [f"distinct-row-{r}" for r in rows]

    snaps = SimpleNamespace(
        get=lambda *_: (fn, None, Counter(overload=2, third=1)),
        signals=lambda *_: (
            signal,
            signal,
            signal,
            signal,
            signal,
            Mentions.parse("report"),
            "report",
        ),
        r=SimpleNamespace(indexer=SimpleNamespace(unit_texts=texts)),
    )

    def pass2(items, scores, *_):
        for item in items:
            item.sel = np.arange(len(item.rows_b))
            item.xc = item.xb.copy()

    monkeypatch.setattr(replay.bl, "pass2", pass2)
    ce = SimpleNamespace(tokens_computed=0)

    def score(query, texts):
        ce.tokens_computed += len(texts)
        return np.arange(len(texts), dtype=float)

    ce.score = score
    model = {"semantic": {"trees": [{"v": [0]}]}, "rerank": {"trees": [{"v": [0]}]}}
    trace = replay.capture(
        Query("q", "org/repo", "abc", "report"), snaps, None, model, ce, lambda: None
    )
    assert len(trace["actions"]) == 6
    assert len(trace["universe"]) == 3 and set(requested) == {0, 1, 2}
    for action in trace["actions"].values():
        assert sorted(action["ranked_rows"]) == [0, 1, 2]
    assert "gold" not in trace and "targets" not in trace


def test_existing_gpu_pipeline_uses_site_rows_for_colliding_names():
    from scripts.fresh_website import Gpu

    seen = []
    fn = SimpleNamespace(ids=["a.py::run", "a.py::run"])

    def texts(index, rows):
        seen.extend(rows)
        return [f"row-{r}" for r in rows]

    site = SimpleNamespace(
        last_ranked_rows=[0, 1],
        snaps=SimpleNamespace(
            get=lambda *_: (fn, None, None),
            r=SimpleNamespace(indexer=SimpleNamespace(unit_texts=texts)),
        ),
    )
    gpu = object.__new__(Gpu)
    gpu.config = {"languages": {"python": {"depth": 50, "weight": 1.0}}}
    gpu.members = [SimpleNamespace(score=lambda *_: np.array([1.0, 0.0]))]
    inst = SimpleNamespace(repo="org/repo", base_commit="abc", problem_statement="report")
    gpu.rerank(site, inst, fn.ids)
    assert seen == [0, 1]
    site.last_ranked_rows = []
    with pytest.raises(ValueError, match="aligned row identities"):
        gpu.rerank(site, inst, fn.ids)
