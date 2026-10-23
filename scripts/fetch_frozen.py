import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

from allfather.eval.dataset import load_instances
from allfather.search.retriever import BM25Retriever

EMBEDDING = ("jinaai/jina-code-embeddings-0.5b", "4db235132dafbe56a8b9c5f59b59795ecf58a4a7")
RERANKER_BASE = ("Qwen/Qwen3-Reranker-0.6B", "e61197ed45024b0ed8a2d74b80b4d909f1255473")
HOLDOUT = Path("data/holdout/manifest.json")
HOLDOUT_GOLD = Path("data/gold/odin_holdout.jsonl")


def models() -> None:
    snapshot_download(EMBEDDING[0], revision=EMBEDDING[1], max_workers=2)
    snapshot_download(RERANKER_BASE[0], revision=RERANKER_BASE[1], max_workers=2)
    loaded = Path(snapshot_download(RERANKER_BASE[0], max_workers=2)).name
    if loaded != RERANKER_BASE[1]:
        sys.exit(
            f"{RERANKER_BASE[0]} resolves to {loaded} here, not the frozen {RERANKER_BASE[1]} (ADR 0032)"
        )
    if subprocess.run([sys.executable, "scripts/adapters.py", "fetch"]).returncode:
        sys.exit(
            "the reranker adapters could not be fetched (a Hugging Face token with access is needed)"
        )
    print("models ready", flush=True)


def commits() -> dict[str, set[str]]:
    manifest = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    for name in manifest["files"]:
        hf_hub_download(
            manifest["source"], name, repo_type="dataset", revision=manifest["revision"]
        )
    gold = [
        json.loads(line) for line in HOLDOUT_GOLD.read_text(encoding="utf-8").splitlines() if line
    ]
    scored = {g["instance_id"] for g in gold if g["files"] or g["functions"] or g["classes"]}
    wanted: dict[str, set[str]] = defaultdict(set)
    for instance in manifest["instances"]:
        if instance["instance_id"] in scored:
            wanted[instance["repo"]].add(instance["base_commit"])
    skipped = len(manifest["instances"]) - len(scored)
    print(
        f"holdout files ready: {len(scored)} issues to score, {skipped} without a target skipped",
        flush=True,
    )
    lite = load_instances("lite", "test")
    for instance in lite:
        wanted[instance.repo].add(instance.base_commit)
    print(f"lite ready: {len(lite)} issues", flush=True)
    return wanted


def mirrors(wanted: dict[str, set[str]]) -> None:
    retriever = BM25Retriever(exclude_tests=True, analysis_cache=False)
    for n, repo in enumerate(sorted(wanted), start=1):
        retriever.indexer.prefetch(repo, wanted[repo])
        print(f"  {n}/{len(wanted)} {repo}: {len(wanted[repo])} commits", flush=True)
    retriever.close()


def main() -> int:
    import sentence_transformers
    import torch

    print(
        f"torch {torch.__version__}, sentence-transformers {sentence_transformers.__version__}",
        flush=True,
    )
    models()
    mirrors(commits())
    print("fetch finished", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
