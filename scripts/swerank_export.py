"""Export a set for SweRank's retrievers (ADR 0033, tier T1), in the per-issue BEIR layout they read.

    uv run python scripts/swerank_export.py --set fresh --out ../swerank-fresh

One folder per issue, named <prefix><issue id with unsafe characters replaced>, holding:
corpus.jsonl (every non-test function, method and class at the base commit, split by Allfather's
own chunker so both systems see the same units; _id is SweRank's "path/Class/method" form and the
text starts with the file path, as in the authors' corpora), queries.jsonl (the issue) and
qrels/test.tsv (the answer key). index.json maps folder names back to issue ids. Copy the output
directory to PACE and run cluster/swerank/retrieve.sbatch with DATA pointing at it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from frontier import load_set  # noqa: E402

from allfather.index.chunker import MODULE, chunk_file  # noqa: E402
from allfather.parsing.symbols import is_test_path, language_of  # noqa: E402
from allfather.repos import BlobReader, RepoCache  # noqa: E402


def swerank_id(path: str, qualname: str) -> str:
    return f"{path}/{qualname.replace('.', '/')}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prefix", default="fresh-function_")
    args = ap.parse_args()
    ids, items = load_set(args.set)
    cache = RepoCache(ROOT / ".cache" / "repos")
    index = {}
    for q in ids:
        item = items[q]
        if not item["gold"]:
            continue
        folder = args.out / f"{args.prefix}{re.sub(r'[^A-Za-z0-9_.-]', '_', q)}"
        index[folder.name] = q
        if (folder / "qrels" / "test.tsv").exists():
            continue
        entries = [
            e
            for e in cache.list_tree(item["repo"], item["base_commit"])
            if language_of(e.path) and not is_test_path(e.path)
        ]
        cache.prefetch_blobs(item["repo"], [f"{item['base_commit']}:{e.path}" for e in entries])
        corpus = []
        with BlobReader(cache.ensure_commit(item["repo"], item["base_commit"])) as reader:
            for e in entries:
                for c in chunk_file(reader.read(e.oid), e.path):
                    if c.kind != MODULE:
                        corpus.append(
                            {
                                "_id": swerank_id(e.path, c.qualname),
                                "title": "",
                                "text": f"{e.path}\n{c.text}",
                            }
                        )
        gold = {swerank_id(*g.split("::", 1)) for g in item["gold"]}
        (folder / "qrels").mkdir(parents=True, exist_ok=True)
        with (folder / "corpus.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
            for doc in corpus:
                handle.write(json.dumps(doc) + "\n")
        (folder / "queries.jsonl").write_text(
            json.dumps({"_id": q, "text": item["text"]}) + "\n", encoding="utf-8", newline="\n"
        )
        (folder / "qrels" / "test.tsv").write_text(
            "query-id\tcorpus-id\tscore\n" + "".join(f"{q}\t{g}\t1\n" for g in sorted(gold)),
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"  {q}: {len(corpus)} units, {len(gold)} gold, {sum(1 for d in corpus if d['_id'] in gold)} found in the corpus",
            flush=True,
        )
    (args.out / "index.json").write_text(
        json.dumps(index, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {len(index)} folders to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
