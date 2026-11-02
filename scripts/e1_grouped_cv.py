"""E1 of ADR 0033: how optimistic is cross-validation grouped by issue rather than by project?

    uv run python scripts/e1_grouped_cv.py

Reads the ranker features saved by `allfather ltr` (SWE-bench test minus Lite, 1,941 issues, 12
projects) and cross-validates the same LambdaMART ranker three ways on the same matrix: five folds
of random issues (ADR 0006), five folds that keep each project together, and one fold per project.
No test set is read. Writes results/research/e1_grouped_cv.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from allfather.eval.metrics import holm, paired_bootstrap
from allfather.eval.provenance import provenance
from allfather.rank.ltr import LEVELS, RankingData, _folds, cross_validate, project_folds

FEATURES = "results/ltr_features_full_minus_lite_{level}.npz"
OUT = Path("results/research/e1_grouped_cv.json")
KS = (1, 5, 10)


def load(path: str) -> RankingData:
    z = np.load(path)
    return RankingData(z["X"], z["y"], z["group"], z["n_gold"], z["qids"].tolist())


def per_query(scores: np.ndarray, data: RankingData) -> dict[str, np.ndarray]:
    out = {f"hit@{k}": [] for k in KS} | {f"recall@{k}": [] for k in KS} | {"mrr": []}
    start = 0
    for size, n_gold in zip(data.group, data.n_gold, strict=True):
        s, y = scores[start : start + size], data.y[start : start + size]
        order = np.argsort(-s, kind="stable")
        for k in KS:
            found = y[order[:k]].sum()
            out[f"hit@{k}"].append(float(found > 0))
            out[f"recall@{k}"].append(found / n_gold)
        hits = np.flatnonzero(y[order])
        out["mrr"].append(1.0 / (hits[0] + 1) if len(hits) else 0.0)
        start += size
    return {k: np.array(v) for k, v in out.items()}


def project_ci(
    values: np.ndarray, projects: np.ndarray, n: int = 4000, seed: int = 0
) -> list[float]:
    names = np.unique(projects)
    rows = {p: np.flatnonzero(projects == p) for p in names}
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n):
        picked = np.concatenate([rows[p] for p in rng.choice(names, len(names))])
        means.append(values[picked].mean())
    return [round(float(x), 4) for x in np.percentile(means, [2.5, 97.5])]


def main() -> int:
    report: dict = {
        "adr": "docs/decisions/0033-frontier-comparison-protocol.md",
        "experiment": "E1",
        "levels": {},
    }
    family = {}
    for level, (names, baseline, _) in LEVELS.items():
        data = load(FEATURES.format(level=level))
        projects = np.array([q.rsplit("-", 1)[0] for q in data.qids])
        schemes = {
            "issue_5fold": _folds(len(data.group), 5, 0),
            "project_5fold": project_folds(data.qids, 5),
            "leave_one_project_out": project_folds(data.qids, len(set(projects))),
        }
        level_report = {
            "queries": len(data.group),
            "projects": int(len(set(projects))),
            "schemes": {},
        }
        values = {}
        for name, splits in schemes.items():
            rounds, _, _ = cross_validate(data, baseline, names, splits=splits)
            values[name] = per_query(data.oof, data)
            level_report["schemes"][name] = {
                "rounds": rounds,
                "folds": len(splits),
                **{m: round(float(v.mean()), 4) for m, v in values[name].items()},
                "hit@10_ci95_by_project": project_ci(values[name]["hit@10"], projects),
            }
            print(
                level,
                name,
                rounds,
                {
                    m: round(float(v.mean()), 4)
                    for m, v in values[name].items()
                    if m in ("hit@10", "recall@10", "mrr")
                },
                flush=True,
            )
        base = per_query(-data.X[:, names.index(baseline)], data)
        level_report["hybrid_baseline"] = {m: round(float(v.mean()), 4) for m, v in base.items()}
        level_report["issue_minus_project"] = {}
        for other in ("project_5fold", "leave_one_project_out"):
            for metric in ("hit@10", "recall@10", "mrr"):
                d = paired_bootstrap(values[other][metric], values["issue_5fold"][metric])
                key = f"{level}:{other}:{metric}"
                family[key] = d.p_value
                level_report["issue_minus_project"][f"{other}:{metric}"] = {
                    "delta": d.delta, "ci95": list(d.ci95), "p": d.p_value, "wins": d.wins, "losses": d.losses,
                }  # fmt: skip
        report["levels"][level] = level_report
    for key, p in holm(family).items():
        level, other, metric = key.split(":")
        report["levels"][level]["issue_minus_project"][f"{other}:{metric}"]["p_holm"] = p
    report["provenance"] = provenance()
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps({lv: r["issue_minus_project"] for lv, r in report["levels"].items()}, indent=1)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
