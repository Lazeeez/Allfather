"""Inspect flagged gold targets in cached Git blobs without fetching or modifying labels."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from allfather.parsing import symbols  # noqa: E402


def inspect(record: dict, target: dict, cache: Path) -> dict:
    path = target["id"].split("::", 1)[0]
    mirror = cache / (record["repo"].replace("/", "__") + ".git")
    process = subprocess.run(
        ["git", "show", f"{record['base_commit']}:{path}"],
        cwd=mirror,
        capture_output=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"},
        timeout=60,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.decode(errors="replace")[:500])
    source = process.stdout
    language = symbols.language_of(path)
    tree = symbols.parse(source, language)
    matches = [
        symbol
        for symbol in symbols.extract_symbols(source, path, tree)
        if symbol.id == target["id"] and not symbol.nested
    ]
    errors, stack = [], [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "ERROR" or node.is_missing:
            start, end = node.start_point[0] + 1, node.end_point[0] + 1
            errors.append(
                {
                    "kind": node.type,
                    "missing": node.is_missing,
                    "start": [start, node.start_point[1]],
                    "end": [end, node.end_point[1]],
                    "byte_range": [node.start_byte, node.end_byte],
                    "line_overlap_with_target": any(
                        s.start_line <= end and start <= s.end_line for s in matches
                    ),
                    "text_prefix": source[node.start_byte : node.end_byte].decode(
                        "utf-8", "replace"
                    )[:140],
                }
            )
        stack.extend(reversed(node.children))
    return {
        "id": record["id"],
        "repo": record["repo"],
        "base_commit": record["base_commit"],
        "target": target["id"],
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "source_bytes": len(source),
        "language": language,
        "matches": [
            {
                "kind": s.kind,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "start_column": s.col,
            }
            for s in matches
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/repos")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    loaded = json.loads(args.review.read_bytes())
    records = loaded if isinstance(loaded, list) else loaded["records"]
    report = {
        "scope": "Only supplied complete records and flagged targets; no inference, gold edits or Git fetches.",
        "limitations": [
            "Line overlap is not proof of semantic extraction failure or gold invalidity.",
            "Columns are zero-based byte columns; lines are one-based.",
            "Source hashes identify local blobs; equivalence to PACE audit blobs requires its inventories.",
        ],
        "review_sha256": hashlib.sha256(args.review.read_bytes()).hexdigest(),
        "source_sha256": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path(__file__),
                ROOT / "src/allfather/parsing/symbols.py",
                ROOT / "src/allfather/parsing/python_symbols.py",
            )
        },
        "parser_versions": {
            name: importlib.metadata.version(name)
            for name in (
                "tree-sitter",
                "tree-sitter-python",
                "tree-sitter-go",
                "tree-sitter-javascript",
                "tree-sitter-typescript",
                "tree-sitter-java",
                "tree-sitter-rust",
            )
        },
        "records_received": len(records),
        "targets": [],
        "failures": [],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as output:
        for record in records:
            for target in record["gold"]:
                if target["status"] == "unique" and not target["file_has_parser_error"]:
                    continue
                try:
                    report["targets"].append(inspect(record, target, args.cache))
                except Exception as exc:
                    report["failures"].append(
                        {"id": record["id"], "target": target["id"], "error": str(exc)}
                    )
        output.write(json.dumps(report, indent=2) + "\n")
    print(f"Inspected {len(report['targets'])} targets; {len(report['failures'])} failures")
    return int(bool(report["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
