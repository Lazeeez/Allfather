import argparse
import dataclasses
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import browser_ltr as bl  # noqa: E402

from allfather.eval.metrics import (  # noqa: E402
    aggregate,
    holm,
    mcnemar_exact,
    metric_values,
    paired_bootstrap,
    score,
)
from allfather.eval.provenance import provenance  # noqa: E402

OUT = ROOT / "results" / "website-rerank"
WORK = OUT / "work"
TASKS = WORK / "tasks.jsonl"
DEPTHS = (20, 50)
WEIGHTS = (0.25, 0.5, 1.0, 2.0, 4.0, float("inf"))
KS = (1, 5, 10)
KEEP = 100
SEED = 0


def website_orders(train: list, snaps) -> list[list[str]]:
    splits = bl.repo_folds(train)
    n_gold = [len(it.targets) for it in train]
    X, Y, _ = bl.stage_rows(train, "b")
    _, oof_b, _ = bl.cv_items(train, X, Y, n_gold, splits)
    embed = bl.make_embedder()
    bl.pass2(train, oof_b, snaps, embed, "train")
    embed.save()
    XC = [it.xc for it in train]
    YC = [
        np.array(
            [u in it.targets for u in (bl.unit_ids(it, it.rows_b[it.sel]) if len(it.sel) else [])],
            np.float32,
        )
        for it in train
    ]
    _, oof_c, _ = bl.cv_items(train, XC, YC, n_gold, splits)
    orders = [bl.reranked(it, sb, sc) for it, sb, sc in zip(train, oof_b, oof_c, strict=True)]
    print(
        "website, out of fold, all training issues:",
        bl.fmt(bl.metrics(orders, [it.targets for it in train])),
    )
    return orders


def use_multilang() -> None:
    global TASKS
    bl.MULTILANG = True
    bl.CACHE = Path(".cache/browser_ltr_multilang")
    bl.TRAIN["multilang"] = ("multilang", "train", [])
    TASKS = WORK / "tasks_multilang.jsonl"


def build_tasks() -> int:
    if TASKS.exists():
        sys.exit(f"{TASKS} exists")
    sys.modules["__main__"].Item = bl.Item
    snaps = bl.Snapshots()
    parts = {name: bl.build(name, spec, snaps) for name, spec in bl.TRAIN.items()}
    train = [it for part in parts.values() for it in part]
    orders = website_orders(train, snaps)
    rebench = {it.qid for it in parts["multilang" if bl.MULTILANG else "rebench"]}
    WORK.mkdir(parents=True, exist_ok=True)
    written = 0
    with TASKS.open("w", encoding="utf-8", newline="\n") as handle:
        for it, order in zip(train, orders, strict=True):
            if it.qid not in rebench:
                continue
            fn, _, _ = snaps.get(it.repo, it.commit)
            row_of = dict(zip(bl.unit_ids(it, it.rows_b), it.rows_b.tolist(), strict=True))
            ids = order[:KEEP]
            texts = snaps.r.indexer.unit_texts(fn, [row_of[u] for u in ids[: max(DEPTHS)]])
            handle.write(
                json.dumps(
                    {
                        "qid": it.qid,
                        "repo": it.repo,
                        "query": it.text,
                        "ids": ids,
                        "ranker_scores": (-np.log1p(np.arange(1, len(ids) + 1))).tolist(),
                        "texts": texts,
                        "gold": sorted(it.targets),
                        "language": bl.LANG_OF.get(it.qid, "python"),
                    }
                )
                + "\n"
            )
            written += 1
    snaps.close()
    print(
        f"wrote {TASKS}: {written} issues from {len({it.repo for it in parts['rebench']})} projects"
    )
    return 0


