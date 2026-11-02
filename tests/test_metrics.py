import numpy as np
import pytest

from allfather.eval.metrics import (
    aggregate,
    bootstrap_ci,
    holm,
    mcnemar_exact,
    paired_bootstrap,
    percentile,
    score,
    sign_flip_p,
)


def test_score_basic():
    s = score(["a", "b", "c", "d"], {"c", "x"}, ks=[1, 3, 5])
    assert s.first_rank == 3
    assert s.rr == pytest.approx(1 / 3)
    assert s.recall == {1: 0.0, 3: 0.5, 5: 0.5}
    assert s.hit == {1: 0.0, 3: 1.0, 5: 1.0}
    assert s.full == {1: 0.0, 3: 0.0, 5: 0.0}


def test_duplicates_do_not_inflate_rank_budget():
    s = score(["a", "a", "a", "b"], {"b"}, ks=[2])
    assert s.first_rank == 2
    assert s.recall[2] == 1.0


def test_miss():
    s = score(["a"], {"b"}, ks=[10])
    assert s.first_rank is None
    assert s.rr == 0.0


def test_empty_gold_rejected():
    with pytest.raises(ValueError):
        score(["a"], set(), ks=[1])


def test_aggregate():
    scores = [score(["a"], {"a"}, [1]), score(["b"], {"a"}, [1])]
    agg = aggregate(scores, [1])
    assert agg["n"] == 2
    assert agg["recall@1"] == 0.5
    assert agg["mrr"] == 0.5


def test_bootstrap_ci_brackets_mean():
    scores = [score(["a"], {"a"}, [1])] * 30 + [score(["b"], {"a"}, [1])] * 70
    lo, hi = bootstrap_ci(scores, "recall@1")
    assert lo < 0.3 < hi
    assert bootstrap_ci([score(["a"], {"a"}, [1])] * 5, "mrr") == [1.0, 1.0]


def test_paired_bootstrap_detects_real_difference():
    a = np.array([0.0] * 50 + [1.0] * 50)
    b = np.array([1.0] * 90 + [0.0] * 10)
    d = paired_bootstrap(a, b)
    assert d.delta == pytest.approx(0.4)
    assert d.p_value < 0.01
    assert d.ci95[0] > 0


def test_paired_bootstrap_identical_runs_are_not_significant():
    a = np.array([0.0, 1.0] * 50)
    d = paired_bootstrap(a, a.copy())
    assert d.delta == 0
    assert d.p_value == 1.0


def test_mcnemar_exact_matches_the_binomial_test():
    assert mcnemar_exact(4, 0) == pytest.approx(0.125)
    assert mcnemar_exact(9, 2) == pytest.approx(0.0654296875)
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 0) == 1.0


def test_paired_bootstrap_uses_the_exact_test_on_binary_outcomes():
    a = np.array([0.0] * 4 + [1.0] * 10)
    b = np.array([1.0] * 4 + [1.0] * 10)
    assert paired_bootstrap(a, b).p_value == pytest.approx(0.125)


def test_sign_flip_p_on_continuous_differences():
    rng = np.random.default_rng(1)
    assert sign_flip_p(rng.normal(1.0, 0.5, 40)) < 0.001
    assert sign_flip_p(rng.normal(0.0, 0.5, 40)) > 0.01
    assert sign_flip_p(np.zeros(10)) == 1.0


def test_holm_adjusts_in_order_and_stays_monotone():
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == {"a": 0.03, "c": 0.06, "b": 0.06}


def test_percentile():
    assert percentile([5, 1, 3], 50) == 3
    assert percentile([], 99) == 0.0
