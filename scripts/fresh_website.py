"""Run the website's own pipeline (ADR 0033, tier T0) on a set from scripts/frontier.py.

    uv run python scripts/fresh_website.py --set pilot
    uv run python scripts/fresh_website.py --set fresh --gpu results/website-rerank/gpu_config.json

The same ranking the live-accuracy monitor runs (browser rankers, semantic and language-model
stages), in all six languages. With --gpu, the top functions are also re-read by the GPU reranker's
adapters on this machine and blended into the order as the site does, for the languages and with
the depth and weight the configuration names (ADR 0034); the output is then <set>_website-gpu.jsonl.
With --files, each record also keeps the file ranker's top 10 (ADR 0033's file-level amendment), written
to <set>_website-files.jsonl. Writes results/research/frontier/<set>_website.jsonl otherwise. Resumable.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from frontier import OUT, load_set, log_test_run  # noqa: E402
from live_eval import RANKER, Site  # noqa: E402
from website_rerank import blended  # noqa: E402

from allfather.eval.dataset import Instance  # noqa: E402
from allfather.eval.execution import bind_run, digest, make_plan, source_hashes  # noqa: E402
from allfather.parsing.symbols import language_of  # noqa: E402
from allfather.rank.confidence import confidence_features, predict_confidence  # noqa: E402

CONFIDENCE = ROOT / "web" / "src" / "assets" / "confidence.json"


def list_language(units: list[str]) -> str | None:
    langs = Counter(
        "typescript" if lang == "tsx" else lang
        for u in units
        if (lang := language_of(u.split("::", 1)[0]))
    )
    if not langs:
        return None
    lang, n = langs.most_common(1)[0]
    return lang if n * 2 > len(units) else None


class Gpu:
    def __init__(self, path: Path) -> None:
        from allfather.rank.cross_encoder import CrossEncoder

        self.config = json.loads(path.read_text(encoding="utf-8"))
        self.members = [CrossEncoder(adapter=ROOT / a) for a in self.config["adapters"]]

    def rerank(self, site: Site, inst: Instance, ranked: list[str]) -> tuple[list[str], str | None]:
        depth = max(c["depth"] for c in self.config["languages"].values())
        lang = list_language(ranked[:depth])
        setting = self.config["languages"].get(lang or "")
        if not setting or len(ranked) < 2:
            return ranked, None
        fn, _, _ = site.snaps.get(inst.repo, inst.base_commit)
        rows = site.last_ranked_rows
        if len(rows) != len(ranked) or any(
            fn.ids[row] != uid for row, uid in zip(rows, ranked, strict=True)
        ):
            raise ValueError("GPU reranking requires aligned row identities from Site.rank")
        top = ranked[: setting["depth"]]
        texts = site.snaps.r.indexer.unit_texts(fn, rows[: len(top)])
        scores = [m.score(inst.problem_statement, texts).tolist() for m in self.members]
        task = {"ids": ranked, "ranker_scores": (-np.log1p(np.arange(1, len(ranked) + 1))).tolist()}
        return blended(task, scores, setting["depth"], setting["weight"]), lang


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--gpu", type=Path)
    ap.add_argument("--files", action="store_true")
    ap.add_argument(
        "--tag", help="new identity for a changed recipe; historical outputs cannot be resumed"
    )
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--execution-seed", type=int, default=37)
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()
    ids, items = load_set(args.set)
    system = "website-gpu" if args.gpu else "website-files" if args.files else "website"
    if args.tag:
        system += "-" + args.tag
    target = OUT / f"{args.set}_{system}.jsonl"
    assets = {"ranker": digest(RANKER.read_bytes()), "confidence": digest(CONFIDENCE.read_bytes())}
    if args.gpu:
        assets["gpu_config"] = digest(args.gpu.read_bytes())
        for adapter in json.loads(args.gpu.read_bytes())["adapters"]:
            for name in ("adapter_config.json", "adapter_model.safetensors"):
                assets[f"{adapter}/{name}"] = digest((ROOT / adapter / name).read_bytes())
    plan = make_plan(
        ids,
        items,
        {
            "set": args.set,
            "system": system,
            "files": args.files,
            "assets": assets,
            "sources": source_hashes(
                ROOT,
                [
                    "scripts/fresh_website.py",
                    "scripts/frontier.py",
                    "scripts/live_eval.py",
                    "scripts/browser_ltr.py",
                    "scripts/website_rerank.py",
                ],
            ),
        },
        args.execution_seed,
        args.limit,
    )
    execution_hash, done = bind_run(target, plan)
    if args.plan_only or len(done) == len(plan["ids"]):
        print(
            json.dumps(
                {
                    "manifest_sha256": execution_hash,
                    "planned": len(plan["ids"]),
                    "completed": len(done),
                    "projects": plan["projects"],
                }
            )
        )
        return 0
    site = Site()
    gpu = Gpu(args.gpu) if args.gpu else None
    model = json.loads(CONFIDENCE.read_text(encoding="utf-8"))
    label = f"ranker {site.sha[:12]}" + (f", GPU config {args.gpu.name}" if gpu else "")
    if not done:
        log_test_run(args.set, system, label, target)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        for q in plan["ids"]:
            if q in done:
                continue
            item = items[q]
            inst = Instance(q, item["repo"], item["base_commit"], "", item["text"])
            start = time.perf_counter()
            site.last_semantic = None
            ranked, ranked_files, units = site.rank(inst, set(), set())
            sure = None
            if site.last_semantic is not None:
                s_b, X, chars = site.last_semantic
                sure = round(
                    float(predict_confidence(model, confidence_features(s_b, X, chars))[0]), 4
                )
            reranked_for = None
            if gpu:
                ranked, reranked_for = gpu.rerank(site, inst, ranked)
            top = [{"file": u.split("::", 1)[0], "name": u.split("::", 1)[1]} for u in ranked[:10]]
            record = {
                "id": q,
                "system": system,
                "execution_manifest_sha256": execution_hash,
                "requested_model": label,
                "date": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": round(time.perf_counter() - start, 1),
                "answer": {"functions": top},
                "units": units,
                "confidence": sure,
                "gpu_language": reranked_for,
                **({"files": ranked_files[:10]} if args.files else {}),
                "cost_usd": None,
                "cost_accounting": {
                    "schema": "run-cost-v1",
                    "usd": None,
                    "state": "unknown",
                    "basis": "local compute was not monetized",
                    "scope": "run_charge",
                },
                "tools": [],
                "web_tool_used": False,
            }
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            print(f"  {q}: {units} units, {record['seconds']} s, GPU {reranked_for}", flush=True)
    site.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