def z(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / x.std() if len(x) and x.std() > 0 else np.zeros_like(x)


def blended(task: dict, members: list[list[float]], depth: int, weight: float) -> list[str]:
    n = min(depth, len(task["ids"]), len(members[0]))
    ce = np.mean([z(np.asarray(s[:n], float)) for s in members], axis=0)
    base = z(np.asarray(task["ranker_scores"][:n], float))
    combined = ce if np.isinf(weight) else base + weight * ce
    head = [task["ids"][i] for i in np.argsort(-combined, kind="stable")]
    return head + task["ids"][n:]


def scored(tasks: list[dict], raw: dict, setting) -> list:
    out = []
    for t in tasks:
        ranked = t["ids"] if setting is None else blended(t, raw[t["qid"]], *setting)
        out.append(score(ranked[:10], t["gold"], KS))
    return out


def evaluate(name: str) -> int:
    tasks = [json.loads(line) for line in TASKS.open(encoding="utf-8")]
    tasks = [t for t in tasks if t["gold"] and t["ids"]]
    raw = {
        r["qid"]: r["scores"]
        for r in map(json.loads, (WORK / f"scores_{name}.jsonl").open(encoding="utf-8"))
    }
    missing = [t["qid"] for t in tasks if t["qid"] not in raw]
    if missing:
        sys.exit(f"{len(missing)} issues have no scores, e.g. {missing[:3]}")
    repos = sorted({t["repo"] for t in tasks})
    half = set(
        np.asarray(repos)[np.random.default_rng(SEED).permutation(len(repos))[: len(repos) // 2]]
    )
    halves = [[t for t in tasks if t["repo"] in half], [t for t in tasks if t["repo"] not in half]]
    grid = [(d, w) for d in DEPTHS for w in WEIGHTS]
    report: dict = {"issues": len(tasks), "projects": len(repos), "halves": []}
    pooled_base, pooled_cand = [], []
    for k in (0, 1):
        choose_on, apply_to = halves[k], halves[1 - k]
        hits = {s: aggregate(scored(choose_on, raw, s), KS)["hit@10"] for s in grid}
        best = max(grid, key=lambda s: (hits[s], -s[0]))
        base, cand = scored(apply_to, raw, None), scored(apply_to, raw, best)
        pooled_base += base
        pooled_cand += cand
        report["halves"].append(
            {
                "chosen_on_projects": len({t["repo"] for t in choose_on}),
                "applied_to_issues": len(apply_to),
                "setting": [best[0], None if np.isinf(best[1]) else best[1]],
                "grid_hit@10_on_choosing_half": {
                    f"{d}/{w}": round(v, 4) for (d, w), v in hits.items()
                },
                "website": aggregate(base, KS),
                "with_reranker": aggregate(cand, KS),
            }
        )
    report["pooled"] = {
        "website": aggregate(pooled_base, KS),
        "with_reranker": aggregate(pooled_cand, KS),
        "paired": {
            m: dataclasses.asdict(
                paired_bootstrap(metric_values(pooled_base, m), metric_values(pooled_cand, m))
            )
            for m in ("hit@10", "hit@1", "hit@5", "mrr", "recall@10", "all@10")
        },
    }
    by_language: dict[str, list[int]] = {}
    for i, t in enumerate([t for k in (0, 1) for t in halves[1 - k]]):
        by_language.setdefault(t.get("language", "python"), []).append(i)
    report["by_language"] = {}
    for lang, idx in sorted(by_language.items()):
        b = [pooled_base[i].hit[10] for i in idx]
        c = [pooled_cand[i].hit[10] for i in idx]
        wins = sum(1 for x, y in zip(b, c, strict=True) if y > x)
        losses = sum(1 for x, y in zip(b, c, strict=True) if x > y)
        report["by_language"][lang] = {
            "issues": len(idx),
            "website_hit@10": round(float(np.mean(b)), 4),
            "with_reranker_hit@10": round(float(np.mean(c)), 4),
            "gain": round(float(np.mean(c) - np.mean(b)), 4),
            "wins": wins,
            "losses": losses,
            "p_exact": round(mcnemar_exact(wins, losses), 6),
        }
    adjusted = holm({k: v["p_exact"] for k, v in report["by_language"].items()})
    for lang, row in report["by_language"].items():
        row["p_holm"] = adjusted[lang]
        row["passes_adr_0034"] = bool(row["gain"] >= 0.02 and row["p_holm"] < 0.05)
    gain = report["pooled"]["paired"]["hit@10"]
    report["decision"] = {
        "rule": "build the server if pooled function hit@10 improves by >= 0.020 with p < 0.05",
        "met": bool(gain["delta"] >= 0.02 and gain["p_value"] < 0.05),
    }
    report["provenance"] = provenance()
    target = OUT / f"server_reranker_{name}.json"
    if target.exists():
        sys.exit(f"{target} exists")
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps({k: v for k, v in report.items() if k not in ("provenance", "halves")}, indent=1)
    )
    for h in report["halves"]:
        print(
            "setting",
            h["setting"],
            "website",
            round(h["website"]["hit@10"], 4),
            "with reranker",
            round(h["with_reranker"]["hit@10"], 4),
        )
    return 0


SEMANTIC_ORDERS = WORK / "semantic_orders.jsonl"


def semantic_orders() -> int:
    if SEMANTIC_ORDERS.exists():
        sys.exit(f"{SEMANTIC_ORDERS} exists")
    sys.modules["__main__"].Item = bl.Item
    snaps = bl.Snapshots()
    parts = {name: bl.build(name, spec, snaps) for name, spec in bl.TRAIN.items()}
    train = parts["swe-bench"] + parts["rebench"]
    rebench = {it.qid for it in parts["rebench"]}
    splits = bl.repo_folds(train)
    n_gold = [len(it.targets) for it in train]
    X, Y, _ = bl.stage_rows(train, "b")
    _, oof_b, _ = bl.cv_items(train, X, Y, n_gold, splits)
    with SEMANTIC_ORDERS.open("w", encoding="utf-8", newline="\n") as handle:
        for it, sb in zip(train, oof_b, strict=True):
            if it.qid in rebench:
                ids = bl.unit_ids(it, it.rows_b)
                order = [ids[i] for i in bl.order(sb)] if len(sb) else []
                handle.write(json.dumps({"qid": it.qid, "ids": order[:KEEP]}) + "\n")
    snaps.close()
    print(f"wrote {SEMANTIC_ORDERS}")
    return 0


def skip_language_model(name: str) -> int:
    depth, weight = 50, 1.0
    tasks = [json.loads(line) for line in TASKS.open(encoding="utf-8")]
    tasks = [t for t in tasks if t["gold"] and t["ids"]]
    raw = {
        r["qid"]: r["scores"]
        for r in map(json.loads, (WORK / f"scores_{name}.jsonl").open(encoding="utf-8"))
    }
    semantic = {r["qid"]: r["ids"] for r in map(json.loads, SEMANTIC_ORDERS.open(encoding="utf-8"))}
    differ = [t["qid"] for t in tasks if set(semantic[t["qid"]][:depth]) != set(t["ids"][:depth])]
    if differ:
        sys.exit(f"{len(differ)} issues have different top {depth}s, e.g. {differ[:3]}")
    base, cand = [], []
    for t in tasks:
        base.append(score(blended(t, raw[t["qid"]], depth, weight)[:10], t["gold"], KS))
        n = min(depth, len(t["ids"]), len(raw[t["qid"]][0]))
        by_id = {u: [s[i] for s in raw[t["qid"]]] for i, u in enumerate(t["ids"][:n])}
        order = semantic[t["qid"]]
        members = [[by_id[u][m] for u in order[:n]] for m in range(len(raw[t["qid"]]))]
        swapped = {**t, "ids": order}
        cand.append(score(blended(swapped, members, depth, weight)[:10], t["gold"], KS))
    paired = {
        m: dataclasses.asdict(paired_bootstrap(metric_values(base, m), metric_values(cand, m)))
        for m in ("hit@10", "hit@1", "hit@5", "mrr", "recall@10")
    }
    gain = paired["hit@10"]
    report = {
        "issues": len(tasks),
        "projects": len({t["repo"] for t in tasks}),
        "setting": [depth, weight],
        "same_top_50": True,
        "gpu_over_language_model_order": aggregate(base, KS),
        "gpu_over_semantic_order": aggregate(cand, KS),
        "paired": paired,
        "decision": {
            "rule": "skip the language model if hit@10 loss <= 0.005 and the 95% interval's loss end < 0.010",
            "met": bool(gain["delta"] >= -0.005 and gain["ci95"][0] > -0.010),
        },
        "provenance": provenance(),
    }
    target = OUT / f"skip_language_model_{name}.json"
    if target.exists():
        sys.exit(f"{target} exists")
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k != "provenance"}, indent=1))
    return 0


