"""E3 of ADR 0033: how much of each system's SWE-bench Lite score comes from reports that name the fix?

    uv run python scripts/e3_hint_strata.py

Descriptive only. Re-scores rankings already stored in results/ against Allfather's function-level
answer key, split by what the report says about the fix:

- function: it names a function the fix changes (its bare name, as a whole word)
- file: it names a file the fix changes (its path or file name), but no fixed function
- trace: it has a traceback, but names neither
- none: it names nothing the fix touches

No system is run and nothing is decided from this. Writes results/research/e3_hint_strata.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from allfather.eval.dataset import load_instances
from allfather.eval.metrics import bootstrap_ci, score
from allfather.eval.provenance import provenance

OUT = Path("results/research/e3_hint_strata.json")
STRATA = ("function", "file", "trace", "none")
ALLFATHER = {
    "BM25, naive tokens": "results/bm25-naive_function_lite_test.json",
    "BM25, code-aware": "results/bm25-code-notests_function_lite_test.json",
    "Hybrid": "results/hybrid-notests_function_lite_test.json",
    "Learning to rank": "results/ltr-notests_function_lite_test.json",
    "ltr-ce-notests": "results/ltr-ce-notests_function_lite_test.json",
    "allfather-fast (frozen)": "results/frozen/allfather-fast_function_lite.json",
}
SWERANK = {
    "SweRankEmbed-Small": "results/reproductions/swerank-embed-small_lite_2026-10-14.json",
    "SweRankEmbed-Large": "results/reproductions/swerank-embed-large_lite_2026-10-14.json",
    "SweRankLLM-Small": "results/reproductions/swerank-llm-small_lite_2026-10-14.json",
    "SweRankLLM-Large": "results/reproductions/swerank-llm-large_lite_2026-10-14.json",
}
TRACEBACK = re.compile(r"Traceback \(most recent call last\)|^\s+File \"[^\"]+\", line \d+", re.M)


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
    return "trace" if TRACEBACK.search(text) else "none"


def swerank_id(unit: str) -> str:
    path, qual = unit.split("::", 1)
    return f"{path}/{qual.replace('.', '/')}"


def main() -> int:
    text = {i.instance_id: i.problem_statement for i in load_instances("lite", "test")}
    reference = json.loads(Path(ALLFATHER["ltr-ce-notests"]).read_text(encoding="utf-8"))
    gold = {r["instance_id"]: r["gold"] for r in reference["per_instance"]}
    strata = {q: stratum(text[q], g) for q, g in gold.items()}
    rankings: dict[str, dict[str, list[str]]] = {}
    for name, path in ALLFATHER.items():
        rows = json.loads(Path(path).read_text(encoding="utf-8"))["per_instance"]
        rankings[name] = {r["instance_id"]: r["ranked"] for r in rows}
    for name, path in SWERANK.items():
        rankings[name] = json.loads(Path(path).read_text(encoding="utf-8"))["rankings"]

    report: dict = {
        "adr": "docs/decisions/0033-frontier-comparison-protocol.md",
        "experiment": "E3",
        "note": "SweRank rankings are scored against Allfather's answer key on the issues they cover, not the LocAgent labels their paper uses",
        "strata": {s: sum(1 for v in strata.values() if v == s) for s in STRATA},
        "systems": {},
    }
    for name, ranked in rankings.items():
        is_swerank = name in SWERANK
        entry = {}
        for s in (*STRATA, "all"):
            qs = [q for q in gold if (s == "all" or strata[q] == s) and q in ranked]
            target = {q: [swerank_id(g) for g in gold[q]] if is_swerank else gold[q] for q in qs}
            scores = [score(ranked[q][:10], target[q], [1, 5, 10]) for q in qs]
            if not scores:
                continue
            hit10 = np.mean([x.hit[10] for x in scores])
            entry[s] = {
                "issues": len(qs),
                "hit@10": round(float(hit10), 4),
                "hit@10_ci95": bootstrap_ci(scores, "hit@10"),
                "hit@1": round(float(np.mean([x.hit[1] for x in scores])), 4),
            }
        report["systems"][name] = entry
        print(
            f"{name:26}",
            "  ".join(
                f"{s} {entry[s]['hit@10']:.3f} (n={entry[s]['issues']})"
                for s in (*STRATA, "all")
                if s in entry
            ),
        )
    report["provenance"] = provenance()
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("strata:", report["strata"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
