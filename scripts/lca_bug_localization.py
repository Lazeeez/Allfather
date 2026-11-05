"""Allfather on Long Code Arena's bug-localization task (ADR 0035).

    uv run python scripts/lca_bug_localization.py rank --lang py --split train
    uv run python scripts/lca_bug_localization.py choose
    uv run python scripts/lca_bug_localization.py rank --lang py --split test
    uv run python scripts/lca_bug_localization.py score

`rank` runs the website's pipeline (browser configuration) on each bug and stores its file ranking,
the answer key, and the test file paired with each top file. On `train` it takes ADR 0035's random
150 bugs per language; on `test` it refuses to run before `choose` has fixed the setting. `choose`
picks k and the test rule on the training bugs by mean F1. `score` applies the chosen setting to the
test bugs, computes the leaderboard's metrics, and writes the answer files for the submission.
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

DATASET = "JetBrains-Research/lca-bug-localization"
CACHE = ROOT / ".cache" / "lca"
OUT = ROOT / "results" / "lca"
EXT = {"py": ".py", "java": ".java"}
SAMPLE = 150
KS = (1, 2, 3, 4, 5)
TESTS = ("off", "paired")
KEEP = 20


def bugs(lang: str, split: str) -> list[dict]:
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        DATASET, f"{lang}/{split}-00000-of-00001.parquet", repo_type="dataset", local_dir=CACHE
    )
    rows = pq.read_table(path).to_pylist()
    if split == "train":
        rows = random.Random(0).sample(sorted(rows, key=lambda r: r["text_id"]), SAMPLE)
    return rows


def test_names(path: str, lang: str) -> list[str]:
    stem = Path(path).stem
    if lang == "py":
        return [f"test_{stem}.py", f"{stem}_test.py"]
    return [f"{stem}Test.java", f"{stem}Tests.java", f"Test{stem}.java"]


def paired_test(path: str, lang: str, files: list[str]) -> str | None:
    names = set(test_names(path, lang))
    found = [f for f in files if f.rsplit("/", 1)[-1] in names and f != path]
    if not found:
        return None
    folder = path.rsplit("/", 1)[0].split("/") if "/" in path else []

    def shared(f: str) -> int:
        parts = f.rsplit("/", 1)[0].split("/") if "/" in f else []
        n = 0
        for a, b in zip(folder, parts, strict=False):
            if a != b:
                break
            n += 1
        return n

    return sorted(found, key=lambda f: (-shared(f), f))[0]


def log_test_run(lang: str, target: Path) -> None:
    from datetime import UTC, datetime

    log = ROOT / "results" / "test-evals.log"
    rel = target.relative_to(ROOT).as_posix()
    if f"| {rel} |" in log.read_text(encoding="utf-8"):
        return
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"{datetime.now(UTC).date().isoformat()} | lca-{lang}-test | website (website pipeline, browser configuration) | file | {rel} | "
            "ADR 0035 run on Long Code Arena's test split, once, with the setting chosen on train\n"
        )


def cmd_rank(lang: str, split: str) -> int:
    from live_eval import Site

    from allfather.eval.dataset import Instance

    target = OUT / f"{lang}_{split}_ranked.jsonl"
    if split == "test":
        if not (OUT / "choice.json").exists():
            sys.exit("run choose on the training bugs first (ADR 0035)")
        if not target.exists():
            log_test_run(lang, target)
    OUT.mkdir(parents=True, exist_ok=True)
    done = (
        {json.loads(line)["text_id"] for line in target.open(encoding="utf-8")}
        if target.exists()
        else set()
    )
    site = Site()
    cache = site.snaps.r.indexer.cache
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        for r in bugs(lang, split):
            if r["text_id"] in done:
                continue
            repo = f"{r['repo_owner']}/{r['repo_name']}"
            text = f"{r['issue_title']}\n\n{r['issue_body'] or ''}"
            record = {"text_id": r["text_id"], "repo": repo, "base_sha": r["base_sha"],
                      "gold": sorted(ast.literal_eval(r["changed_files"]))}  # fmt: skip
            try:
                inst = Instance(r["text_id"], repo, r["base_sha"], "", text)
                ranked, files, units = site.rank(inst, set(), set())
                every = cache.list_files(repo, r["base_sha"])
                code = [f for f in every if f.endswith(EXT[lang])]
                record |= {
                    "files": files[:KEEP],
                    "units": units,
                    "language_files": len(code),
                    "tests": {f: paired_test(f, lang, code) for f in files[: max(KS)]},
                }
            except Exception as exc:  # noqa: BLE001
                record["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            print(f"  {r['text_id']}: {len(record.get('files', []))} files"
                  f"{', ' + record['error'] if 'error' in record else ''}", flush=True)  # fmt: skip
    site.close()
    return 0


def answer(record: dict, k: int, tests: str) -> list[str]:
    top = record.get("files", [])[:k]
    out = list(top)
    if tests == "paired":
        for f in top:
            t = record.get("tests", {}).get(f)
            if t and t not in out:
                out.append(t)
    return out


def metrics(record: dict, predicted: list[str]) -> dict:
    expected, actual = set(record["gold"]), set(predicted)
    tp, fp, fn = len(expected & actual), len(actual - expected), len(expected - actual)
    negatives = max(record.get("language_files", 0) - len(expected | actual), 0)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {
        "P": p,
        "R": r,
        "F1-score": 2 * p * r / (p + r) if p + r else 0.0,
        "FPR": fp / (fp + negatives) if fp + negatives else 0.0,
        "All_correct": float(actual == expected),
        "All_incorrect": float(not (expected & actual) and len(actual) > 0),
        "Output_count": float(len(actual)),
    }


def mean(rows: list[dict]) -> dict:
    return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in rows[0]} if rows else {}


def records(lang: str, split: str) -> list[dict]:
    path = OUT / f"{lang}_{split}_ranked.jsonl"
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def cmd_choose() -> int:
    target = OUT / "choice.json"
    if target.exists():
        sys.exit(f"{target} exists: the setting is fixed (ADR 0035)")
    out = {
        "rule": "highest mean F1 on 150 random train bugs; ties to smaller k, then off",
        "languages": {},
    }
    for lang in EXT:
        rs = records(lang, "train")
        grid = {
            f"k={k},tests={t}": mean([metrics(r, answer(r, k, t)) for r in rs])
            for k in KS
            for t in TESTS
        }
        best = max(
            ((k, t) for k in KS for t in TESTS),
            key=lambda s: (grid[f"k={s[0]},tests={s[1]}"]["F1-score"], -s[0], s[1] == "off"),
        )
        out["languages"][lang] = {
            "bugs": len(rs),
            "errors": sum("error" in r for r in rs),
            "k": best[0],
            "tests": best[1],
            "grid": grid,
        }
        print(lang, "chose", best, grid[f"k={best[0]},tests={best[1]}"])
    target.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


def hit_at(record: dict, k: int) -> float:
    return float(bool(set(record.get("files", [])[:k]) & set(record["gold"])))


def cmd_score() -> int:
    choice = json.loads((OUT / "choice.json").read_text(encoding="utf-8"))["languages"]
    familiar = {
        k.lower()
        for k in json.loads((ROOT / "data/fresh/excluded.json").read_text(encoding="utf-8"))
    }
    report, every, unseen = {"choice": choice, "languages": {}}, [], []
    for lang in EXT:
        c = choice[lang]
        rs = records(lang, "test")
        scored = []
        answers = OUT / f"submission_{lang}_test.jsonl"
        with answers.open("w", encoding="utf-8", newline="\n") as handle:
            for r in rs:
                predicted = answer(r, c["k"], c["tests"])
                m = metrics(r, predicted)
                scored.append(m)
                every.append(m)
                if r["repo"].lower() not in familiar:
                    unseen.append(m)
                handle.write(
                    json.dumps(
                        {
                            "text_id": r["text_id"],
                            "json_completion": json.dumps({"files": predicted}),
                        }
                    )
                    + "\n"
                )
        report["languages"][lang] = {
            "bugs": len(rs),
            "errors": sum("error" in r for r in rs),
            "metrics": mean(scored),
            "file_hit@1": round(sum(hit_at(r, 1) for r in rs) / len(rs), 4),
            "file_hit@5": round(sum(hit_at(r, 5) for r in rs) / len(rs), 4),
        }
    report["both"] = {"bugs": len(every), "metrics": mean(every)}
    report["both_unfamiliar_projects"] = {"bugs": len(unseen), "metrics": mean(unseen)}
    target = OUT / "test.json"
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k != "choice"}, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["rank", "choose", "score"])
    ap.add_argument("--lang", choices=list(EXT))
    ap.add_argument("--split", choices=["train", "test"])
    args = ap.parse_args()
    if args.step == "rank":
        if not args.lang or not args.split:
            sys.exit("rank needs --lang and --split")
        return cmd_rank(args.lang, args.split)
    return cmd_choose() if args.step == "choose" else cmd_score()


if __name__ == "__main__":
    raise SystemExit(main())
