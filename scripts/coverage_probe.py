"""Gold-free CPU retrieval controls on the original fit snapshots; no downloads.

This measures candidate generation, not a new localization method. Scoring is separate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import numpy as np  # noqa: E402
from replay_text_views import PROTOCOL as PARENT_PROTOCOL  # noqa: E402
from replay_text_views import digest, inputs, source_texts, write_json  # noqa: E402
from validate_development_replay import require  # noqa: E402

from allfather.index.snapshot import _PATH_SPLIT  # noqa: E402
from allfather.rank.features import _logrank, _rel, issue_fields  # noqa: E402
from allfather.search.bm25 import BM25Index, Vocab, top_k  # noqa: E402
from allfather.search.tokenize import code_counts  # noqa: E402

PROTOCOL = ROOT / "data/research/coverage-probe-v1.json"
QUOTED = re.compile(r""""([^"\n]{3,200})"|'([^'\n]{3,200})' """, re.X)
IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
KINDS = ("base", "wide", "bm25_full", "field_rrf", "inject_rrf", "inject_refs", "inject_random")


def validate_protocol(protocol: dict) -> None:
    expected = {
        "budgets": [50, 200],
        "fields": ["full", "title", "code", "quoted"],
        "actions": list(KINDS),
        "fusion": {"method": "reciprocal rank", "constant": 60, "per_field_positive_depth": 1000},
        "random_control": {"seed": "37:issue_id", "repeats": 1},
    }
    require(all(protocol.get(k) == v for k, v in expected.items()), "control protocol changed")
    require(protocol["bm25"]["k1"] == 1.2 and protocol["bm25"]["b"] == 0.75, "BM25 changed")
    require(
        protocol["reference_expansion"]["seed_count"] == 10
        and protocol["reference_expansion"]["max_name_fanout"] == 8,
        "reference protocol changed",
    )


def query_fields(text: str) -> dict[str, str]:
    title, code = issue_fields(text)
    quoted = list(dict.fromkeys(a or b for a, b in QUOTED.findall(text)))
    return {"full": text, "title": title, "code": code, "quoted": "\n".join(quoted)}


def lexical_index(texts: list[str], universe: list[dict]) -> tuple[BM25Index, Vocab]:
    vocab, docs, paths = Vocab(), [], {}
    for text, unit in zip(texts, universe, strict=True):
        path = unit["id"].split("::", 1)[0]
        if path not in paths:
            stem = (
                path.removesuffix(".py")
                if path.endswith(".py") or "." not in path
                else path.rsplit(".", 1)[0]
            )
            paths[path] = code_counts(" ".join(_PATH_SPLIT.split(stem)))
        docs.append(vocab.vectorize(code_counts(text) + paths[path]))
    return BM25Index.from_docs(docs, len(vocab)), vocab


def positive_order(scores: np.ndarray, limit: int = 1000) -> list[int]:
    return [int(r) for r in top_k(scores, limit) if scores[r] > 0]


def fuse(lists: list[list[int]]) -> list[int]:
    scores = defaultdict(float)
    for rows in lists:
        for rank, row in enumerate(rows, 1):
            scores[row] += 1 / (60 + rank)
    return sorted(scores, key=lambda r: (-scores[r], r))


def reference_neighbors(
    texts: list[str], universe: list[dict], seeds: list[int]
) -> tuple[list[int], dict]:
    """Lexical name references, not typed/resolved call edges; comments can match."""
    names = defaultdict(list)
    paths = [u["id"].split("::", 1)[0] for u in universe]
    for row, unit in enumerate(universe):
        name = unit["id"].split("::", 1)[1].rsplit(".", 1)[-1]
        names[name].append(row)
    scores = defaultdict(float)
    counts = Counter()
    for rank, seed in enumerate(seeds[:10], 1):
        for name in sorted(set(IDENT.findall(texts[seed]))):
            candidates = [r for r in names.get(name, []) if r != seed]
            local = [r for r in candidates if paths[r] == paths[seed]]
            candidates = local or candidates
            if not candidates:
                continue
            if len(candidates) > 8:
                counts["references_skipped_for_ambiguity"] += 1
                continue
            counts["resolved_name_references"] += 1
            for row in candidates:
                scores[row] += 1 / ((60 + rank) * len(candidates))
    return sorted(scores, key=lambda r: (-scores[r], r)), dict(counts)


