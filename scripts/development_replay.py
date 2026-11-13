"""Gold-free stage/action capture on the frozen exploratory pilot, with existing weights.

All six actions run on every selected issue. Rows, content keys, candidate pools,
features, rankings, CE scores and component times are retained; scoring is separate.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import browser_ltr as bl  # noqa: E402
import numpy as np  # noqa: E402
from development_assets import MANIFEST as ASSET_MANIFEST  # noqa: E402
from development_assets import cached_models  # noqa: E402
from website_rerank import blended  # noqa: E402

from allfather.rank.browser import FEATURES, POOL, SEMANTIC, extract, predict_many  # noqa: E402
from allfather.search.retriever import Query  # noqa: E402

VERSION = "development-stage-replay-v1"
MODEL_IDS = (bl.STATIC_MODEL, bl.EMBEDDER, "Qwen/Qwen3-Reranker-0.6B")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: dict, compress: bool = False) -> None:
    payload = (json.dumps(value, separators=(",", ":")) + "\n").encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(gzip.compress(payload, mtime=0) if compress else payload)
    temporary.replace(path)


def capture(query: Query, snaps, embed, ranker: dict, ce, sync, seed: int = 37) -> dict:
    """No gold labels accepted. Preserve index row identity, including colliding names."""
    started = time.perf_counter()
    fn, matrix, names = snaps.get(query.repo, query.base_commit)
    prepared = time.perf_counter()
    lex, title_lex, code_lex, sem, tsem, mentions, _ = snaps.signals(fn, matrix, query.text)
    signaled = time.perf_counter()
    pools, actions = {}, {}
    for label, factor in (("base", 1), ("wide", 4)):
        sync()
        tick = time.perf_counter()
        budgets = {key: value * factor for key, value in POOL.items()}
        rows, features = extract(
            fn, lex, title_lex, code_lex, mentions, names, sem, tsem, budgets=budgets
        )
        semantic = predict_many(ranker["semantic"], features)
        item = bl.Item(query.instance_id, query.repo, query.base_commit, query.text, set(), set())
        item.rows_b, item.xb = rows, features
        item.ids = [fn.ids[int(row)] for row in rows]
        # Existing MiniLM feature recipe, with pinned weights and no historical embedding cache.
        if len(rows):
            bl.pass2([item], [semantic], snaps, embed, "development")
        s2 = (
            predict_many(ranker["rerank"], item.xc)
            if len(rows) and "rerank" in ranker
            else np.array([])
        )
        if not all(np.isfinite(a).all() for a in (features, semantic, s2)):
            raise ValueError("nonfinite local feature or score")
        semantic_order = bl.order(semantic)
        if len(s2):
            chosen = set(item.sel.tolist())
            positions = [int(item.sel[i]) for i in bl.order(s2)] + [
                i for i in semantic_order if i not in chosen
            ]
        else:
            positions = semantic_order
        ranked_rows = [int(rows[i]) for i in positions]
        sync()
        actions[f"{label}_local"] = {
            "ranked_rows": ranked_rows,
            "seconds": time.perf_counter() - tick,
        }
        pools[label] = {
            "budgets": budgets,
            "rows": rows.tolist(),
            "features": features.tolist(),
            "semantic_scores": semantic.tolist(),
            "semantic_ranked_rows": [int(rows[i]) for i in semantic_order],
            "minilm_rows": rows[item.sel].tolist() if len(rows) else [],
            "minilm_ranker_scores": s2.tolist(),
        }
    if not set(pools["base"]["rows"]).issubset(pools["wide"]["rows"]):
        raise ValueError("wide pool is not a superset of base pool")
    jobs = [(label, depth) for label in pools for depth in (50, 200)]
    random.Random(f"{seed}:{query.instance_id}").shuffle(jobs)
    for label, depth in jobs:
        sync()
        tick = time.perf_counter()
        ranked = actions[f"{label}_local"]["ranked_rows"]
        top = ranked[:depth]
        texts = snaps.r.indexer.unit_texts(fn, top) if top else []
        before = ce.tokens_computed
        raw = ce.score(query.text, texts).tolist() if texts else []
        if len(raw) != len(top) or not np.isfinite(raw).all():
            raise ValueError("invalid cross-encoder score shape/value")
        task = {"ids": ranked, "ranker_scores": (-np.log1p(np.arange(1, len(ranked) + 1))).tolist()}
        # The blend operates on row numbers, never an ID -> last-row dictionary.
        result = blended(task, [raw], depth, 1.0) if raw else ranked
        sync()
        actions[f"{label}_ce{depth}"] = {
            "ranked_rows": result,
            "read_rows": top,
            "raw_scores": raw,
            "seconds": time.perf_counter() - tick,
            "tokens_computed": ce.tokens_computed - before,
            "weight": 1.0,
        }
    return {
        "schema": VERSION,
        "id": query.instance_id,
        "repo": query.repo,
        "base_commit": query.base_commit,
        "text_sha256": hashlib.sha256(query.text.encode()).hexdigest(),
        "universe": [
            {"row": i, "id": uid, "text_key": fn.unit_keys[i].hex()} for i, uid in enumerate(fn.ids)
        ],
        "files": [{"path": path, "blob": oid} for path, oid in zip(fn.files, fn.oids, strict=True)],
        "feature_names": FEATURES + SEMANTIC,
        "pools": pools,
        "actions": actions,
        "ce_execution_order": [f"{label}_ce{depth}" for label, depth in jobs],
        "snapshot_prepare_seconds": prepared - started,
        "shared_signals_seconds": signaled - prepared,
        "total_seconds": time.perf_counter() - started,
        "timing_scope": "Observed sequential replay. Shared snapshot/signals plus local stage plus incremental CE; not browser latency or a deployed-policy cost estimate.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan", type=Path, default=ROOT / "data/research/development-pilot-v1.json"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    invocation_start = time.perf_counter()
    if args.limit < 0:
        parser.error("limit must be nonnegative")
    plan = json.loads(args.plan.read_bytes())
    data = ROOT / "data/fresh-full/gold.jsonl"
    if digest(data) != plan["dataset_sha256"]:
        parser.error("dataset changed since pilot selection")
    # Extract only inference inputs. Do not pass labels, patches or hint strata to capture().
    inputs = {}
    for line in data.read_bytes().splitlines():
        row = json.loads(line)
        inputs[row["id"]] = Query(row["id"], row["repo"], row["base_commit"], row["text"])
    selected = plan["instances"][: args.limit] if args.limit else plan["instances"]
    for item in selected:
        query = inputs[item["id"]]
        if (query.repo, query.base_commit, hashlib.sha256(query.text.encode()).hexdigest()) != (
            item["repo"],
            item["base_commit"],
            item["text_sha256"],
        ):
            parser.error("pilot metadata mismatch")
    import torch
    from sentence_transformers import SentenceTransformer

    from allfather.rank.cross_encoder import CrossEncoder

    if not torch.cuda.is_available():
        parser.error("GPU replay requires CUDA")
    threads = int(os.environ.get("SLURM_CPUS_PER_TASK", "2"))
    torch.set_num_threads(threads)
    torch.manual_seed(plan["seed"])
    locations = cached_models(json.loads(ASSET_MANIFEST.read_bytes()))
    model_identity = {
        name: {
            "revision": path.name,
            "files_sha256": {
                str(p.relative_to(path)): digest(p) for p in sorted(path.rglob("*")) if p.is_file()
            },
        }
        for name, path in locations.items()
    }
    adapter = ROOT / "models/ce_multi/A/foldall"
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        if not (adapter / name).exists():
            parser.error(f"existing adapter missing: {adapter / name}")
    ranker_path = ROOT / "web/src/assets/ranker.json"
    sources = [
        *sorted((ROOT / "src/allfather").rglob("*.py")),
        Path(__file__),
        ROOT / "scripts/development_assets.py",
        ROOT / "scripts/browser_ltr.py",
        ROOT / "scripts/website_rerank.py",
    ]
    config = {
        "schema": VERSION,
        "plan_sha256": digest(args.plan),
        "assets_sha256": digest(ASSET_MANIFEST),
        "python": sys.version,
        "platform": platform.platform(),
        "instances": selected,
        "model_identity": model_identity,
        "ranker_sha256": digest(ranker_path),
        "adapter_sha256": {p.name: digest(p) for p in sorted(adapter.iterdir()) if p.is_file()},
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in sources},
        "packages": {
            name: importlib.metadata.version(name)
            for name in (
                "torch",
                "transformers",
                "sentence-transformers",
                "peft",
                "huggingface-hub",
                "safetensors",
                "tokenizers",
                "numpy",
                "scipy",
                "tree-sitter",
                "tree-sitter-python",
                "tree-sitter-go",
                "tree-sitter-java",
                "tree-sitter-javascript",
                "tree-sitter-typescript",
                "tree-sitter-rust",
            )
        },
        "device": torch.cuda.get_device_name(0),
        "torch_cuda_version": torch.version.cuda,
        "nvidia_smi": subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv"],
            text=True,
        ).strip(),
        "threads": threads,
        "recipe": {
            "pool_scale": 4,
            "ce_depths": [50, 200],
            "ce_weight": 1.0,
            "query_tokens": 512,
            "doc_tokens": 256,
            "minilm_tokens": 256,
        },
    }
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = args.out / "manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_bytes()) != config:
            parser.error("replay manifest differs; choose a new output directory")
    else:
        write_json(manifest, config)
    tick = time.perf_counter()
    bl.MULTILANG = True
    snaps = bl.Snapshots(static_revision=locations[bl.STATIC_MODEL].name)
    model = SentenceTransformer(str(locations[bl.EMBEDDER]), device="cuda")
    model.max_seq_length = 256

    def embed(texts):
        return model.encode(texts, normalize_embeddings=True, batch_size=32)

    ce = CrossEncoder(adapter=adapter, base=str(locations[MODEL_IDS[2]]))
    ranker = json.loads(ranker_path.read_bytes())
    startup = time.perf_counter() - tick
    failures = []
    prior = (
        json.loads((args.out / "index.json").read_bytes())["completed"]
        if (args.out / "index.json").exists()
        else {}
    )
    # Validate the old index before any progress write could replace its checksums.
    for qid, previous in prior.items():
        target = args.out / (hashlib.sha256(qid.encode()).hexdigest() + ".json.gz")
        if not target.exists() or digest(target) != previous["sha256"]:
            raise ValueError(f"previously completed trace changed: {qid}")
    # Preserve all verified checksums even if an interrupted resume processes only
    # the first few issues before writing its next progress checkpoint.
    completed = dict(prior)
    try:
        for item in selected:
            qid = item["id"]
            target = args.out / (hashlib.sha256(qid.encode()).hexdigest() + ".json.gz")
            try:
                if target.exists():
                    if qid in prior and digest(target) != prior[qid]["sha256"]:
                        raise ValueError("existing trace checksum mismatch")
                    trace = json.loads(gzip.decompress(target.read_bytes()))
                    if trace["id"] != qid or trace["manifest_sha256"] != digest(manifest):
                        raise ValueError("existing trace identity mismatch")
                else:
                    trace = capture(
                        inputs[qid], snaps, embed, ranker, ce, torch.cuda.synchronize, plan["seed"]
                    )
                    trace["manifest_sha256"] = digest(manifest)
                    trace["slurm_job_id"] = os.environ.get("SLURM_JOB_ID")
                    write_json(target, trace, compress=True)
                completed[qid] = {
                    "file": target.name,
                    "sha256": digest(target),
                    "universe": len(trace["universe"]),
                    "base_pool": len(trace["pools"]["base"]["rows"]),
                    "wide_pool": len(trace["pools"]["wide"]["rows"]),
                }
                print(qid, completed[qid], flush=True)
            except Exception as exc:
                failures.append({"id": qid, "error": f"{type(exc).__name__}: {exc}"})
                print("FAILED", qid, failures[-1]["error"], flush=True)
            write_json(args.out / "index.json", {"completed": completed, "failures": failures})
    finally:
        snaps.close()
    summary = {
        "expected": len(selected),
        "completed": len(completed),
        "failures": failures,
        "startup_seconds": startup,
        "script_seconds": time.perf_counter() - invocation_start,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    write_json(args.out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
