"""Choose the six-language GPU reranker by ADR 0034's rule, from the saved fold scores.

    uv run python scripts/rerank_choice.py

For every scored configuration (the current Python-only pair and candidates A, B and C), the bugs are
ranked exactly as scripts/website_rerank.py evaluates them: depth and weight chosen on one half of the
projects, applied to the other, halves pooled. Per language it reports each configuration's function
hit@10, the paired exact test against the website pipeline with Holm's correction across languages,
and the paired test between configurations, so the choice compares them on the same bugs. Writes
results/website-rerank/choice.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import website_rerank as wr  # noqa: E402

from allfather.eval.metrics import aggregate, holm, mcnemar_exact  # noqa: E402

CONFIGS = {
    "current pair": ("zero-shot-multilang", "current"),
    "A": ("cand-A-multilang", "cand-A-python"),
    "B": ("cand-B-multilang", "cand-B-python"),
    "C": ("cand-C-multilang", "cand-C-python"),
}


def outcomes(task_file: Path, name: str) -> tuple[dict[str, int], dict[str, int], dict[str, str]]:
    tasks = [json.loads(line) for line in task_file.open(encoding="utf-8")]
    tasks = [t for t in tasks if t["gold"] and t["ids"]]
    raw = {
        r["qid"]: r["scores"]
        for r in map(json.loads, (wr.WORK / f"scores_{name}.jsonl").open(encoding="utf-8"))
    }
    repos = sorted({t["repo"] for t in tasks})
    half = set(
        np.asarray(repos)[np.random.default_rng(wr.SEED).permutation(len(repos))[: len(repos) // 2]]
    )
    halves = [[t for t in tasks if t["repo"] in half], [t for t in tasks if t["repo"] not in half]]
    grid = [(d, w) for d in wr.DEPTHS for w in wr.WEIGHTS]
    base, cand, lang = {}, {}, {}
    for k in (0, 1):
        choose_on, apply_to = halves[k], halves[1 - k]
        hits = {s: aggregate(wr.scored(choose_on, raw, s), wr.KS)["hit@10"] for s in grid}
        best = max(grid, key=lambda s: (hits[s], -s[0]))
        for t, b, c in zip(
            apply_to, wr.scored(apply_to, raw, None), wr.scored(apply_to, raw, best), strict=True
        ):
            base[t["qid"]], cand[t["qid"]], lang[t["qid"]] = (
                b.hit[10],
                c.hit[10],
                t.get("language", "python"),
            )
    return base, cand, lang


def paired(a: dict[str, int], b: dict[str, int], ids: list[str]) -> dict:
    wins = sum(1 for q in ids if b[q] > a[q])
    losses = sum(1 for q in ids if a[q] > b[q])
    return {
        "delta": round(float(np.mean([b[q] - a[q] for q in ids])), 4),
        "wins": wins,
        "losses": losses,
        "p": round(mcnemar_exact(wins, losses), 6),
    }


def main() -> int:
    files = (wr.WORK / "tasks_multilang.jsonl", wr.WORK / "tasks.jsonl")
    base, lang, results = {}, {}, {}
    for config, names in CONFIGS.items():
        results[config] = {}
        for task_file, name in zip(files, names, strict=True):
            b, c, found = outcomes(task_file, name)
            base.update(b)
            lang.update(found)
            results[config].update(c)
    languages = sorted(set(lang.values()))
    report: dict = {"languages": {}, "head_to_head": {}}
    for config, cand in results.items():
        rows = {}
        for L in languages:
            ids = [q for q in cand if lang[q] == L]
            rows[L] = {
                "issues": len(ids),
                "website": round(float(np.mean([base[q] for q in ids])), 4),
                "with": round(float(np.mean([cand[q] for q in ids])), 4),
            } | paired(base, cand, ids)
        adjusted = holm({L: r["p"] for L, r in rows.items() if L != "python"})
        for L, r in rows.items():
            r["p_holm"] = adjusted.get(L)
            r["passes"] = bool(L != "python" and r["delta"] >= 0.02 and adjusted[L] < 0.05)
        report["languages"][config] = rows
    for x in CONFIGS:
        for y in CONFIGS:
            if x < y:
                report["head_to_head"][f"{x} vs {y}"] = {
                    L: paired(results[x], results[y], [q for q in results[x] if lang[q] == L])
                    for L in languages
                }
    target = wr.OUT / "choice.json"
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    head = "".join(f"{c:>14}" for c in CONFIGS)
    print(f"{'language':12}{'website':>9}{head}")
    for L in languages:
        print(
            f"{L:12}{report['languages']['A'][L]['website']:9.3f}"
            + "".join(
                f"{report['languages'][c][L]['with']:10.3f}{'*' if report['languages'][c][L]['passes'] else ' '}   "
                for c in CONFIGS
            )
        )
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