def inject(base: list[int], proposal: list[int], budget: int) -> list[int]:
    """Keep the first half; replace at most half with rows outside the original prefix."""
    original = base[:budget]
    capacity = len(original)
    head = original[: (capacity + 1) // 2]
    original_set, seen = set(original), set(head)
    new = []
    for row in proposal:
        if row not in original_set and row not in seen and len(new) < capacity - len(head):
            new.append(row)
            seen.add(row)
    result = head + new
    result += [r for r in original if r not in seen][: capacity - len(result)]
    require(len(result) == len(set(result)) == capacity, "injection cardinality mismatch")
    return result


def capture(query: str, parent: dict, mirror_root: Path) -> dict:
    started = time.perf_counter()
    texts = source_texts(parent, list(range(len(parent["universe"]))), mirror_root)
    read_at = time.perf_counter()
    index, vocab = lexical_index(texts, parent["universe"])
    indexed_at = time.perf_counter()
    fields = query_fields(query)
    scores, orders, features = {}, {}, {}
    for name, text in fields.items():
        terms = code_counts(text)
        vector = vocab.lookup(terms)
        scores[name] = index.scores(vector)
        orders[name] = positive_order(scores[name])
        top = scores[name][top_k(scores[name], 2)]
        features[name] = {
            "characters": len(text),
            "unique_terms": len(terms),
            "known_unique_terms": len(vector[0]),
            "positive_units": int(np.count_nonzero(scores[name] > 0)),
            "max_score": float(top[0]) if len(top) else 0.0,
            "first_second_gap": float(top[0] - top[1]) if len(top) > 1 else 0.0,
        }
    parity = {}
    feature_names = parent["feature_names"]
    for name, prefix in (("full", "bm25"), ("title", "title_bm25"), ("code", "code_bm25")):
        relative, logrank = _rel(scores[name]), _logrank(scores[name])
        for pool in ("base", "wide"):
            rows = parent["pools"][pool]["rows"]
            saved = np.asarray(parent["pools"][pool]["features"], dtype=np.float32)
            for suffix, values in (("rel", relative), ("logrank", logrank)):
                expected = saved[:, feature_names.index(f"{prefix}_{suffix}")]
                difference = float(
                    np.max(np.abs(values[rows].astype(np.float32) - expected), initial=0)
                )
                parity[f"{pool}/{name}/{suffix}"] = difference
                require(
                    difference <= 2e-6,
                    f"reconstructed lexical feature differs: {pool}/{name}/{suffix}/{difference}",
                )
    rrf = fuse(list(orders.values()))
    neighbors, ref_features = reference_neighbors(texts, parent["universe"], rrf)
    shuffled = list(range(len(texts)))
    random.Random(f"37:{parent['id']}").shuffle(shuffled)
    base, wide = (parent["actions"][f"{p}_local"]["ranked_rows"] for p in ("base", "wide"))
    actions = {}
    for k in (50, 200):
        choices = {
            "base": base[:k],
            "wide": wide[:k],
            "bm25_full": orders["full"][:k],
            "field_rrf": rrf[:k],
            "inject_rrf": inject(base, rrf, k),
            "inject_refs": inject(base, neighbors, k),
            "inject_random": inject(base, shuffled, k),
        }
        for name, rows in choices.items():
            actions[f"{name}_{k}"] = {
                "rows": rows,
                "added_vs_base_read": sorted(set(rows) - set(base[:k])),
                "removed_vs_base_read": sorted(set(base[:k]) - set(rows)),
                "outside_base_pool": sorted(set(rows) - set(parent["pools"]["base"]["rows"])),
            }
    return {
        "schema": "fit-coverage-probe-v1",
        "id": parent["id"],
        "repo": parent["repo"],
        "base_commit": parent["base_commit"],
        "text_sha256": parent["text_sha256"],
        "universe_units": len(texts),
        "query_fields": fields,
        "field_orders_top1000": orders,
        "rrf_order": rrf,
        "reference_order": neighbors,
        "features": {"fields": features, "references": ref_features},
        "lexical_feature_parity": parity,
        "actions": actions,
        "timing": {
            "source_seconds": read_at - started,
            "index_seconds": indexed_at - read_at,
            "query_and_selection_seconds": time.perf_counter() - indexed_at,
            "total_seconds": time.perf_counter() - started,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), "use a new output directory")
    protocol = json.loads(PROTOCOL.read_bytes())
    validate_protocol(protocol)
    require(
        protocol["parent_protocol_sha256"] == digest(PARENT_PROTOCOL), "parent protocol changed"
    )
    selected = inputs(args.parent, json.loads(PARENT_PROTOCOL.read_bytes()))
    require([r[0]["id"] for r in selected] == protocol["fit_ids"], "fit membership changed")
    source_files = [
        Path(__file__),
        ROOT / "scripts/replay_text_views.py",
        *sorted((ROOT / "src/allfather").rglob("*.py")),
    ]
    manifest = {
        "schema": "fit-coverage-probe-v1",
        "protocol_sha256": digest(PROTOCOL),
        "protocol": protocol,
        "parent_manifest_sha256": digest(args.parent / "manifest.json"),
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in source_files},
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": sys.version,
        "packages": {
            name: importlib.metadata.version(name)
            for name in (
                "numpy",
                "scipy",
                "tree-sitter",
                "tree-sitter-python",
                "tree-sitter-go",
                "tree-sitter-java",
                "tree-sitter-rust",
                "tree-sitter-javascript",
                "tree-sitter-typescript",
            )
        },
    }
    args.out.mkdir(parents=True)
    write_json(args.out / "manifest.json", manifest)
    completed, failures = {}, []
    for item, query, parent in selected:
        try:
            result = capture(query, parent, ROOT / ".cache/repos")
            result["manifest_sha256"] = digest(args.out / "manifest.json")
            result["parent_trace_sha256"] = protocol["trace_sha256"][item["id"]]
            filename = hashlib.sha256(item["id"].encode()).hexdigest() + ".json.gz"
            write_json(args.out / filename, result, compress=True)
            completed[item["id"]] = {"file": filename, "sha256": digest(args.out / filename)}
            print(
                item["id"],
                len(parent["universe"]),
                "units;",
                round(result["timing"]["total_seconds"], 2),
                "seconds",
                flush=True,
            )
        except Exception as exc:
            failures.append({"id": item["id"], "error": f"{type(exc).__name__}: {exc}"})
            print("FAILED", failures[-1], flush=True)
        write_json(args.out / "index.json", {"completed": completed, "failures": failures})
    write_json(
        args.out / "summary.json",
        {"expected": len(selected), "completed": len(completed), "failures": failures},
    )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
