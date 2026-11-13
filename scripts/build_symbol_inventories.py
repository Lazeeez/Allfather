"""Build gold-independent, versioned base-snapshot inventories for evaluator repair.

CPU only. Reads every supported non-test source file, retaining duplicate symbol IDs,
source blob IDs, parser-error flags and line ranges. No model or agent is invoked.
Resume only with identical source/inputs; failed snapshots remain retryable.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from frontier import load_set  # noqa: E402

from allfather.parsing import symbols  # noqa: E402
from allfather.repos import BlobReader, RepoCache  # noqa: E402

VERSION = "symbol-inventory-v1"


def snapshot_inventory(cache: RepoCache, repo: str, commit: str) -> dict:
    entries = [
        entry
        for entry in cache.list_tree(repo, commit)
        if symbols.language_of(entry.path) and not symbols.is_test_path(entry.path)
    ]
    cache.prefetch_blobs(repo, [f"{commit}:{entry.path}" for entry in entries])
    files, units = [], []
    with BlobReader(cache.ensure_commit(repo, commit)) as reader:
        for entry in entries:
            source = reader.read(entry.oid)
            language = symbols.language_of(entry.path)
            tree = symbols.parse(source, language)
            found = symbols.extract_symbols(source, entry.path, tree)
            files.append(
                {
                    "path": entry.path,
                    "blob": entry.oid,
                    "language": language,
                    "parser_has_error": tree.root_node.has_error,
                }
            )
            units.extend(
                {
                    "id": symbol.id,
                    "kind": symbol.kind,
                    "start_line": symbol.start_line,
                    "end_line": symbol.end_line,
                }
                for symbol in found
                if not symbol.nested
            )
    counts = Counter(unit["id"] for unit in units)
    return {
        "schema": VERSION,
        "repo": repo,
        "base_commit": commit,
        "collection_complete": True,
        "policy": "language_of source files, is_test_path excluded; non-nested symbols; module remainder excluded",
        "files": files,
        "symbols": units,
        "colliding_ids": {unit: count for unit, count in counts.items() if count > 1},
        "parser_error_files": [file["path"] for file in files if file["parser_has_error"]],
    }


def write_json(path: Path, value: dict, compressed: bool = False) -> None:
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    temporary.write_bytes(gzip.compress(payload, mtime=0) if compressed else payload)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", default="fresh-full")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/repos")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=37)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    ids, items = load_set(args.set)
    # No gold labels or issue text are passed to the builder or written to the manifest.
    inputs = [
        {"id": q, "repo": items[q]["repo"], "base_commit": items[q]["base_commit"]} for q in ids
    ]
    order = list(inputs)
    random.Random(args.seed).shuffle(order)
    if args.limit:
        order = order[: args.limit]
    sources = [
        Path(__file__),
        ROOT / "scripts/frontier.py",
        ROOT / "src/allfather/repos.py",
        ROOT / "src/allfather/parsing/symbols.py",
        ROOT / "src/allfather/parsing/python_symbols.py",
    ]
    packages = [
        "tree-sitter",
        *[
            f"tree-sitter-{lang}"
            for lang in ("python", "javascript", "typescript", "java", "go", "rust")
        ],
    ]
    configuration = {
        "schema": VERSION,
        "set": args.set,
        "seed": args.seed,
        "instances": order,
        "source_sha256": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "parser_versions": {package: importlib.metadata.version(package) for package in packages},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = args.out / "manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != configuration:
            parser.error("manifest differs; use a new output directory")
    else:
        write_json(manifest, configuration)
    cache = RepoCache(args.cache)
    index, failures = {}, []
    for number, item in enumerate(order, 1):
        key = hashlib.sha256(f"{item['repo']}@{item['base_commit']}".encode()).hexdigest()
        target = args.out / f"{key}.json.gz"
        try:
            if target.exists():
                inventory = json.loads(gzip.decompress(target.read_bytes()))
                if (inventory["repo"], inventory["base_commit"], inventory["schema"]) != (
                    item["repo"],
                    item["base_commit"],
                    VERSION,
                ) or not inventory["collection_complete"]:
                    raise ValueError("invalid existing snapshot inventory")
            else:
                inventory = snapshot_inventory(cache, item["repo"], item["base_commit"])
                write_json(target, inventory, compressed=True)
            index[item["id"]] = {
                "file": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "files": len(inventory["files"]),
                "symbols": len(inventory["symbols"]),
                "colliding_ids": len(inventory["colliding_ids"]),
                "parser_error_files": len(inventory["parser_error_files"]),
            }
            print(f"{number}/{len(order)} {item['id']}: {index[item['id']]}", flush=True)
        except Exception as exc:  # noqa: BLE001 - recorded; snapshot is retried on resume
            failures.append({"id": item["id"], "error": f"{type(exc).__name__}: {exc}"})
            print(f"FAILED {item['id']}: {exc}", flush=True)
        write_json(
            args.out / "index.json", {"schema": VERSION, "instances": index, "failures": failures}
        )
    summary = {
        "schema": VERSION,
        "expected": len(order),
        "completed": len(index),
        "failures": failures,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_identity": "source_sha256 in manifest; git commit alone does not identify uncommitted changes",
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "parser_error_instances": [q for q, value in index.items() if value["parser_error_files"]],
        "collision_instances": [q for q, value in index.items() if value["colliding_ids"]],
    }
    write_json(args.out / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
