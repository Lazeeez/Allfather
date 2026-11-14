"""Capture pinned fit patches, optionally retrieving missing blobs into OS temporary storage.

Existing Git mirrors remain read-only. Remote bytes must match the tree's Git blob ID.
No predictions are read, no labels changed, and no model assets are downloaded.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from development_assets import digest  # noqa: E402
from replay_text_views import write_json  # noqa: E402
from validate_development_replay import require  # noqa: E402

from allfather.index.chunker import MODULE, chunk_file  # noqa: E402
from allfather.parsing.symbols import language_of  # noqa: E402

ZERO = "0" * 40


def symbols(source: bytes, path: str) -> list:
    # chunk_file defaults unknown paths to Python; archives/configs are not source units.
    return [c for c in chunk_file(source, path) if c.kind != MODULE] if language_of(path) else []


def git(mirror: Path, args: list[str], objects: Path) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=mirror,
        capture_output=True,
        timeout=120,
        env={
            **os.environ,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(objects.resolve()),
        },
    )
    require(result.returncode == 0, result.stderr.decode("utf-8", "replace")[:500])
    return result.stdout


def changed_files(raw: bytes) -> list[dict]:
    fields = raw.split(b"\0")
    require(fields[-1] == b"" and len(fields) % 2 == 1, "malformed raw diff")
    result = []
    for i in range(0, len(fields) - 1, 2):
        mode_a, mode_b, old, new, status = fields[i].decode("ascii").split()
        require(mode_a.startswith(":"), "malformed raw mode")
        require(status in ("A", "M", "D", "T"), "renames must be disabled")
        require(
            all(len(x) == 40 and all(c in "0123456789abcdef" for c in x) for x in (old, new)),
            "invalid object ID",
        )
        result.append(
            {
                "path": fields[i + 1].decode("utf-8"),
                "status": status,
                "old_mode": mode_a[1:],
                "new_mode": mode_b,
                "old_blob": old,
                "new_blob": new,
            }
        )
    return result


def verified_object(data: bytes, oid: str) -> bytes:
    raw = b"blob " + str(len(data)).encode() + b"\0" + data
    require(hashlib.sha1(raw).hexdigest() == oid, "downloaded blob does not match pinned tree")
    return zlib.compress(raw)


def blob(
    mirror: Path,
    objects: Path,
    repo: str,
    commit: str,
    path: str,
    oid: str,
    allow_download: bool,
    downloads: dict,
) -> bytes:
    if oid == ZERO:
        return b""
    try:
        return git(mirror, ["cat-file", "blob", oid], objects)
    except ValueError:
        if not allow_download:
            raise
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(path, safe='/')}"
    request = urllib.request.Request(url, headers={"User-Agent": "Allfather-pinned-patch-audit"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    compressed = verified_object(data, oid)
    target = objects / oid[:2] / oid[2:]
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(compressed)
    downloads[oid] = {"url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return data


def capture(record: dict, objects: Path, allow_download: bool, downloads: dict) -> dict:
    mirror = ROOT / ".cache/repos" / (record["repo"].replace("/", "__") + ".git")
    base, merge = record["base_commit"], record["merge_commit"]
    changes = changed_files(
        git(mirror, ["diff", "--raw", "--no-renames", "--abbrev=40", "-z", base, merge], objects)
    )
    for entry in changes:
        path = entry["path"]
        try:
            require(
                entry["old_mode"] != "160000" and entry["new_mode"] != "160000",
                "gitlink requires separate submodule audit",
            )
            before = blob(
                mirror,
                objects,
                record["repo"],
                base,
                path,
                entry["old_blob"],
                allow_download,
                downloads,
            )
            after = blob(
                mirror,
                objects,
                record["repo"],
                merge,
                path,
                entry["new_blob"],
                allow_download,
                downloads,
            )
            # Verify local bytes too; do not rely only on the download check.
            for data, oid in ((before, entry["old_blob"]), (after, entry["new_blob"])):
                if oid != ZERO:
                    verified_object(data, oid)
            patch = git(
                mirror,
                [
                    "diff",
                    "--no-ext-diff",
                    "--no-textconv",
                    "--no-renames",
                    "-U3",
                    base,
                    merge,
                    "--",
                    path,
                ],
                objects,
            )
            entry.update(
                patch=patch.decode("utf-8", "replace"),
                patch_sha256=hashlib.sha256(patch).hexdigest(),
            )
            old_symbols = symbols(before, path)
            new_symbols = symbols(after, path)
            old_ids = {c.id(path) for c in old_symbols}
            entry["new_symbol_ids"] = sorted({c.id(path) for c in new_symbols} - old_ids)
            entry["gold_base_context"] = [
                {
                    "id": c.id(path),
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "text": c.text,
                }
                for c in old_symbols
                if c.id(path) in record["gold_functions"]
            ]
        except Exception as exc:
            entry["unavailable"] = f"{type(exc).__name__}: {exc}"
    return {
        **{
            k: record[k]
            for k in ("id", "repo", "issue", "pr", "base_commit", "merge_commit", "gold_functions")
        },
        "changes": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--download-missing", action="store_true")
    args = parser.parse_args()
    require(not args.out.exists(), "use a new output directory")
    plan_path = ROOT / "data/research/development-pilot-v1.json"
    data_path = ROOT / "data/fresh-full/gold.jsonl"
    stage = ROOT / "results/research/corrections/task-audit-stage-a-v1"
    summary = json.loads((stage / "summary.json").read_bytes())
    require(
        digest(stage / "rows.jsonl") == summary["rows_sha256"], "frozen report annotations changed"
    )
    plan = json.loads(plan_path.read_bytes())
    require(digest(data_path) == plan["dataset_sha256"], "dataset changed")
    selected = [r for r in plan["instances"] if r["split"] == "fit"]
    data = {r["id"]: r for r in map(json.loads, data_path.read_bytes().splitlines())}
    manifest = {
        "schema": "fit-patch-audit-v1",
        "stage_a_rows_sha256": summary["rows_sha256"],
        "plan_sha256": digest(plan_path),
        "dataset_sha256": digest(data_path),
        "script_sha256": digest(Path(__file__)),
        "source_sha256": {
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in sorted((ROOT / "src/allfather").rglob("*.py"))
        },
        "packages": {
            name: importlib.metadata.version(name)
            for name in (
                "tree-sitter",
                "tree-sitter-python",
                "tree-sitter-go",
                "tree-sitter-java",
                "tree-sitter-rust",
                "tree-sitter-javascript",
                "tree-sitter-typescript",
            )
        },
        "fit_ids": [r["id"] for r in selected],
        "download_missing": args.download_missing,
        "downloads": {},
    }
    args.out.mkdir(parents=True)
    completed, failures = {}, []
    with tempfile.TemporaryDirectory(prefix="allfather-patch-audit-") as temp:
        objects = Path(temp) / "objects"
        objects.mkdir()
        for item in selected:
            qid = item["id"]
            try:
                record = data[qid]
                require(
                    all(item[k] == record[k] for k in ("id", "repo", "base_commit")),
                    "snapshot join mismatch",
                )
                result = capture(record, objects, args.download_missing, manifest["downloads"])
                filename = hashlib.sha256(qid.encode()).hexdigest() + ".json"
                write_json(args.out / filename, result)
                entry = {
                    "file": filename,
                    "sha256": digest(args.out / filename),
                    "changed_files": len(result["changes"]),
                    "unavailable_patches": sum("unavailable" in c for c in result["changes"]),
                }
                completed[qid] = entry
                print(
                    qid,
                    entry["changed_files"],
                    "files;",
                    entry["unavailable_patches"],
                    "unavailable",
                    flush=True,
                )
            except Exception as exc:
                failures.append({"id": qid, "error": str(exc)})
                print("FAILED", failures[-1], flush=True)
            write_json(args.out / "index.json", {"completed": completed, "failures": failures})
        write_json(args.out / "manifest.json", manifest)
    write_json(
        args.out / "summary.json",
        {
            "expected": len(selected),
            "completed": len(completed),
            "failures": failures,
            "downloaded_blobs": len(manifest["downloads"]),
            "unavailable_patches": sum(e["unavailable_patches"] for e in completed.values()),
        },
    )
    return int(bool(failures) or any(e["unavailable_patches"] for e in completed.values()))


if __name__ == "__main__":
    raise SystemExit(main())
