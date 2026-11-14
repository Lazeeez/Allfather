"""Deterministic token-budget controls, with no labels, paths or repository metadata."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter

from allfather.search.tokenize import code_counts

QUERY_VIEWS = ("prefix", "head_tail")
DOC_VIEWS = ("prefix", "head_tail", "lexical", "random")


def positions(n: int, budget: int, mode: str) -> list[list[int]]:
    if n < 0 or budget <= 0:
        raise ValueError("invalid token count/budget")
    if mode not in QUERY_VIEWS:
        raise ValueError("unknown positional view")
    if n <= budget or mode == "prefix":
        return [[0, min(n, budget)]]
    head = (budget + 1) // 2
    return [[0, head], [n - (budget - head), n]]


def windows(n: int, budget: int) -> list[list[int]]:
    if n < 0 or budget <= 0:
        raise ValueError("invalid token count/budget")
    if n <= budget:
        return [[0, n]]
    starts = sorted({*range(0, n - budget + 1, max(1, budget // 2)), n - budget})
    return [[i, i + budget] for i in starts]


def select(ids: list[int], spans: list[list[int]]) -> list[int]:
    return [t for start, end in spans for t in ids[start:end]]


def token_hash(ids: list[int]) -> str:
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def doc_views(tokenizer, ids: list[int], query_ids: list[int], seed: str, budget=256) -> dict:
    """BM25 within this unit's overlapping windows; ties prefer the earliest window.

    The lexical selector sees only the selected query tokens. Its document-local IDF
    and all-window CPU work are controls, not a claimed novel or free selector.
    """
    spans = windows(len(ids), budget)
    query = set(code_counts(tokenizer.decode(query_ids)))
    counts = [code_counts(tokenizer.decode(ids[a:b])) for a, b in spans]
    df = Counter(term for terms in counts for term in terms)
    lengths = [sum(c.values()) for c in counts]
    mean_length = sum(lengths) / len(lengths) or 1.0
    scores = []
    for terms, length in zip(counts, lengths, strict=True):
        score = 0.0
        for term in query & terms.keys():
            idf = math.log1p((len(spans) - df[term] + 0.5) / (df[term] + 0.5))
            tf = terms[term]
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / mean_length))
        scores.append(score)
    best = max(range(len(spans)), key=lambda i: scores[i])
    random_index = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(spans)
    choices = {
        "prefix": positions(len(ids), budget, "prefix"),
        "head_tail": positions(len(ids), budget, "head_tail"),
        "lexical": [spans[best]],
        "random": [spans[random_index]],
    }
    return {
        name: {
            "ids": select(ids, ranges),
            "spans": ranges,
            "sha256": token_hash(select(ids, ranges)),
            "window_count": len(spans),
        }
        for name, ranges in choices.items()
    }
