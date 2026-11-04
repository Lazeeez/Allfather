import random

from allfather.rank.ce_train import training_plan


def old_draws(usable: list[dict], epochs: int, group: int) -> list[tuple[str, int, list[int]]]:
    out = []
    for _ in range(epochs):
        random.shuffle(usable)
        for rec in usable:
            pi = random.randrange(len(rec["pos"]))
            ni = random.sample(range(len(rec["neg"])), min(group - 1, len(rec["neg"])))
            out.append((rec["qid"], pi, ni))
    return out


def records() -> list[dict]:
    return [
        {"qid": f"q{i}", "pos": ["p"] * (1 + i % 3), "neg": ["n"] * (5 + 7 * i % 20)}
        for i in range(40)
    ]


def test_plan_draws_exactly_what_the_training_loop_always_drew():
    random.seed(0)
    expected = old_draws(records(), epochs=2, group=16)
    random.seed(0)
    plan = training_plan(records(), epochs=2, group=16)
    assert [(rec["qid"], pi, ni) for rec, pi, ni in plan] == expected
    assert len(plan) == 80
