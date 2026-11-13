"""Inventory every tracked file, parse Python/JSON, and map code entry points.

This is a structural audit, not a claim of manual review or runtime correctness.
Only tracked files are read; private caches, credentials and local runs are excluded.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists; use a new audit filename")
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    entries, errors = {}, []
    for name in filter(None, paths):
        path = ROOT / name
        content = path.read_bytes()
        entry = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        entries[name] = entry
        try:
            text = content.decode("utf-8-sig")
            if "\x00" in text:
                raise UnicodeError("binary")
        except UnicodeError:
            entry["kind"] = "binary"
            continue
        entry.update(kind="text", lines=len(text.splitlines()))
        try:
            if path.suffix == ".py":
                tree = ast.parse(text, filename=name)
                entry["docstring"] = ast.get_docstring(tree)
                entry["definitions"] = [
                    {"name": node.name, "line": node.lineno, "kind": type(node).__name__}
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                ]
                entry["imports"] = sorted(
                    {
                        module
                        for node in ast.walk(tree)
                        for module in (
                            [node.module or ""]
                            if isinstance(node, ast.ImportFrom)
                            else [alias.name for alias in node.names]
                            if isinstance(node, ast.Import)
                            else []
                        )
                    }
                )
            elif path.suffix == ".json":
                value = json.loads(text)
                entry["json_type"] = type(value).__name__
            elif path.suffix == ".jsonl":
                entry["records"] = sum(
                    1 for line in text.splitlines() if line and json.loads(line) is not None
                )
            elif path.suffix == ".md":
                entry["headings"] = [line for line in text.splitlines() if line.startswith("#")]
        except (SyntaxError, ValueError) as exc:
            errors.append({"path": name, "error": str(exc)})
    report = {
        "base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "scope": "Tracked working-tree files; all bytes read and hashed. AST/JSON parsing is not semantic review.",
        "tracked_files": len(entries),
        "by_area": dict(
            sorted(
                Counter(
                    Path(name).parts[0] if "/" in name else "(root)" for name in entries
                ).items()
            )
        ),
        "by_suffix": dict(sorted(Counter(Path(name).suffix for name in entries).items())),
        "parse_errors": errors,
        "files": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "files"}, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
