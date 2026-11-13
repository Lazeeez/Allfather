from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import comb

import numpy as np


@dataclass(frozen=True, slots=True)
class QueryScore:
    recall: dict[int, float]
    hit: dict[int, float]
    full: dict[int, float]
    rr: float
    first_rank: int | None


def score(ranked: Sequence[str], gold: Iterable[str], ks: Sequence[int]) -> QueryScore:
    gold_set = set(gold)
    if not gold_set:
        raise ValueError("gold set is empty")
    seen: list[str] = []
    dedup: set[str] = set()
    for item in ranked:
        if item not in dedup:
            dedup.add(item)
            seen.append(item)
    first_rank = next((i + 1 for i, item in enumerate(seen) if item in gold_set), None)
    recall, hit, full = {}, {}, {}
    for k in ks:
        found = len(gold_set.intersection(seen[:k]))
        recall[k] = found / len(gold_set)
        hit[k] = float(found > 0)
        full[k] = float(found == len(gold_set))
    return QueryScore(recall, hit, full, 1.0 / first_rank if first_rank else 0.0, first_rank)


def aggregate(scores: Sequence[QueryScore], ks: Sequence[int]) -> dict[str, float]:
    n = len(scores)
    if n == 0:
        return {"n": 0}
    out: dict[str, float] = {"n": n, "mrr": sum(s.rr for s in scores) / n}
    for k in ks:
        out[f"recall@{k}"] = sum(s.recall[k] for s in scores) / n
        out[f"hit@{k}"] = sum(s.hit[k] for s in scores) / n
        out[f"all@{k}"] = sum(s.full[k] for s in scores) / n
    return {key: round(v, 4) if isinstance(v, float) else v for key, v in out.items()}


def metric_values(scores: Sequence[QueryScore], metric: str) -> np.ndarray:
    """Per-query values of an aggregate metric name such as `mrr` or `recall@10`."""
    if metric == "mrr":
        return np.array([s.rr for s in scores])
    name, k = metric.split("@")
    attr = {"recall": "recall", "hit": "hit", "all": "full"}[name]
    return np.array([getattr(s, attr)[int(k)] for s in scores])


def bootstrap_ci(
    scores: Sequence[QueryScore], metric: str, n: int = 2000, seed: int = 0
) -> list[float]:
    """95% percentile-bootstrap interval of the mean over queries."""
    values = metric_values(scores, metric)
    if not len(values):
        return [0.0, 0.0]
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (n, len(values)))].mean(axis=1)
    return [round(float(x), 4) for x in np.percentile(means, [2.5, 97.5])]


@dataclass(frozen=True, slots=True)
class PairedDiff:
    delta: float
    ci95: tuple[float, float]
    p_value: float
    wins: int
    losses: int


def paired_bootstrap(a: np.ndarray, b: np.ndarray, n: int = 10000, seed: int = 0) -> PairedDiff:
    """Is b better than a on the same queries? Resamples queries, keeping pairs together.

    The interval is a percentile bootstrap of the mean difference. The p-value is two-sided
    and comes from a paired randomization test (Urbano et al., SIGIR 2019): exact McNemar
    when every difference is -1, 0 or 1, random sign flips otherwise.
    """
    diff = np.asarray(b, float) - np.asarray(a, float)
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), (n, len(diff)))].mean(axis=1)
    observed = diff.mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return PairedDiff(
        round(float(observed), 4),
        (round(float(lo), 4), round(float(hi), 4)),
        sign_flip_p(diff, n, seed),
        int((diff > 0).sum()),
        int((diff < 0).sum()),
    )


def sign_flip_p(diff: np.ndarray, n: int = 10000, seed: int = 0) -> float:
    nonzero = diff[diff != 0]
    if not len(nonzero):
        return 1.0
    if np.all(np.abs(nonzero) == 1):
        wins, total = int((nonzero > 0).sum()), len(nonzero)
        return mcnemar_exact(wins, total - wins)
    rng = np.random.default_rng(seed)
    observed = abs(nonzero.sum())
    signs = rng.choice([-1.0, 1.0], size=(n, len(nonzero)))
    extreme = int((np.abs(signs @ nonzero) >= observed - 1e-12).sum())
    return (extreme + 1) / (n + 1)


def mcnemar_exact(wins: int, losses: int) -> float:
    total = wins + losses
    if total == 0:
        return 1.0
    tail = min(wins, losses)
    cdf = sum(comb(total, i) for i in range(tail + 1)) / 2**total
    return float(min(1.0, 2 * cdf))


def holm(p_values: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values, for a family of tests reported together."""
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    out, running = {}, 0.0
    for i, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - i) * p))
        out[key] = running
    return out


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(p / 100 * (len(ordered) - 1))))
    return ordered[idx]
