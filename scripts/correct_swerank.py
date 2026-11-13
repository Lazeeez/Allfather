"""Recover saved identifiers without inference; preserve the original evidence (ADR 0037).

Run with --out results/research/corrections/import-v1. The destination must not exist.
The legacy scorer is retained explicitly to isolate import damage; exact-ID metrics are
also reported. Neither is a substitute for the planned complete-inventory resolver.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from fresh_analysis import METRICS, file_hits, languages, project_ci, stratum  # noqa: E402
from frontier import OUT, load_set, matched, unit_ids  # noqa: E402
from swerank_export import swerank_id  # noqa: E402
from swerank_import import split_id  # noqa: E402

from allfather.eval.metrics import holm, paired_bootstrap, score  # noqa: E402

VERSION = "swerank-import-v1"


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def recover(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    corrected, changes = copy.deepcopy(rows), []
    for row in corrected:
        for slot, prediction in enumerate((row.get("answer") or {}).get("functions", []), 1):
            if prediction.get("name") or not isinstance(prediction.get("file"), str):
                continue
            old = prediction["file"]
            new = split_id(old)
            if not new["name"]:
                continue
            if swerank_id(new["file"], new["name"]) != old:
                raise ValueError(f"identifier does not round-trip: {old}")
            changes.append({"id": row["id"], "slot": slot, "original": old, "recovered": new})
            prediction.update(new)
    return corrected, changes


def outcomes(rows: list[dict], items: dict, legacy: bool) -> dict:
    out = {}
    for row in rows:
        q = row["id"]
        if q in out:
            raise ValueError(f"duplicate result: {q}")
        gold = items[q]["gold"]
        if not gold:
            continue
        ranked = unit_ids(row.get("answer"))
        s = score(matched(ranked, gold) if legacy else ranked, gold, [1, 5, 10])
        out[q] = {
            **{f"hit@{k}": s.hit[k] for k in (1, 5, 10)},
            **{f"recall@{k}": s.recall[k] for k in (1, 5, 10)},
            "all@10": s.full[10],
            "mrr": s.rr,
        }
    return out


def means(values: dict) -> dict:
    if not values:
        return {"issues": 0}
    return {
        "issues": len(values),
        **{
            key: float(np.mean([v[key] for v in values.values()]))
            for key in next(iter(values.values()))
        },
    }


def paired(runs: dict, items: dict, reference: str) -> dict:
    report, pvalues = {}, {}
    for system, run in runs.items():
        if system == reference:
            continue
        ids = sorted(set(run) & set(runs[reference]))
        if not ids:
            continue
        for metric in METRICS:
            a = np.array([runs[reference][q][metric] for q in ids])
            b = np.array([run[q][metric] for q in ids])
            d = paired_bootstrap(a, b)
            key = f"{system}:{metric}"
            report[key] = {
                "ids": ids,
                "issues": len(ids),
                "delta_system_minus_reference": float((b - a).mean()),
                "issue_bootstrap_ci95": d.ci95,
                "project_bootstrap_ci95": project_ci(
                    b - a, np.array([items[q]["repo"] for q in ids])
                ),
                "p_issue_paired": d.p_value,
                "wins": d.wins,
                "losses": d.losses,
            }
            pvalues[key] = d.p_value
    for key, value in holm(pvalues).items():
        report[key]["p_holm"] = value
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("destination exists; use a new correction namespace")
    inputs = sorted(OUT.glob("fresh*_*swerank*.jsonl"))
    if not inputs:
        parser.error("no saved SweRank runs")
    report = {
        "version": VERSION,
        "base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "scope": "Import-only correction, no inference; legacy gold-dependent scoring and exact sensitivity.",
        "limitations": [
            "Original fresh SweRank corpus membership not verified by this script; syntactic round trips only.",
            "Exact sensitivity retains historical unit_ids filtering; invalid-slot handling is not repaired here.",
            "Legacy scoring is gold-dependent; complete candidate inventory resolution remains required.",
            "Costs, inference source coverage, human annotations and benchmark labels are not repaired here.",
        ],
        "inputs_sha256": {},
        "code_sha256": {},
        "runs": {},
        "comparisons": {},
    }
    for path in (
        Path(__file__),
        ROOT / "scripts/swerank_import.py",
        ROOT / "scripts/frontier.py",
        ROOT / "scripts/fresh_analysis.py",
        ROOT / "src/allfather/parsing/symbols.py",
        ROOT / "src/allfather/eval/metrics.py",
    ):
        report["code_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    staged = {}
    for path in inputs:
        set_name, system = path.stem.split("_", 1)
        ids, items = load_set(set_name)
        before = read_rows(path)
        after, changes = recover(before)
        staged[path.name] = after
        report["inputs_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        legacy = outcomes(after, items, True)
        langs = languages(set_name)
        report["runs"][path.stem] = {
            "set": set_name,
            "system": system,
            "expected_instances": len(ids),
            "changed_predictions": len(changes),
            "changed_instances": len({c["id"] for c in changes}),
            "changes": changes,
            "before_legacy": means(outcomes(before, items, True)),
            "after_legacy": means(legacy),
            "after_exact_sensitivity": means(outcomes(after, items, False)),
            "before_file": means(file_hits(before, items)),
            "after_file": means(file_hits(after, items)),
            "by_language_after_legacy": {
                lang: means({q: v for q, v in legacy.items() if langs.get(q) == lang})
                for lang in sorted(set(langs.values()))
            },
            "by_hint_after_legacy": {
                hint: means(
                    {
                        q: v
                        for q, v in legacy.items()
                        if stratum(items[q]["text"], items[q]["gold"]) == hint
                    }
                )
                for hint in ("function", "file", "trace", "none")
            },
        }
    for set_name in sorted({p.stem.split("_", 1)[0] for p in inputs}):
        _, items = load_set(set_name)
        runs = {}
        for path in sorted(OUT.glob(f"{set_name}_*.jsonl")):
            system = path.stem[len(set_name) + 1 :]
            if system == "website-files" or path.name.endswith(".errors.jsonl"):
                continue
            report["inputs_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            runs[system] = outcomes(staged.get(path.name, read_rows(path)), items, True)
        report["comparisons"][set_name] = {
            "reference": "website-gpu",
            "rule": "legacy scoring, all systems x five metrics; issue-weighted means",
            "paired": paired(runs, items, "website-gpu"),
            "coverage": {
                s: {"ids": sorted(run), "projects": dict(Counter(items[q]["repo"] for q in run))}
                for s, run in runs.items()
            },
        }
    # Do all computations before publishing a new directory. Never touch historical files.
    args.out.mkdir(parents=True)
    for name, rows in staged.items():
        with (args.out / name).open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.out / "audit.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for name, run in report["runs"].items():
        print(
            f"{name}: {run['before_legacy']['hit@10']:.6f} -> {run['after_legacy']['hit@10']:.6f}; {run['changed_predictions']} repaired identifiers"
        )
    print(f"wrote {args.out}; legacy comparison remains provisional")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
