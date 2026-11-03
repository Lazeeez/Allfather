"""Step 2 of ADR 0034: train and cross-validate reranker candidates on all six languages.

    uv run python scripts/ce_multilang.py records
    uv run python scripts/ce_multilang.py train --candidate B --fold 0     # on PACE, one job per fold
    uv run python scripts/ce_multilang.py score --candidate B --fold 0
    uv run python scripts/website_rerank.py evaluate --multilang --name cand-B
    uv run python scripts/website_rerank.py evaluate --name cand-B         # the Python tasks

records: training examples from the reranker tasks of ADR 0021 (Python) and ADR 0034 (the five
other languages): each bug's query, the source of every function its fix changed, and its hard
negatives, the website pipeline's out-of-fold top 50 minus the fix. folds: five folds that keep
each project whole. train: one candidate (A, B or C, as ADR 0034 defines them) on four folds.
score: that candidate's adapter on the held-out fold's tasks, appended to the scores file the
evaluation reads. `--fold all` trains the final adapter on every project.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from allfather.index.chunker import MODULE, chunk_file  # noqa: E402
from allfather.index.snapshot import unit_text  # noqa: E402
from allfather.rank.ltr import project_folds  # noqa: E402
from allfather.repos import RepoCache  # noqa: E402

WORK = ROOT / "results" / "website-rerank" / "work"
TASK_FILES = [WORK / "tasks.jsonl", WORK / "tasks_multilang.jsonl"]
RECORDS = WORK / "ce_records.jsonl"
GOLD = [
    ROOT / "data" / "gold" / n
    for n in ("swebench_full_test.jsonl", "swebench_rebench_train.jsonl", "multilang_train.jsonl")
]
MODELS = ROOT / "models" / "ce_multi"
FOLDS = 5
CANDIDATES = {
    "A": {"base": "Qwen/Qwen3-Reranker-0.6B", "group": 8, "epochs": 1, "balanced": False},
    "B": {"base": "Qwen/Qwen3-Reranker-0.6B", "group": 16, "epochs": 2, "balanced": True},
    "C": {"base": "Qwen/Qwen3-Reranker-4B", "group": 16, "epochs": 2, "balanced": True},
}


def tasks() -> list[dict]:
    out = []
    for path in TASK_FILES:
        out += [json.loads(line) for line in path.open(encoding="utf-8")]
    return [t for t in out if t["gold"] and t["ids"]]


def commits() -> dict[str, str]:
    found = {}
    for path in GOLD:
        for line in path.open(encoding="utf-8"):
            row = json.loads(line)
            found[row["instance_id"]] = row["base_commit"]
    return found


def gold_texts(cache: RepoCache, repo: str, commit: str, units: list[str]) -> list[str]:
    by_file: dict[str, set[str]] = {}
    for u in units:
        path, qual = u.split("::", 1)
        by_file.setdefault(path, set()).add(qual)
    texts = []
    for path, quals in sorted(by_file.items()):
        try:
            source = cache.read_file(repo, commit, path)
        except Exception:  # noqa: BLE001
            continue
        texts += [
            unit_text(c.qualname, c.text)
            for c in chunk_file(source, path)
            if c.kind != MODULE and c.qualname in quals
        ]
    return texts


def cmd_records(_: argparse.Namespace) -> int:
    base = commits()
    cache = RepoCache(ROOT / ".cache" / "repos")
    with RECORDS.open("w", encoding="utf-8", newline="\n") as handle:
        for n, t in enumerate(tasks(), 1):
            gold = set(t["gold"])
            pos = gold_texts(cache, t["repo"], base[t["qid"]], sorted(gold))
            neg = [text for u, text in zip(t["ids"], t["texts"], strict=False) if u not in gold]
            record = {
                "qid": t["qid"],
                "repo": t["repo"],
                "language": t.get("language", "python"),
                "query": t["query"],
                "pos": pos,
                "neg": neg,
            }
            handle.write(json.dumps(record) + "\n")
            if n % 250 == 0:
                print(n, flush=True)
    print(f"wrote {RECORDS}")
    return 0


def fold_of() -> dict[str, int]:
    rows = tasks()
    qids = [f"{t['repo']}-{i}" for i, t in enumerate(rows)]
    out = {}
    for k, (_, test) in enumerate(project_folds(qids, FOLDS)):
        for i in test:
            out[rows[i]["repo"]] = k
    return out


def balanced(records: list[dict], epochs: int, seed: int) -> list[dict]:
    by_lang: dict[str, list[dict]] = {}
    for r in records:
        by_lang.setdefault(r["language"], []).append(r)
    weights = {lang: math.sqrt(len(rs)) for lang, rs in by_lang.items()}
    total = sum(weights.values())
    rng = random.Random(seed)
    draws = epochs * len(records)
    out = []
    for lang, rs in sorted(by_lang.items()):
        n = round(draws * weights[lang] / total)
        out += [rs[rng.randrange(len(rs))] for _ in range(n)]
    return out


def cmd_train(args: argparse.Namespace) -> int:
    from allfather.rank.ce_train import train_cross_encoder

    cand = CANDIDATES[args.candidate]
    folds = fold_of()
    records = [json.loads(line) for line in RECORDS.open(encoding="utf-8")]
    if args.fold != "all":
        records = [r for r in records if folds[r["repo"]] != int(args.fold)]
    records = [r for r in records if r["pos"] and r["neg"]]
    epochs = cand["epochs"]
    if cand["balanced"]:
        records, epochs = (
            balanced(records, epochs, seed=int(args.fold) if args.fold != "all" else 99),
            1,
        )
    print(
        f"candidate {args.candidate}, fold {args.fold}: {len(records)} examples, {dict(Counter(r['language'] for r in records))}",
        flush=True,
    )
    out = MODELS / args.candidate / f"fold{args.fold}"
    train_cross_encoder(records, out, epochs=epochs, group=cand["group"], base=cand["base"], seed=0)
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    from allfather.rank.cross_encoder import CrossEncoder

    folds = fold_of()
    target = WORK / f"scores_cand-{args.candidate}.jsonl"
    done = (
        {json.loads(line)["qid"] for line in target.open(encoding="utf-8")}
        if target.exists()
        else set()
    )
    model = CrossEncoder(
        adapter=MODELS / args.candidate / f"fold{args.fold}",
        base=CANDIDATES[args.candidate]["base"],
    )
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        for t in tasks():
            if folds[t["repo"]] != int(args.fold) or t["qid"] in done:
                continue
            handle.write(
                json.dumps(
                    {"qid": t["qid"], "scores": [model.score(t["query"], t["texts"]).tolist()]}
                )
                + "\n"
            )
            handle.flush()
    print(f"scored fold {args.fold} into {target}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("records")
    for name in ("train", "score"):
        sp = sub.add_parser(name)
        sp.add_argument("--candidate", required=True, choices=sorted(CANDIDATES))
        sp.add_argument("--fold", required=True)
    args = ap.parse_args()
    return {"records": cmd_records, "train": cmd_train, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
