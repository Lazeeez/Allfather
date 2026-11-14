from types import SimpleNamespace

import numpy as np
import pytest

from allfather.index.chunker import MODULE, chunk_file
from allfather.index.snapshot import unit_key, unit_text
from allfather.rank.cross_encoder import CrossEncoder
from scripts import replay_text_views as replay
from scripts.text_views import doc_views, positions, select, windows


def test_token_views_preserve_budget_and_leave_short_inputs_unchanged():
    tokenizer = SimpleNamespace(decode=lambda ids: " ".join(f"word{i}" for i in ids))
    for n in (0, 1, 255, 256, 257, 590, 3000):
        ids = list(range(n))
        variants = doc_views(tokenizer, ids, [1000], "seed")
        assert {len(v["ids"]) for v in variants.values()} == {min(n, 256)}
        if n <= 256:
            assert all(v["ids"] == ids for v in variants.values())
        assert variants == doc_views(tokenizer, ids, [1000], "seed")
    assert select(list(range(10)), positions(10, 4, "head_tail")) == [0, 1, 8, 9]
    assert windows(590, 256)[-1] == [334, 590]


def test_lexical_window_finds_late_evidence_and_falls_back_to_prefix():
    tokenizer = SimpleNamespace(
        decode=lambda ids: " ".join("socketFailure" if i == 2 else "padding" for i in ids)
    )
    ids = [1] * 500 + [2] * 90
    selected = doc_views(tokenizer, ids, [2], "seed")
    assert selected["lexical"]["spans"][0][0] > 0
    assert 2 in selected["lexical"]["ids"]
    no_match = doc_views(SimpleNamespace(decode=lambda ids: ""), ids, [], "seed")
    assert no_match["lexical"]["spans"] == [[0, 256]]


def test_explicit_tokens_build_identical_prompts_and_enforce_budgets():
    ce = object.__new__(CrossEncoder)
    ce.tok = lambda s, **kwargs: {"input_ids": list(s.encode())}
    ce._fixed_ids = {}
    ce.max_query_tokens, ce.max_doc_tokens = 4, 3
    ce._score_encoded = lambda prefix, docs: (prefix, docs)
    expected = ce.score("query", ["document", "ab"])
    assert ce.score_tokenized(list(b"quer"), [list(b"doc"), list(b"ab")]) == expected
    with pytest.raises(ValueError, match="limit"):
        ce.score_tokenized([1] * 5, [[2]])
    with pytest.raises(ValueError, match="limit"):
        ce.score_tokenized([1], [[2] * 4])
    for invalid in (-1, True, "1"):
        with pytest.raises(ValueError, match="integer"):
            ce.score_tokenized([invalid], [])
    assert ce.score("ignored", []).size == 0


def test_source_reconstruction_keeps_colliding_names_and_checks_hashes(monkeypatch, tmp_path):
    import hashlib

    source = (
        b"if flag:\n    def run():\n        return 1\nelse:\n    def run():\n        return 2\n"
    )
    chunks = [c for c in chunk_file(source, "a.py") if c.kind != MODULE]
    texts = [unit_text(c.qualname, c.text) for c in chunks]
    oid = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    trace = {
        "repo": "org/repo",
        "files": [{"path": "a.py", "blob": oid}],
        "universe": [
            {"row": i, "id": "a.py::run", "text_key": unit_key(t).hex()}
            for i, t in enumerate(texts)
        ],
    }

    def batch(args, **kwargs):
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"
        return SimpleNamespace(
            returncode=0, stdout=f"{oid} blob {len(source)}\n".encode() + source + b"\n"
        )

    monkeypatch.setattr(replay.subprocess, "run", batch)
    assert replay.source_texts(trace, [1, 0], tmp_path) == texts[::-1]
    trace["universe"][0]["text_key"] = "wrong"
    with pytest.raises(ValueError, match="not reconstructed"):
        replay.source_texts(trace, [0], tmp_path)


def test_capture_runs_all_controls_with_fixed_rows_and_budget():
    class FakeCE:
        tokens_computed = 0

        def score_tokenized(self, query, docs):
            self.tokens_computed += len(query) + sum(map(len, docs))
            return np.array([sum(d) for d in docs], dtype=float)

    trace = {"id": "x#1", "actions": {}}
    for pool, depth in replay.POOL_DEPTHS.items():
        trace["actions"][f"{pool}_local"] = {"ranked_rows": [4, 2, 8]}
        trace["actions"][f"{pool}_ce{depth}"] = {
            "read_rows": [4, 2, 8],
            "raw_scores": [4, 2, 8],
            "ranked_rows": [4, 8, 2],
        }
    prepared = {
        "pools": {p: [4, 2, 8] for p in replay.POOL_DEPTHS},
        "queries": {q: {"ids": [1, 2]} for q in replay.QUERY_VIEWS},
        "views": {
            q: {r: {d: {"ids": [r]} for d in replay.DOC_VIEWS} for r in [4, 2, 8]}
            for q in replay.QUERY_VIEWS
        },
    }
    result = replay.capture(trace, prepared, FakeCE(), lambda: None)
    assert len(result["actions"]) == 16
    assert {a["tokens_computed"] for a in result["actions"].values()} == {5}
    assert all(a["read_rows"] == [4, 2, 8] for a in result["actions"].values())
    assert all(set(a["ranked_rows"]) == {2, 4, 8} for a in result["actions"].values())


def test_visibility_handles_multibyte_offsets():
    from scripts.audit_fit_evidence import visible

    # Multiple byte-level tokens may end at the same Unicode character.
    def tokenizer(*args, **kwargs):
        return {"offset_mapping": [(0, 1), (0, 1), (1, 2), (2, 3)]}

    assert visible(tokenizer, "你好吗", 2)["visible_text"] == "你"
