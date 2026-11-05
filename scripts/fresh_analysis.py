"""The analysis of ADR 0033, for any set scripts/frontier.py and scripts/fresh_website.py have run.

    uv run python scripts/fresh_analysis.py --set pilot
    uv run python scripts/fresh_analysis.py --set fresh --threshold 0.62

RQ1: every system's function-level metrics with 95% intervals from a bootstrap over projects, and
paired tests against the reference (exact McNemar on yes/no metrics, a randomization test on MRR),
Holm-adjusted across the whole table. RQ2: mean cost and time per bug and the systems no other
beats on both accuracy and cost. RQ3: escalating the bugs the reference is least confident about to
each other system, across thresholds, against escalating the same number at random; --threshold
reports the operating point chosen beforehand on development data. RQ4: hit@10 by what the report
names. Writes results/research/analysis_<set>.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from frontier import FRESH, OUT, load_set, matched, unit_ids  # noqa: E402

from allfather.eval.metrics import holm, paired_bootstrap, score  # noqa: E402

METRICS = ("hit@1", "hit@5", "hit@10", "all@10", "mrr")
STRATA = ("function", "file", "trace", "none")
TRACE = re.compile(
    r"Traceback \(most recent call last\)|^\s+File \"[^\"]+\", line \d+|^\s+at [\w$.<>]+ \(?[^\s)]+:\d+|"
    r"^goroutine \d+ \[|panicked at |^\s+at [\w$.]+\([\w$]+\.java:\d+\)",
    re.M,
)


def per_issue(rows: list[dict], items: dict[str, dict]) -> dict[str, dict[str, float]]:
    out = {}
    for r in rows:
        gold = items[r["id"]]["gold"]
        if not gold:
            continue
        s = score(matched(unit_ids(r.get("answer")), gold), gold, [1, 5, 10])
        out[r["id"]] = {
            "hit@1": s.hit[1], "hit@5": s.hit[5], "hit@10": s.hit[10], "all@10": s.full[10], "mrr": s.rr,
            "cost": r.get("cost_usd") or 0.0, "seconds": r.get("seconds") or 0.0, "confidence": r.get("confidence"),
        }  # fmt: skip
    return out


def stratum(text: str, gold: list[str]) -> str:
    names = {g.split("::", 1)[1].split(".")[-1] for g in gold}
    if any(re.search(rf"(?<![\w.]){re.escape(n)}(?!\w)", text) for n in names):
        return "function"
    files = {g.split("::", 1)[0] for g in gold}
    if any(
        f in text or re.search(rf"(?<![\w/]){re.escape(f.rsplit('/', 1)[-1])}(?!\w)", text)
        for f in files
    ):
        return "file"
    return "trace" if TRACE.search(text) else "none"


def project_ci(
    values: np.ndarray, projects: np.ndarray, n: int = 4000, seed: int = 0
) -> list[float]:
    names = np.unique(projects)
    rows = {p: np.flatnonzero(projects == p) for p in names}
    rng = np.random.default_rng(seed)
    means = [
        values[np.concatenate([rows[p] for p in rng.choice(names, len(names))])].mean()
        for _ in range(n)
    ]
    return [round(float(x), 4) for x in np.percentile(means, [2.5, 97.5])]


def escalation(ref: dict, other: dict, ids: list[str], threshold: float | None) -> dict:
    conf = np.array(
        [ref[q]["confidence"] if ref[q]["confidence"] is not None else 0.0 for q in ids]
    )
    a = np.array([ref[q]["hit@10"] for q in ids])
    b = np.array([other[q]["hit@10"] for q in ids])
    cost_a = np.array([ref[q]["cost"] for q in ids])
    cost_b = np.array([other[q]["cost"] for q in ids])
    curve = []
    for t in sorted({0.0, 1.01, *np.round(conf, 4).tolist()}):
        send = conf < t
        curve.append(
            {
                "threshold": round(float(t), 4),
                "escalated": round(float(send.mean()), 4),
                "hit@10": round(float(np.where(send, b, a).mean()), 4),
                "random_hit@10": round(float(a.mean() + send.mean() * (b.mean() - a.mean())), 4),
                "cost": round(float((cost_a + send * cost_b).mean()), 5),
            }
        )
    out = {
        "reference_hit@10": round(float(a.mean()), 4),
        "other_hit@10": round(float(b.mean()), 4),
        "other_cost": round(float(cost_b.mean()), 5),
        "curve": curve,
    }
    if threshold is not None:
        out["chosen"] = next((c for c in curve if c["threshold"] >= threshold), curve[-1])
    return out


FREE_PREFIXES = ("website", "allfather", "swerank", "open-", "gemini-")
FREE_LUNA = {"codex-single", "codex-agent"}


def free_to_use(system: str) -> bool:
    return system.startswith(FREE_PREFIXES) or system in FREE_LUNA


def languages(set_name: str) -> dict[str, str]:
    if not set_name.startswith("fresh"):
        return {}
    return {
        r["id"]: r["language"]
        for r in map(json.loads, (FRESH / "gold.jsonl").open(encoding="utf-8"))
    }


def long_path_bugs(set_name: str) -> set[str]:
    path = FRESH / "long_path_bugs.json"
    if not set_name.startswith("fresh") or not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8"))["bugs"])


def cohen_kappa(a: list, b: list) -> float:
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    expected = sum((a.count(v) / n) * (b.count(v) / n) for v in set(a) | set(b))
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def strata_agreement() -> dict:
    sheet = list(csv.DictReader((FRESH / "strata_check.csv").open(encoding="utf-8")))
    column = next(c for c in sheet[0] if c.startswith("your_answer"))
    mine = {r["id"]: r[column].strip().lower() for r in sheet if r[column].strip()}
    if len(mine) < len(sheet):
        return {"filled_in": len(mine), "rows": len(sheet)}
    if bad := sorted({v for v in mine.values() if v not in STRATA}):
        sys.exit(f"strata_check.csv has answers outside {STRATA}: {bad}")
    parser = {
        r["id"]: r["parser_says"]
        for r in csv.DictReader((FRESH / "strata_parser.csv").open(encoding="utf-8"))
    }
    ids = sorted(mine)
    a, b = [mine[q] for q in ids], [parser[q] for q in ids]
    kappa = cohen_kappa(a, b)
    return {
        "rows": len(ids),
        "agreement": round(sum(x == y for x, y in zip(a, b, strict=True)) / len(ids), 4),
        "kappa": round(kappa, 4),
        "confusion": {
            f"{x}->{y}": sum(1 for p, q in zip(a, b, strict=True) if (p, q) == (x, y))
            for x in STRATA
            for y in STRATA
            if any((p, q) == (x, y) for p, q in zip(a, b, strict=True))
        },
        "rq4_indicative_only": kappa < 0.6,
    }


def repeatability(items: dict[str, dict], system: str = "codex-single-astra") -> dict | None:
    again = OUT / f"fresh-repeat50_{system}-repeat.jsonl"
    if not again.exists():
        return None
    first = {
        r["id"]: r
        for r in map(json.loads, (OUT / f"fresh-agents_{system}.jsonl").open(encoding="utf-8"))
    }
    second = {r["id"]: r for r in map(json.loads, again.open(encoding="utf-8"))}
    ids = sorted(set(first) & set(second))
    a, b = per_issue([first[q] for q in ids], items), per_issue([second[q] for q in ids], items)
    ids = sorted(set(a) & set(b))
    hit_a, hit_b = [a[q]["hit@10"] for q in ids], [b[q]["hit@10"] for q in ids]
    tops = [(unit_ids(first[q].get("answer")), unit_ids(second[q].get("answer"))) for q in ids]
    return {
        "issues": len(ids),
        "hit@10_first": round(float(np.mean(hit_a)), 4),
        "hit@10_again": round(float(np.mean(hit_b)), 4),
        "hit@10_outcome_changed": sum(x != y for x, y in zip(hit_a, hit_b, strict=True)),
        "hit@10_kappa": round(cohen_kappa(hit_a, hit_b), 4),
        "same_first_answer": round(
            float(np.mean([bool(x) and x[:1] == y[:1] for x, y in tops])), 4
        ),
        "top10_jaccard_mean": round(
            float(
                np.mean(
                    [
                        len(set(x) & set(y)) / len(set(x) | set(y)) if x or y else 1.0
                        for x, y in tops
                    ]
                )
            ),
            4,
        ),
    }


def paired_family(runs: dict, reference: str) -> dict:
    ref = runs[reference]
    out, family = {}, {}
    for system, res in runs.items():
        if system == reference:
            continue
        common = sorted(set(res) & set(ref))
        for m in METRICS:
            d = paired_bootstrap(
                np.array([ref[q][m] for q in common]), np.array([res[q][m] for q in common])
            )
            key = f"{system}:{m}"
            out[key] = {
                "issues": len(common),
                "delta": d.delta,
                "ci95": list(d.ci95),
                "p": d.p_value,
                "wins": d.wins,
                "losses": d.losses,
            }
            family[key] = d.p_value
    for key, p in holm(family).items():
        out[key]["p_holm"] = p
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--reference", default="website")
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--also-reference")
    args = ap.parse_args()
    _, items = load_set(args.set)
    runs = {}
    for path in sorted(OUT.glob(f"{args.set}_*.jsonl")):
        if path.name.endswith(".errors.jsonl"):
            continue
        system = path.stem[len(args.set) + 1 :]
        runs[system] = per_issue([json.loads(line) for line in path.open(encoding="utf-8")], items)
    if args.reference not in runs:
        sys.exit(f"no {args.reference} run for {args.set}")
    ref = runs[args.reference]
    report: dict = {
        "set": args.set,
        "reference": args.reference,
        "systems": {},
        "paired": {},
        "strata": {},
        "escalation": {},
    }
    report["paired"] = paired_family(runs, args.reference)
    if args.also_reference in runs:
        report["also_reference"] = {
            "reference": args.also_reference,
            "paired": paired_family(runs, args.also_reference),
        }
    for system, res in runs.items():
        ids = sorted(res)
        projects = np.array([items[q]["repo"] for q in ids])
        entry = {"issues": len(ids), "projects": int(len(set(projects)))}
        for m in METRICS:
            v = np.array([res[q][m] for q in ids])
            entry[m] = round(float(v.mean()), 4)
            entry[f"{m}_ci95"] = project_ci(v, projects)
        entry["cost_usd"] = round(float(np.mean([res[q]["cost"] for q in ids])), 5)
        entry["seconds"] = round(float(np.mean([res[q]["seconds"] for q in ids])), 1)
        report["systems"][system] = entry
        if system == args.reference:
            continue
        common = sorted(set(res) & set(ref))
        if all(ref[q]["confidence"] is not None for q in common):
            report["escalation"][system] = escalation(ref, res, common, args.threshold)
    langs = languages(args.set)
    if langs:
        report["by_language"] = {}
        for system, res in runs.items():
            report["by_language"][system] = {}
            for lang in sorted(set(langs.values())):
                qs = sorted(q for q in res if langs.get(q) == lang)
                if qs:
                    v = np.array([res[q]["hit@10"] for q in qs])
                    report["by_language"][system][lang] = {
                        "issues": len(qs),
                        "hit@10": round(float(v.mean()), 4),
                        "hit@10_ci95": project_ci(v, np.array([items[q]["repo"] for q in qs])),
                    }
    excluded = long_path_bugs(args.set)
    if excluded:
        report["sensitivity_without_long_path_bugs"] = {
            "bugs_left_out": len(excluded & set(ref)),
            "paired_hit@10": {},
        }
        for system, res in runs.items():
            if system == args.reference:
                continue
            common = sorted((set(res) & set(ref)) - excluded)
            d = paired_bootstrap(
                np.array([ref[q]["hit@10"] for q in common]),
                np.array([res[q]["hit@10"] for q in common]),
            )
            report["sensitivity_without_long_path_bugs"]["paired_hit@10"][system] = {
                "issues": len(common), "delta": d.delta, "ci95": list(d.ci95), "p": d.p_value,
            }  # fmt: skip
    if args.set.startswith("fresh"):
        report["strata_hand_check"] = strata_agreement()
        report["repeatability"] = {
            s: repeatability(items, s) for s in ("codex-single-astra", "codex-agent-astra")
        }
    strata = {q: stratum(items[q]["text"], items[q]["gold"]) for q in items if items[q]["gold"]}
    for system, res in runs.items():
        report["strata"][system] = {
            s: {
                "issues": len(qs),
                "hit@10": round(float(np.mean([res[q]["hit@10"] for q in qs])), 4),
            }
            for s in STRATA
            if (qs := [q for q in res if strata.get(q) == s])
        }
    order = sorted(report["systems"].items(), key=lambda kv: (kv[1]["cost_usd"], -kv[1]["hit@10"]))
    best = -1.0
    report["pareto"] = []
    for system, e in order:
        if e["hit@10"] > best:
            report["pareto"].append(system)
            best = e["hit@10"]
    free = sorted(
        (name for name in report["systems"] if free_to_use(name)),
        key=lambda n: -report["systems"][n]["hit@10"],
    )
    report["free_to_use"] = {
        "rule": "free to a user: Allfather, SweRank, open-weight models, gemini-3.8-flash (a free-tier model) and gpt-6-luna (the free ChatGPT model), Devstral Small 2 (open weights); decided by system, not by result (ADR 0033)",
        "ranking": [
            {
                "system": n,
                "hit@10": report["systems"][n]["hit@10"],
                "hit@10_ci95": report["systems"][n]["hit@10_ci95"],
            }
            for n in free
        ],
    }
    target = ROOT / "results" / "research" / f"analysis_{args.set}.json"
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    for system, e in report["systems"].items():
        print(
            f"{system:16} n={e['issues']:4} hit@1 {e['hit@1']:.3f} hit@10 {e['hit@10']:.3f} {e['hit@10_ci95']} all@10 {e['all@10']:.3f} MRR {e['mrr']:.3f} ${e['cost_usd']:.4f} {e['seconds']} s"
        )
    for key, v in report["paired"].items():
        if key.endswith("hit@10"):
            print(
                f"  {key}: {v['delta']:+.3f} {v['wins']}/{v['losses']} p={v['p']} holm={v['p_holm']}"
            )
    print("pareto:", report["pareto"])
    print("strata:", {s: report["strata"][args.reference].get(s, {}).get("issues") for s in STRATA})
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