HELD_OUT = WORK / "tasks_heldout.jsonl"
HELD_OUT_SETS = ("lite", "unseen")


def held_out_tasks(ranker_path: Path) -> int:
    from allfather.rank.browser import predict_many

    if HELD_OUT.exists():
        sys.exit(f"{HELD_OUT} exists")
    sys.modules["__main__"].Item = bl.Item
    ranker = json.loads(ranker_path.read_text(encoding="utf-8"))
    bl.MULTILANG = bool(ranker["meta"].get("multilang"))
    if bl.MULTILANG:
        bl.CACHE = Path(".cache/browser_ltr_multilang")
    snaps = bl.Snapshots()
    WORK.mkdir(parents=True, exist_ok=True)
    written = 0
    with HELD_OUT.open("w", encoding="utf-8", newline="\n") as handle:
        for name in HELD_OUT_SETS:
            for it in bl.build(name, bl.TEST[name], snaps):
                ids, order = [], []
                if it.xb is not None and len(it.xb):
                    ids = bl.unit_ids(it, it.rows_b)
                    order = [ids[i] for i in bl.order(predict_many(ranker["semantic"], it.xb))]
                texts = []
                if order:
                    fn, _, _ = snaps.get(it.repo, it.commit)
                    row_of = dict(zip(ids, it.rows_b.tolist(), strict=True))
                    texts = snaps.r.indexer.unit_texts(
                        fn, [row_of[u] for u in order[: max(DEPTHS)]]
                    )
                record = {
                    "qid": it.qid,
                    "set": name,
                    "repo": it.repo,
                    "query": it.text,
                    "ids": order[:KEEP],
                    "ranker_scores": (-np.log1p(np.arange(1, len(order[:KEEP]) + 1))).tolist(),
                    "texts": texts,
                    "gold": sorted(it.targets),
                }
                handle.write(json.dumps(record) + "\n")
                written += 1
    snaps.close()
    print(f"wrote {HELD_OUT}: {written} issues; ranker {ranker_path}")
    return 0


