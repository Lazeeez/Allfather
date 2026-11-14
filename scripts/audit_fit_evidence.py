"""Inspect fit-only report/source visibility using cached base blobs and pinned tokenizers.

Post-hoc gold/merge evidence is diagnostic only; nothing here is an inference feature.
No downloads, Git fetches, model forward passes or gold edits are performed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from development_assets import MANIFEST, cached_models, digest  # noqa: E402

from allfather.index.chunker import MODULE, chunk_file  # noqa: E402
from allfather.index.snapshot import unit_key, unit_text  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(mirror: Path, args: list[str]) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=mirror,
        capture_output=True,
        timeout=60,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[:500])
    return result.stdout


def visible(tokenizer, text: str, limit: int) -> dict:
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoded["offset_mapping"]
    end = max((stop for _, stop in offsets[:limit]), default=0)
    return {
        "tokens": len(offsets),
        "limit": limit,
        "visible_char_end": end,
        "visible_text": text[:end],
        "prefix_sha256": sha(text[:end].encode()),
    }


def inspect_target(trace: dict, target: dict, source: bytes, tokenizer) -> dict:
    uid = target["id"]
    path = uid.split("::", 1)[0]
    chunks = [c for c in chunk_file(source, path) if c.kind != MODULE and c.id(path) == uid]
    if len(chunks) != 1 or len(target["retrieval_rows"]) != 1:
        raise ValueError(f"expected an audited unique fit target: {uid}")
    chunk = chunks[0]
    text = unit_text(chunk.qualname, chunk.text)
    row = trace["universe"][target["retrieval_rows"][0]]
    if row["id"] != uid or row["text_key"] != unit_key(text).hex():
        raise ValueError(f"source text differs from PACE row: {uid}")
    view = visible(tokenizer, text, 256)
    return {
        "id": uid,
        "kind": chunk.kind,
        "source_lines": [chunk.start_line, chunk.end_line],
        "source_sha256": sha(source),
        "text_key": row["text_key"],
        "indexed_characters": len(text),
        "document_tokens": view["tokens"],
        "visible_char_end": view["visible_char_end"],
        "visible_indexed_lines": len(view["visible_text"].splitlines()),
        "prefix_sha256": view["prefix_sha256"],
        "prefix_preview": view["visible_text"][:300],
        "indexed_text": text,
    }


def run(bundle: Path, out: Path) -> dict:
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer

    spec = json.loads(MANIFEST.read_bytes())
    models = cached_models(spec)
    for name, model in spec["models"].items():
        for filename, expected in model["files_sha256"].items():
            if digest(models[name] / filename) != expected:
                raise ValueError(f"pinned model asset differs: {name}/{filename}")
    ce = AutoTokenizer.from_pretrained(
        str(models["Qwen/Qwen3-Reranker-0.6B"]), local_files_only=True
    )
    mini = AutoTokenizer.from_pretrained(
        str(models["sentence-transformers/all-MiniLM-L6-v2"]), local_files_only=True
    )
    static = Tokenizer.from_file(str(models["minishlab/potion-code-16M"] / "tokenizer.json"))
    static.no_truncation()
    static.no_padding()
    gold = {
        r["id"]: r
        for r in map(json.loads, (ROOT / "data/fresh-full/gold.jsonl").read_bytes().splitlines())
    }
    analysis_path = ROOT / "results/research/corrections/development-analysis-v1/rows.jsonl"
    # Fail closed to the original fit projects before opening any trace or query.
    rows = [
        r for r in map(json.loads, analysis_path.read_bytes().splitlines()) if r["split"] == "fit"
    ]
    plan = json.loads((ROOT / "data/research/development-pilot-v1.json").read_bytes())
    if {r["id"] for r in rows} != {r["id"] for r in plan["instances"] if r["split"] == "fit"}:
        raise ValueError("fit membership mismatch")
    index = json.loads((bundle / "index.json").read_bytes())["completed"]
    records, reports = [], []
    out.mkdir(parents=True, exist_ok=False)
    for row in rows:
        target = gold[row["id"]]
        text = target["text"]
        ce_view = visible(ce, text, 512)
        mini_view = mini(text, truncation=True, max_length=256, return_offsets_mapping=True)
        mini_end = max((stop for _, stop in mini_view["offset_mapping"]), default=0)
        static_encoding = static.encode(text)
        static_end = max((stop for _, stop in static_encoding.offsets[:512]), default=0)
        views = {
            "ce512": ce_view["visible_char_end"],
            "minilm256": mini_end,
            "static512": static_end,
        }
        reports.append(
            {
                "id": row["id"],
                "query_characters": len(text),
                "query_sha256": sha(text.encode()),
                "ce_query_tokens": ce_view["tokens"],
                "visible_char_end": views,
                "truncated": {name: end < len(text.rstrip()) for name, end in views.items()},
            }
        )
        if any(a["hit@10"] for a in row["modes"]["strict_symbol"]["actions"].values()):
            continue
        trace = json.loads(gzip.decompress((bundle / index[row["id"]]["file"]).read_bytes()))
        if sha((bundle / index[row["id"]]["file"]).read_bytes()) != index[row["id"]]["sha256"]:
            raise ValueError("trace hash mismatch")
        mirror = ROOT / ".cache/repos" / (target["repo"].replace("/", "__") + ".git")
        sources, details, failures = {}, [], []
        for label in row["targets"]:
            path = label["id"].split("::", 1)[0]
            if path not in sources:
                source = git(mirror, ["show", f"{target['base_commit']}:{path}"])
                oid = hashlib.sha1(
                    b"blob " + str(len(source)).encode() + b"\0" + source
                ).hexdigest()
                if oid != next(f["blob"] for f in trace["files"] if f["path"] == path):
                    raise ValueError(f"base blob mismatch: {path}")
                sources[path] = source
            details.append(inspect_target(trace, label, sources[path], ce))
        changed = git(
            mirror,
            [
                "diff",
                "--name-status",
                "--no-renames",
                target["base_commit"],
                target["merge_commit"],
            ],
        ).decode("utf-8", "replace")
        changes = [
            {"status": line.split("\t", 1)[0], "path": line.split("\t", 1)[1]}
            for line in changed.splitlines()
        ]
        patches = {}
        for path in sources:
            try:
                patch = git(
                    mirror,
                    [
                        "diff",
                        "--no-ext-diff",
                        "--no-renames",
                        "-U4",
                        target["base_commit"],
                        target["merge_commit"],
                        "--",
                        path,
                    ],
                )
                patches[path] = {"sha256": sha(patch), "text": patch.decode("utf-8", "replace")}
            except RuntimeError as exc:
                failures.append({"path": path, "error": str(exc)})
        record = {
            "id": row["id"],
            "repo": target["repo"],
            "issue": target["issue"],
            "pr": target["pr"],
            "base_commit": target["base_commit"],
            "merge_commit": target["merge_commit"],
            "query": text,
            "query_views": reports[-1],
            "ce_visible_query": ce_view["visible_text"],
            "targets": details,
            "changed_paths": changes,
            "merge_subject": git(mirror, ["show", "-s", "--format=%s", target["merge_commit"]])
            .decode()
            .strip(),
            "patches": patches,
            "unavailable_patches": failures,
        }
        # Full query/source excerpts remain local review material, not packaged model inputs.
        filename = hashlib.sha256(row["id"].encode()).hexdigest() + ".json"
        (out / filename).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        records.append(
            {
                **{
                    k: record[k]
                    for k in (
                        "id",
                        "repo",
                        "issue",
                        "pr",
                        "base_commit",
                        "merge_commit",
                        "query_views",
                        "changed_paths",
                        "merge_subject",
                        "unavailable_patches",
                    )
                },
                "targets": [{k: v for k, v in t.items() if k != "indexed_text"} for t in details],
                "review_file": filename,
                "review_sha256": sha((out / filename).read_bytes()),
                "patch_sha256": {p: v["sha256"] for p, v in patches.items()},
            }
        )
    result = {
        "schema": "fit-evidence-audit-v1",
        "scope": "Post-hoc fit-only evidence visibility and source review; not causal annotation or a scored new method.",
        "analysis_sha256": sha(analysis_path.read_bytes()),
        "script_sha256": sha(Path(__file__).read_bytes()),
        "tokenizer_revisions": {k: v["revision"] for k, v in spec["models"].items()},
        "query_profiles": reports,
        "failures_reviewed": records,
        "limitations": [
            "Merge and gold information is diagnostic only and must not enter action selection.",
            "A token window ending before an edit-related line does not alone prove that truncation caused failure.",
            "Feature-addition reports are retained; additions outside base-snapshot target space require explicit task interpretation.",
            "Unavailable post-merge blobs are reported without fetching.",
        ],
    }
    (out / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Profiled {len(reports)} fit queries and inspected {len(records)} persistent failures")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
