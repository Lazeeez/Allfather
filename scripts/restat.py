"""Recompute the p-values the site publishes with the paired randomization test in metrics.py.

    uv run python scripts/restat.py

Reads only saved outcomes: the per-issue rows in results/browser_ltr_multilang/report.json and the
win/loss counts in results/website-rerank/*.json. No model runs and no test set is evaluated again.
Writes web/public/data/lite.json in place. The languages that use the learned ranker were chosen by
the cross-validation rule of ADR 0025 with the earlier test; that choice is recorded, not redone.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from allfather.eval.metrics import holm, mcnemar_exact, paired_bootstrap

ROOT = Path(__file__).resolve().parents[1]
LITE = ROOT / "web" / "public" / "data" / "lite.json"
REPORT = ROOT / "results" / "browser_ltr_multilang" / "report.json"
GPU = ROOT / "results" / "website-rerank"
FAMILY = ("multilingual", "polybench")
TEST = "paired randomization: exact McNemar on hit@10; Holm-adjusted across the language rows of the two test sets"


def by_language(rows: list[dict]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["language"], []).append(r)
    return {
        lang: (
            np.array([r["keyword_and_meaning_hit@10"] for r in rs]),
            np.array([r["learned_hit@10"] for r in rs]),
        )
        for lang, rs in out.items()
    }


def gain(base: np.ndarray, learned: np.ndarray, old: dict) -> dict:
    d = paired_bootstrap(base, learned)
    if abs(d.delta - old["delta"]) > 1e-4:
        raise SystemExit(f"recomputed delta {d.delta} differs from the saved {old['delta']}")
    return {**old, "p": d.p_value, "wins": d.wins, "losses": d.losses}


def exact(paired: dict) -> float:
    return round(mcnemar_exact(paired["wins"], paired["losses"]), 4)


def main() -> int:
    lite = json.loads(LITE.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    for name, rows in report["held_out_per_issue"].items():
        langs = lite["held_out_per_language"].get(name)
        if not langs:
            continue
        for lang, (base, learned) in by_language(rows).items():
            langs[lang]["hit@10_gain"] = gain(base, learned, langs[lang]["hit@10_gain"])
    family = {
        f"{name}:{lang}": e["hit@10_gain"]["p"]
        for name in FAMILY
        for lang, e in lite["held_out_per_language"].get(name, {}).items()
    }
    for key, p in holm(family).items():
        name, lang = key.split(":")
        lite["held_out_per_language"][name][lang]["hit@10_gain"]["p_holm"] = p

    for lang, (base, learned) in by_language(report["cv_per_issue"]).items():
        entry = lite["cv_per_language"][lang]
        entry["hit@10_gain"] = gain(base, learned, entry["hit@10_gain"])

    gpu = lite["gpu_reranker"]
    pooled = json.loads((GPU / "server_reranker_current.json").read_text(encoding="utf-8"))
    gpu["hit@10_gain"]["p_value"] = exact(pooled["pooled"]["paired"]["hit@10"])
    skip = json.loads((GPU / "skip_language_model_current.json").read_text(encoding="utf-8"))
    gpu["skip_hit@10"]["p_value"] = exact(skip["paired"]["hit@10"])
    held = json.loads((GPU / "heldout_heldout.json").read_text(encoding="utf-8"))
    for which, entry in gpu["held_out"].items():
        entry["hit@10_gain"]["p_value"] = exact(held[which]["paired"]["hit@10"])
    gpu.pop("other_languages", None)
    shipped = json.loads((GPU / "choice.json").read_text(encoding="utf-8"))["languages"]["A"]
    others = json.loads((GPU / "server_reranker_cand-A-multilang.json").read_text(encoding="utf-8"))
    python = json.loads((GPU / "server_reranker_cand-A-python.json").read_text(encoding="utf-8"))
    gpu["six_languages"] = {
        "issues": sum(row["issues"] for row in shipped.values()),
        "projects": others["projects"] + python["projects"],
        "by_language": {
            lang: {
                "issues": row["issues"],
                "website_hit@10": row["website"],
                "with_reranker_hit@10": row["with"],
                "gain": row["delta"],
                "wins": row["wins"],
                "losses": row["losses"],
                "p_holm": row["p_holm"],
            }
            for lang, row in shipped.items()
        },
    }

    lite["tests"] = TEST
    LITE.write_text(json.dumps(lite, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    for name in FAMILY:
        for lang, e in lite["held_out_per_language"].get(name, {}).items():
            g = e["hit@10_gain"]
            print(
                f"{name:12} {lang:10} +{g['delta']:.3f} {g['wins']}/{g['losses']} p={g['p']} holm={g['p_holm']}"
            )
    print(
        "gpu",
        gpu["hit@10_gain"]["p_value"],
        gpu["skip_hit@10"]["p_value"],
        {k: v["hit@10_gain"]["p_value"] for k, v in gpu["held_out"].items()},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