def held_out_evaluate(name: str) -> int:
    tasks = [json.loads(line) for line in HELD_OUT.open(encoding="utf-8")]
    raw = {
        r["qid"]: r["scores"]
        for r in map(json.loads, (WORK / f"scores_{name}.jsonl").open(encoding="utf-8"))
    }
    report: dict = {"setting": [50, 1.0], "adr": "docs/decisions/0021-website-server-reranker.md"}
    for which in HELD_OUT_SETS:
        rows = [t for t in tasks if t["set"] == which and t["gold"]]
        base, cand = [], []
        for t in rows:
            base.append(score(t["ids"][:10], t["gold"], KS))
            if t["ids"] and t["qid"] in raw and raw[t["qid"]] and raw[t["qid"]][0]:
                cand.append(score(blended(t, raw[t["qid"]], 50, 1.0)[:10], t["gold"], KS))
            else:
                cand.append(score(t["ids"][:10], t["gold"], KS))
        report[which] = {
            "issues": len(rows),
            "website": aggregate(base, KS),
            "with_gpu_reranker": aggregate(cand, KS),
            "paired": {
                m: dataclasses.asdict(
                    paired_bootstrap(metric_values(base, m), metric_values(cand, m))
                )
                for m in ("hit@10", "hit@1", "hit@5", "mrr", "recall@10")
            },
        }
    report["provenance"] = provenance()
    target = OUT / f"heldout_{name}.json"
    if target.exists():
        sys.exit(f"{target} exists")
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    with (ROOT / "results" / "test-evals.log").open("a", encoding="utf-8", newline="\n") as log:
        for which in HELD_OUT_SETS:
            log.write(
                f"{date.today().isoformat()} | {which} | website + GPU reranker | function | results/website-rerank/heldout_{name}.json | "
                "ADR 0021's single held-out run of the configuration the site ships; nothing decided\n"
            )
    for which in HELD_OUT_SETS:
        r = report[which]
        print(
            which,
            r["issues"],
            "website hit@10",
            round(r["website"]["hit@10"], 4),
            "with GPU",
            round(r["with_gpu_reranker"]["hit@10"], 4),
            "paired",
            r["paired"]["hit@10"],
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "step",
        choices=[
            "tasks",
            "evaluate",
            "semantic-orders",
            "skip-language-model",
            "held-out-tasks",
            "held-out-evaluate",
        ],
    )
    ap.add_argument("--ranker", type=Path, default=ROOT / "web" / "src" / "assets" / "ranker.json")
    ap.add_argument("--name", default="current")
    ap.add_argument("--multilang", action="store_true")
    args = ap.parse_args()
    if args.multilang:
        use_multilang()
    steps = {
        "tasks": build_tasks,
        "evaluate": lambda: evaluate(args.name),
        "semantic-orders": semantic_orders,
        "skip-language-model": lambda: skip_language_model(args.name),
        "held-out-tasks": lambda: held_out_tasks(args.ranker),
        "held-out-evaluate": lambda: held_out_evaluate(args.name),
    }
    return steps[args.step]()


if __name__ == "__main__":
    sys.exit(main())
