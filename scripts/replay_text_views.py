"""Fit-only token-view experiment on frozen candidate rows; labels are never used.

Reads verified existing traces and base Git blobs, with lazy fetching disabled.
Only model inference needs a GPU. --prepare-only validates all inputs/views offline.
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

import numpy as np  # noqa: E402
from development_assets import MANIFEST as ASSETS  # noqa: E402
from development_assets import cached_models, check_adapter, digest  # noqa: E402
from text_views import (  # noqa: E402
    DOC_VIEWS,
    QUERY_VIEWS,
    doc_views,
    positions,
    select,
    token_hash,
)
from website_rerank import blended  # noqa: E402

from allfather.index.chunker import MODULE, chunk_file  # noqa: E402
from allfather.index.snapshot import unit_key, unit_text  # noqa: E402

PROTOCOL = ROOT / "data/research/text-view-pilot-v1.json"
POOL_DEPTHS = {"base": 50, "wide": 200}


def write_json(path: Path, value: dict, compress=False) -> None:
    data = (json.dumps(value, separators=(",", ":")) + "\n").encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(gzip.compress(data, mtime=0) if compress else data)
    temporary.replace(path)


def inputs(bundle: Path, protocol: dict) -> list[tuple[dict, str, dict]]:
    implementation = {
        "seed": 37,
        "query_views": list(QUERY_VIEWS),
        "document_views": list(DOC_VIEWS),
        "pool_depths": POOL_DEPTHS,
        "query_tokens": 512,
        "document_tokens": 256,
        "window_stride": 128,
        "blend_weight": 1.0,
        "bm25": {
            "k1": 1.2,
            "b": 0.75,
            "idf_scope": "overlapping windows within each candidate unit",
            "query_terms": "selected query view only; existing code_counts tokenizer",
        },
    }
    if any(protocol.get(k) != v for k, v in implementation.items()):
        raise ValueError("protocol differs from implemented controls")
    plan_path = ROOT / "data/research/development-pilot-v1.json"
    if digest(plan_path) != protocol["plan_sha256"]:
        raise ValueError("original plan changed")
    plan = json.loads(plan_path.read_bytes())
    fit = [r for r in plan["instances"] if r["split"] == "fit"]
    if [r["id"] for r in fit] != protocol["fit_ids"]:
        raise ValueError("protocol is not the original fit-only selection")
    if digest(bundle / "manifest.json") != protocol["parent_manifest_sha256"]:
        raise ValueError("parent replay manifest changed")
    data = ROOT / "data/fresh-full/gold.jsonl"
    if digest(data) != plan["dataset_sha256"]:
        raise ValueError("dataset changed")
    # Project immediately to inference fields; no gold values leave this comprehension.
    queries = {
        r["id"]: {k: r[k] for k in ("repo", "base_commit", "text")}
        for r in map(json.loads, data.read_bytes().splitlines())
        if r["id"] in protocol["fit_ids"]
    }
    index = json.loads((bundle / "index.json").read_bytes())["completed"]
    out = []
    for item in fit:
        qid = item["id"]
        q = queries[qid]
        checksum = hashlib.sha256(q["text"].encode()).hexdigest()
        if (q["repo"], q["base_commit"], checksum) != (
            item["repo"],
            item["base_commit"],
            item["text_sha256"],
        ):
            raise ValueError("query metadata mismatch")
        expected_file = hashlib.sha256(qid.encode()).hexdigest() + ".json.gz"
        entry = index[qid]
        if (
            entry["file"] != expected_file
            or digest(bundle / expected_file) != protocol["trace_sha256"][qid]
        ):
            raise ValueError(f"frozen trace changed: {qid}")
        if entry["sha256"] != protocol["trace_sha256"][qid]:
            raise ValueError("parent index checksum changed")
        trace = json.loads(gzip.decompress((bundle / expected_file).read_bytes()))
        if (trace["id"], trace["repo"], trace["base_commit"], trace["text_sha256"]) != (
            qid,
            item["repo"],
            item["base_commit"],
            checksum,
        ) or trace["manifest_sha256"] != protocol["parent_manifest_sha256"]:
            raise ValueError("trace metadata mismatch")
        out.append((item, q["text"], trace))
    return out


def source_texts(trace: dict, rows: list[int], mirror_root: Path) -> list[str]:
    """Rebuild selected content by (ID, content key), never by name alone."""
    universe = trace["universe"]
    requested = [universe[i] for i in rows]
    if any(r["row"] != i for r, i in zip(requested, rows, strict=True)):
        raise ValueError("noncanonical row identity")
    paths = sorted({r["id"].split("::", 1)[0] for r in requested})
    blobs = {f["path"]: f["blob"] for f in trace["files"]}
    mirror = mirror_root / (trace["repo"].replace("/", "__") + ".git")
    result = (
        subprocess.run(
            ["git", "cat-file", "--batch"],
            input=("\n".join(blobs[p] for p in paths) + "\n").encode(),
            cwd=mirror,
            capture_output=True,
            timeout=300,
            env={
                **os.environ,
                "GIT_NO_LAZY_FETCH": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_NO_REPLACE_OBJECTS": "1",
            },
        )
        if paths
        else None
    )
    if result is not None and result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace")[:500])
    data, cursor, found = result.stdout if result else b"", 0, {}
    wanted = {(r["id"], r["text_key"]) for r in requested}
    for path in paths:
        end = data.index(b"\n", cursor)
        fields = data[cursor:end].decode().split()
        if len(fields) != 3 or fields[:2] != [blobs[path], "blob"]:
            raise ValueError(f"base blob unavailable: {path}: {fields}")
        size = int(fields[2])
        source = data[end + 1 : end + 1 + size]
        cursor = end + 2 + size
        oid = hashlib.sha1(b"blob " + str(size).encode() + b"\0" + source).hexdigest()
        if oid != blobs[path]:
            raise ValueError("base blob checksum mismatch")
        for chunk in chunk_file(source, path):
            if chunk.kind == MODULE:
                continue
            text = unit_text(chunk.qualname, chunk.text)
            key = (chunk.id(path), unit_key(text).hex())
            if key in wanted:
                found[key] = text
    if wanted - found.keys():
        raise ValueError(
            f"base content keys not reconstructed: {sorted(wanted - found.keys())[:3]}"
        )
    return [found[(r["id"], r["text_key"])] for r in requested]


def prepare(query: str, trace: dict, tokenizer, mirror_root: Path) -> dict:
    pools = {p: trace["actions"][f"{p}_local"]["ranked_rows"][:n] for p, n in POOL_DEPTHS.items()}
    rows = sorted(set().union(*map(set, pools.values())))
    texts = source_texts(trace, rows, mirror_root)
    # These full tokenizations are CPU work only; forward passes receive bounded views.
    docs = {
        row: tokenizer(t, add_special_tokens=False)["input_ids"]
        for row, t in zip(rows, texts, strict=True)
    }
    full_query = tokenizer(query, add_special_tokens=False)["input_ids"]
    queries, views = {}, {}
    for name in QUERY_VIEWS:
        spans = positions(len(full_query), 512, name)
        ids = select(full_query, spans)
        queries[name] = {"ids": ids, "spans": spans, "sha256": token_hash(ids)}
        views[name] = {
            row: doc_views(
                tokenizer, docs[row], ids, f"37:{trace['id']}:{trace['universe'][row]['text_key']}"
            )
            for row in rows
        }
    return {
        "pools": pools,
        "queries": queries,
        "views": views,
        "query_tokens_full": len(full_query),
        "doc_tokens_full": {r: len(ids) for r, ids in docs.items()},
    }


def capture(trace: dict, prepared: dict, ce, sync) -> dict:
    jobs = [(p, q, d) for p in POOL_DEPTHS for q in QUERY_VIEWS for d in DOC_VIEWS]
    random.Random(f"37:{trace['id']}").shuffle(jobs)
    actions, parity = {}, {}
    for pool, query_view, doc_view in jobs:
        rows = prepared["pools"][pool]
        query = prepared["queries"][query_view]["ids"]
        docs = [prepared["views"][query_view][r][doc_view]["ids"] for r in rows]
        sync()
        start, before = time.perf_counter(), ce.tokens_computed
        raw = ce.score_tokenized(query, docs).tolist()
        sync()
        seconds = time.perf_counter() - start
        if len(raw) != len(rows) or not np.isfinite(raw).all():
            raise ValueError("invalid cross-encoder scores")
        ranked = trace["actions"][f"{pool}_local"]["ranked_rows"]
        task = {"ids": ranked, "ranker_scores": (-np.log1p(np.arange(1, len(ranked) + 1))).tolist()}
        result = blended(task, [raw], POOL_DEPTHS[pool], 1.0) if raw else ranked
        name = f"{pool}_{query_view}_{doc_view}"
        actions[name] = {
            "ranked_rows": result,
            "read_rows": rows,
            "raw_scores": raw,
            "seconds": seconds,
            "tokens_computed": ce.tokens_computed - before,
        }
        if query_view == doc_view == "prefix":
            prior = trace["actions"][f"{pool}_ce{POOL_DEPTHS[pool]}"]
            if prior["read_rows"] != rows:
                raise ValueError("parent CE read order mismatch")
            parity[pool] = {
                "rankings_equal": result == prior["ranked_rows"],
                "scores_max_abs_difference": float(
                    np.max(np.abs(np.array(raw) - prior["raw_scores"]))
                )
                if raw
                else 0.0,
            }
    # All variants in a pool must compute identical numbers of nonpadding positions.
    for pool in POOL_DEPTHS:
        counts = {v["tokens_computed"] for k, v in actions.items() if k.startswith(pool + "_")}
        if len(counts) != 1:
            raise ValueError("unequal token budget across views")
    return {
        "actions": actions,
        "parent_parity": parity,
        "execution_order": ["_".join(j) for j in jobs],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("choose a new output directory; existing evidence is immutable")
    started = time.perf_counter()
    protocol = json.loads(PROTOCOL.read_bytes())
    selected = inputs(args.bundle, protocol)
    spec = json.loads(ASSETS.read_bytes())
    name = "Qwen/Qwen3-Reranker-0.6B"
    locations = cached_models({"models": {name: spec["models"][name]}})
    location = locations[name]
    for relative, expected in spec["models"][name]["files_sha256"].items():
        if digest(location / relative) != expected:
            raise ValueError(f"pinned model file differs: {relative}")
    errors = check_adapter(spec)
    if errors:
        raise ValueError(errors)
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(location), local_files_only=True)
    ce, sync = None, lambda: None
    if not args.prepare_only:
        import torch

        from allfather.rank.cross_encoder import CrossEncoder

        if not torch.cuda.is_available():
            parser.error("inference requires CUDA; use --prepare-only for offline validation")
        torch.set_num_threads(int(os.environ.get("SLURM_CPUS_PER_TASK", "2")))
        torch.manual_seed(37)
        ce = CrossEncoder(adapter=ROOT / spec["adapter"]["path"], base=str(location))
        sync = torch.cuda.synchronize
    sources = [
        *sorted((ROOT / "src/allfather").rglob("*.py")),
        Path(__file__),
        ROOT / "scripts/text_views.py",
        ROOT / "scripts/development_assets.py",
        ROOT / "scripts/website_rerank.py",
    ]
    manifest = {
        "schema": "fit-text-views-v1",
        "prepare_only": args.prepare_only,
        "protocol_sha256": digest(PROTOCOL),
        "assets_sha256": digest(ASSETS),
        "protocol": protocol,
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in sources},
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            n: importlib.metadata.version(n)
            for n in ("torch", "transformers", "peft", "tokenizers", "numpy", "huggingface-hub")
        },
        "device": None if ce is None else torch.cuda.get_device_name(0),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
    }
    args.out.mkdir(parents=True)
    write_json(args.out / "manifest.json", manifest)
    completed, failures, parity = {}, [], {}
    for item, query, trace in selected:
        qid = item["id"]
        try:
            tick = time.perf_counter()
            prepared = prepare(query, trace, tokenizer, ROOT / ".cache/repos")
            seconds = time.perf_counter() - tick
            result = capture(trace, prepared, ce, sync) if ce is not None else {}
            # Save exact token views for independent reconstruction, never labels/patches.
            result.update(
                {
                    "id": qid,
                    "manifest_sha256": digest(args.out / "manifest.json"),
                    "parent_trace_sha256": protocol["trace_sha256"][qid],
                    "prepared": prepared,
                    "prepare_seconds": seconds,
                }
            )
            filename = hashlib.sha256(qid.encode()).hexdigest() + ".json.gz"
            write_json(args.out / filename, result, compress=True)
            completed[qid] = {"file": filename, "sha256": digest(args.out / filename)}
            parity[qid] = result.get("parent_parity")
            print(qid, "prepared" if ce is None else result["parent_parity"], flush=True)
        except Exception as exc:
            failures.append({"id": qid, "error": f"{type(exc).__name__}: {exc}"})
            print("FAILED", failures[-1], flush=True)
        write_json(args.out / "index.json", {"completed": completed, "failures": failures})
    summary = {
        "expected": len(selected),
        "completed": len(completed),
        "failures": failures,
        "prepare_only": args.prepare_only,
        "parent_parity": parity,
        "script_seconds": time.perf_counter() - started,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
    }
    write_json(args.out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
