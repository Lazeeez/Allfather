"""Verify a PACE rescore bundle and compute exploratory project-paired hit@10 diagnostics."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from audit_symbol_inventories import sha256  # noqa: E402
from rescore_inventories import MODES, rows_by_id, summarize_run  # noqa: E402

from allfather.eval.metrics import holm  # noqa: E402

PAIRS = (
    ("fresh-full_swerank-embed-large", "fresh-full_website-gpu"),
    ("fresh-full_website", "fresh-full_website-gpu"),
    ("fresh-full-agents_website", "fresh-full-agents_website-gpu"),
    ("fresh-full-agents_website", "fresh-full-agents_codex-agent-astra"),
    ("fresh-full-agents_website", "fresh-full-agents_codex-agent"),
)
VIEWS = ("all", "unique_gold", "issue_deduplicated")


def cluster_p(values: np.ndarray, draws: int, seed: int) -> float:
    values = values[values != 0]
    if not len(values):
        return 1.0
    threshold = abs(values.sum()) - 1e-12
    if len(values) <= 14:
        signs = np.array(list(itertools.product((-1, 1), repeat=len(values))))
        return float(np.mean(np.abs(signs @ values) >= threshold))
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1, 1], size=(draws, len(values)))
    return float((np.count_nonzero(np.abs(signs @ values) >= threshold) + 1) / (draws + 1))


def paired_clusters(a, b, projects, draws: int = 10000, seed: int = 37) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if not len(a) or len(a) != len(b) or len(a) != len(projects):
        raise ValueError("nonempty aligned pairs required")
    names = sorted(set(projects))
    indices = {p: np.array([i for i, name in enumerate(projects) if name == p]) for p in names}
    sizes = np.array([len(indices[p]) for p in names])
    sums = np.array([(b - a)[indices[p]].sum() for p in names])
    means = sums / sizes
    counts = np.random.default_rng(seed).multinomial(
        len(names), np.full(len(names), 1 / len(names)), size=draws
    )
    micro = counts @ sums / (counts @ sizes)
    macro = counts @ means / len(names)
    return {
        "issues": len(a),
        "projects": len(names),
        "a_hits": int(a.sum()),
        "b_hits": int(b.sum()),
        "b_rescues_a": int(np.count_nonzero((a == 0) & (b == 1))),
        "b_harms_a": int(np.count_nonzero((a == 1) & (b == 0))),
        "issue_weighted": {
            "delta_b_minus_a": float((b - a).mean()),
            "project_bootstrap_ci95": np.percentile(micro, [2.5, 97.5]).tolist(),
            "project_sign_flip_p": cluster_p(sums, draws, seed),
        },
        "project_weighted": {
            "delta_b_minus_a": float(means.mean()),
            "project_bootstrap_ci95": np.percentile(macro, [2.5, 97.5]).tolist(),
            "project_sign_flip_p": cluster_p(means, draws, seed),
        },
        "by_project": {
            p: {"issues": int(n), "net_hits": float(s), "delta": float(m)}
            for p, n, s, m in zip(names, sizes, sums, means, strict=True)
        },
    }


def verify_bundle(bundle: Path) -> tuple[dict, dict, dict]:
    folder = bundle / "inventory-rescore-7012506"
    audit = bundle / "inventory-audit-7012218"
    provenance = json.loads((folder / "provenance.json").read_bytes())
    for name, digest in provenance["input_sha256"].items():
        if sha256(ROOT / name) != digest:
            raise ValueError(f"prediction input changed: {name}")
    for name, digest in provenance["source_sha256"].items():
        if sha256(ROOT / name) != digest:
            raise ValueError(f"scoring code changed: {name}")
    for name, digest in provenance["audit_sha256"].items():
        if sha256(audit / name) != digest:
            raise ValueError(f"audit hash mismatch: {name}")
    if sha256(folder / "scores.jsonl") != provenance["scores_sha256"]:
        raise ValueError("scores hash mismatch")
    gold_path = ROOT / "data/fresh-full/gold.jsonl"
    audit_provenance = json.loads((audit / "provenance.json").read_bytes())
    if (
        sha256(gold_path) != provenance["gold_sha256"]
        or sha256(gold_path) != audit_provenance["gold_sha256"]
    ):
        raise ValueError("gold hash mismatch")
    if sha256(audit / "instances.jsonl") != audit_provenance["instances_sha256"]:
        raise ValueError("audit instance hash mismatch")
    manifest = ROOT / "data/fresh-full/manifest.json"
    if sha256(manifest) != provenance["dataset_manifest_sha256"]:
        raise ValueError("dataset manifest hash mismatch")
    gold = {q: r for q, r in rows_by_id(gold_path).items() if r["full_text_status"] == "unchanged"}
    agents = set(json.loads(manifest.read_bytes())["agent_subsample"]) & set(gold)
    summary = json.loads((folder / "summary.json").read_bytes())
    runs = {name: {} for name in summary["runs"]}
    for line in (folder / "scores.jsonl").read_bytes().splitlines():
        row = json.loads(line)
        name, qid = row["run"], row["id"]
        if qid in runs[name]:
            raise ValueError(f"duplicate score row: {name}/{qid}")
        if row["repo"] != gold[qid]["repo"]:
            raise ValueError(f"score/gold project mismatch: {qid}")
        runs[name][qid] = row
    for name, rows in runs.items():
        expected = agents if name.startswith("fresh-full-agents_") else set(gold)
        if (
            set(rows) - expected
            or summarize_run(list(rows.values()), expected) != summary["runs"][name]
        ):
            raise ValueError(f"score summary mismatch: {name}")
    audited = rows_by_id(audit / "instances.jsonl")
    review = json.loads((folder / "review-gold.json").read_bytes())
    if review != [
        r for r in audited.values() if not r["all_gold_unique"] or r["gold_in_parser_error_files"]
    ]:
        raise ValueError("gold review disagrees with audited instances")
    return (
        runs,
        gold,
        {
            "verified_prediction_files": len(provenance["input_sha256"]),
            "verified_run_summaries": len(runs),
            "review_issues": len(review),
            "bundle_sha256": {
                str(p.relative_to(bundle)): sha256(p)
                for p in sorted(bundle.rglob("*"))
                if p.is_file()
            },
        },
    )


def select_ids(ids: list[str], view: str, rows: dict, gold: dict) -> list[str]:
    ids = sorted(ids)
    if view == "unique_gold":
        return [q for q in ids if rows[q]["all_gold_unique"]]
    if view == "issue_deduplicated":
        seen, selected = set(), []
        for q in ids:
            key = (gold[q]["repo"].casefold(), gold[q]["issue"])
            if key not in seen:
                selected.append(q)
                seen.add(key)
        return selected
    return ids


def analyze(bundle: Path, draws: int = 10000, seed: int = 37) -> dict:
    runs, gold, verification = verify_bundle(bundle)
    comparisons, pvalues, headroom = {}, {}, {}
    for mode in MODES:
        for view in VIEWS:
            for a, b in PAIRS:
                common = sorted(set(runs[a]) & set(runs[b]))
                ids = select_ids(common, view, runs[a], gold)
                hits = {
                    name: [runs[name][q]["modes"][mode]["metrics"]["hit@10"] for q in ids]
                    for name in (a, b)
                }
                value = paired_clusters(
                    hits[a], hits[b], [gold[q]["repo"].casefold() for q in ids], draws, seed
                )
                key = f"{mode}/{view}/{b}-minus-{a}"
                comparisons[key] = {
                    "a": a,
                    "b": b,
                    "mode": mode,
                    "view": view,
                    "ids": ids,
                    "excluded_ids": sorted(set(common) - set(ids)),
                    **value,
                }
                for estimand in ("issue_weighted", "project_weighted"):
                    pvalues[f"{key}/{estimand}"] = value[estimand]["project_sign_flip_p"]
            cheap, gpu = "fresh-full-agents_website", "fresh-full-agents_website-gpu"
            for agent in ("codex-agent-astra", "codex-agent"):
                agent = f"fresh-full-agents_{agent}"
                common = sorted(set(runs[cheap]) & set(runs[gpu]) & set(runs[agent]))
                ids = select_ids(common, view, runs[cheap], gold)
                states = {
                    q: tuple(
                        int(runs[name][q]["modes"][mode]["metrics"]["hit@10"])
                        for name in (cheap, gpu, agent)
                    )
                    for q in ids
                }
                counts = Counter("".join(map(str, s)) for s in states.values())
                headroom[f"{mode}/{view}/{agent}"] = {
                    "ids": ids,
                    "state_order": ["browser", "gpu", "agent"],
                    "joint_outcomes": {f"{i:03b}": counts[f"{i:03b}"] for i in range(8)},
                    "oracle_hits": sum(any(s) for s in states.values()),
                    "agent_only_ids": [q for q, s in states.items() if s == (0, 0, 1)],
                    "gpu_only_ids": [q for q, s in states.items() if s == (0, 1, 0)],
                    "both_local_correct_agent_wrong_ids": [
                        q for q, s in states.items() if s == (1, 1, 0)
                    ],
                }
    adjusted = holm(pvalues)
    for key, result in comparisons.items():
        for estimand in ("issue_weighted", "project_weighted"):
            result[estimand]["p_holm"] = adjusted[f"{key}/{estimand}"]
    return {
        "schema": "inventory-paired-analysis-v1",
        "verification": verification,
        "method": {
            "draws": draws,
            "seed": seed,
            "metric": "hit@10",
            "interval": "Percentile paired bootstrap over projects; variable issue count for issue-weighted estimates.",
            "p_value": "Two-sided project sign-flip; exact for at most 14 nonzero projects, otherwise Monte Carlo with plus-one correction.",
            "holm_family": "All 5 comparisons x 2 identity modes x 3 cohort views x 2 estimands (60 tests).",
            "deduplication": "Keep lexicographically first PR ID per (case-normalized repo, issue) within each matched cohort; outcomes unused.",
        },
        "limitations": [
            "Exploratory analysis of exposed results, not preregistered confirmation or an equivalence test.",
            "Intervals are pointwise; sign-flip inference assumes independent projects and exchangeable paired differences under the null.",
            "Oracle headroom sees outcomes and does not establish learnable routing or a cost benefit.",
            "Source snapshot inventories are not in this transferred bundle; their prior audit cannot be independently repeated from it.",
        ],
        "source_sha256": {
            p.relative_to(ROOT).as_posix(): sha256(p)
            for p in (Path(__file__), ROOT / "src/allfather/eval/metrics.py")
        },
        "comparisons": comparisons,
        "headroom": headroom,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    for row in report["comparisons"].values():
        if row["mode"] == "strict_symbol" and row["view"] == "all":
            print(
                row["b"],
                "minus",
                row["a"],
                json.dumps(
                    {
                        k: row[k]
                        for k in (
                            "issues",
                            "projects",
                            "b_rescues_a",
                            "b_harms_a",
                            "issue_weighted",
                            "project_weighted",
                        )
                    }
                ),
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
