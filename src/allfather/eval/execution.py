"""Freeze outcome-independent execution order and reject incompatible run resumption."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_plan(ids: list[str], items: dict, recipe: dict, seed: int, limit: int = 0) -> dict:
    if not ids or len(set(ids)) != len(ids) or limit < 0:
        raise ValueError("execution needs nonempty unique IDs and a nonnegative limit")
    metadata = [
        {
            "id": q,
            "repo": items[q]["repo"],
            "base_commit": items[q]["base_commit"],
            "text_sha256": digest(items[q]["text"].encode()),
        }
        for q in sorted(ids)
    ]
    ordered = sorted(
        ids, key=lambda q: (digest(json.dumps([seed, q], separators=(",", ":")).encode()), q)
    )
    selected = ordered[:limit] if limit else ordered
    return {
        "schema": "research-execution-v1",
        "seed": seed,
        "limit": limit,
        "order_rule": "SHA256 of compact JSON [seed, id]; no outcome or label enters ordering",
        "recipe": recipe,
        "inputs": metadata,
        "ids": selected,
        "projects": dict(sorted(Counter(items[q]["repo"].casefold() for q in selected).items())),
        "scope": "Execution reproducibility only; not proof of unseen data or model isolation.",
    }


def bind_run(target: Path, plan: dict) -> tuple[str, set[str]]:
    """Freeze before inference; historical outputs without a matching manifest require a new tag."""
    manifest = target.with_suffix(".execution.json")
    errors = target.with_suffix(".errors.jsonl")
    raw = (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode()
    if manifest.exists():
        if manifest.read_bytes() != raw:
            raise ValueError("run inputs/recipe/order changed; choose a new run tag")
    elif target.exists() or errors.exists():
        raise ValueError("historical run has no execution manifest; choose a new run tag")
    identity, done = digest(raw), set()
    for path in (target, errors):
        if not path.exists():
            continue
        for line in path.read_bytes().splitlines():
            row = json.loads(line)
            if row.get("execution_manifest_sha256") != identity or row["id"] not in plan["ids"]:
                raise ValueError("result row is outside the frozen execution plan")
            if path == target:
                if row["id"] in done:
                    raise ValueError("duplicate completed run ID")
                done.add(row["id"])
    if not manifest.exists():
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("xb") as handle:
            handle.write(raw)
    return identity, done


def source_hashes(root: Path, scripts: list[str]) -> dict[str, str]:
    paths = sorted({*root.joinpath("src/allfather").rglob("*.py"), *(root / p for p in scripts)})
    return {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in paths}
