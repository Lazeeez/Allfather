"""Apply ADR 0036's rule: does a reranker that reads more of the report beat candidate A?

    uv run python scripts/rerank_long.py

Every bug is ranked as the site ranks it: the website pipeline's out-of-fold top 50 blended with
the reranker's scores at the frozen depth and per-language weight of
results/website-rerank/gpu_config.json, nothing tuned. Candidate A (512 tokens of the report) is
compared with A-read2048 and L on the training bugs' out-of-fold scores, with the exact paired
test, on reports longer than 2,000 characters, on all bugs, and per language. Writes
results/website-rerank/long_reports.json.
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

from allfather.eval.metrics import mcnemar_exact  # noqa: E402

BASELINE = "A"
CANDIDATES = ("A-read2048", "L")
LONG = 2000
CONFIG = ROOT / "results" / "website-rerank" / "gpu_config.json"


def tasks() -> list[dict]:
    out = []
    for path in (wr.WORK / "tasks.jsonl", wr.WORK / "tasks_multilang.jsonl"):
        for line in path.open(encoding="utf-8"):
            t = json.loads(line)
            if t["gold"] and t["ids"]:
                t.setdefault("language", "python")
                out.append(t)
    return out


def hits(name: str, items: list[dict], settings: dict) -> dict[str, int]:
    raw = {
        r["qid"]: r["scores"]
        for r in map(json.loads, (wr.WORK / f"scores_cand-{name}.jsonl").open(encoding="utf-8"))
    }
    out = {}
    for lang in sorted({t["language"] for t in items}):
        group = [t for t in items if t["language"] == lang]
        s = settings[lang]
        for t, score in zip(group, wr.scored(group, raw, (s["depth"], s["weight"])), strict=True):
            out[t["qid"]] = score.hit[10]
    return out


def paired(a: dict[str, int], b: dict[str, int], ids: list[str]) -> dict:
    wins = sum(1 for q in ids if b[q] > a[q])
    losses = sum(1 for q in ids if a[q] > b[q])
    return {
        "bugs": len(ids),
        "baseline_hit@10": round(float(np.mean([a[q] for q in ids])), 4),
        "candidate_hit@10": round(float(np.mean([b[q] for q in ids])), 4),
        "delta": round(float(np.mean([b[q] - a[q] for q in ids])), 4),
        "wins": wins,
        "losses": losses,
        "p": round(mcnemar_exact(wins, losses), 6),
    }


def main() -> int:
    settings = json.loads(CONFIG.read_text(encoding="utf-8"))["languages"]
    items = tasks()
    lang = {t["qid"]: t["language"] for t in items}
    long_ids = [t["qid"] for t in items if len(t["query"]) > LONG]
    base = hits(BASELINE, items, settings)
    report: dict = {
        "rule": "long reports (> 2,000 characters): gain >= 2.0 points with p < 0.05; all bugs: no loss; no language loses more than 1.0 point (ADR 0036)",
        "long_reports": len(long_ids),
        "candidates": {},
    }
    for name in CANDIDATES:
        cand = hits(name, items, settings)
        ids = sorted(cand)
        by_language = {
            L: paired(base, cand, [q for q in ids if lang[q] == L])
            for L in sorted(set(lang.values()))
        }
        entry = {
            "long": paired(base, cand, long_ids),
            "all": paired(base, cand, ids),
            "by_language": by_language,
        }
        entry["passes_accuracy"] = bool(
            entry["long"]["delta"] >= 0.02
            and entry["long"]["p"] < 0.05
            and entry["all"]["delta"] >= 0
            and all(v["delta"] >= -0.01 for v in by_language.values())
        )
        report["candidates"][name] = entry
        print(
            f"{name}: long {entry['long']['delta'] * 100:+.1f} ({entry['long']['wins']}/{entry['long']['losses']}, p={entry['long']['p']}), "
            f"all {entry['all']['delta'] * 100:+.1f} (p={entry['all']['p']}), "
            + ", ".join(f"{L} {v['delta'] * 100:+.1f}" for L, v in by_language.items())
            + f" -> {'passes' if entry['passes_accuracy'] else 'fails'} the accuracy tests"
        )
    target = ROOT / "results" / "website-rerank" / "long_reports.json"
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
