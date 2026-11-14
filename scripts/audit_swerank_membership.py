"""Check saved SweRank IDs against existing BEIR exports without rebuilding or rescoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from correct_swerank import recover  # noqa: E402
from swerank_export import swerank_id  # noqa: E402


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan_corpus(path: Path, wanted: set[str]) -> dict:
    hasher, counts = hashlib.sha256(), Counter()
    before = path.stat()
    with path.open("rb") as handle:
        for line in handle:
            hasher.update(line)
            if not line.strip():
                continue
            record = json.loads(line)
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("_id"), str)
                or not record["_id"]
            ):
                raise ValueError("corpus row has no valid document ID")
            counts[record["_id"]] += 1
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("corpus changed during inspection")
    return {
        "sha256": hasher.hexdigest(),
        "bytes": after.st_size,
        "documents": sum(counts.values()),
        "distinct_ids": len(counts),
        "colliding_ids": sum(n > 1 for n in counts.values()),
        "requested_counts": {key: counts[key] for key in sorted(wanted)},
    }


def corpus_index(root: Path) -> tuple[dict, str]:
    raw = (root / "index.json").read_bytes()
    index = json.loads(raw)
    if not isinstance(index, dict) or len(set(index.values())) != len(index):
        raise ValueError("export index must map one folder per unique issue")
    if any(
        not folder or folder in (".", "..") or any(c in folder for c in "/\\:") for folder in index
    ):
        raise ValueError("unsafe export folder name")
    return {q: root / folder / "corpus.jsonl" for folder, q in index.items()}, digest(raw)


def audit(short: Path, full: Path, corrections: Path, out: Path) -> dict:
    if out.exists():
        raise ValueError("use a new output directory")
    indices, index_hashes = {}, {}
    for condition, root in (("short", short), ("full", full)):
        indices[condition], index_hashes[condition] = corpus_index(root)
    correction_raw = (corrections / "audit.json").read_bytes()
    correction = json.loads(correction_raw)
    pending, wanted, input_hashes = {}, defaultdict(set), {}
    for run, info in correction["runs"].items():
        original_path = ROOT / "results/research/frontier" / (run + ".jsonl")
        original_raw = original_path.read_bytes()
        relative = original_path.relative_to(ROOT).as_posix()
        if digest(original_raw) != correction["inputs_sha256"][relative]:
            raise ValueError(f"historical predictions changed: {run}")
        corrected_raw = (corrections / (run + ".jsonl")).read_bytes()
        original = [json.loads(s) for s in original_raw.splitlines() if s.strip()]
        corrected = [json.loads(s) for s in corrected_raw.splitlines() if s.strip()]
        reproduced, changes = recover(original)
        if reproduced != corrected or changes != info["changes"]:
            raise ValueError(f"import correction cannot be reproduced: {run}")
        if len({r["id"] for r in corrected}) != len(corrected):
            raise ValueError(f"duplicate prediction row: {run}")
        condition = "full" if info["set"].startswith("fresh-full") else "short"
        recovered = {(r["id"], r["slot"]) for r in changes}
        pending[run] = []
        for row in corrected:
            slots = []
            for slot, prediction in enumerate((row.get("answer") or {}).get("functions", []), 1):
                # Use the exact saved export spelling, without gold-aware normalization.
                doc = (
                    swerank_id(prediction["file"], prediction["name"])
                    if prediction.get("name")
                    else prediction["file"]
                )
                slots.append(
                    {"slot": slot, "document_id": doc, "recovered": (row["id"], slot) in recovered}
                )
                wanted[row["id"]].add(doc)
            pending[run].append({"id": row["id"], "condition": condition, "slots": slots})
        input_hashes[run] = {"original": digest(original_raw), "corrected": digest(corrected_raw)}
    out.mkdir(parents=True)
    cache, failures, corpus_evidence = {}, [], {}
    summaries, output_hashes = {}, {}
    for run, rows in pending.items():
        counts = Counter()
        serialized = []
        for row in rows:
            condition, q = row["condition"], row["id"]
            key = (condition, q)
            if key not in corpus_evidence:
                try:
                    path = indices[condition][q]
                    cache_key = (str(path.resolve()), tuple(sorted(wanted[q])))
                    if cache_key not in cache:
                        cache[cache_key] = scan_corpus(path, wanted[q])
                    corpus_evidence[key] = {"path": str(path), **cache[cache_key]}
                except (KeyError, OSError, ValueError) as exc:
                    corpus_evidence[key] = {"error": f"{type(exc).__name__}: {exc}"}
                    failures.append({"condition": condition, "id": q, **corpus_evidence[key]})
            evidence = corpus_evidence[key]
            counts["issues"] += 1
            counts["corpora_available"] += "error" not in evidence
            for slot in row["slots"]:
                occurrence = evidence.get("requested_counts", {}).get(slot["document_id"])
                status = (
                    "unavailable"
                    if occurrence is None
                    else "missing"
                    if occurrence == 0
                    else "unique"
                    if occurrence == 1
                    else "ambiguous"
                )
                slot.update({"occurrences": occurrence, "membership": status})
                counts["slots"] += 1
                counts[status] += 1
                if slot["recovered"]:
                    counts["recovered_slots"] += 1
                    counts["recovered_" + status] += 1
            serialized.append(json.dumps(row) + "\n")
        raw = "".join(serialized).encode()
        (out / (run + ".jsonl")).write_bytes(raw)
        output_hashes[run + ".jsonl"] = digest(raw)
        summaries[run] = {
            "expected_issues": correction["runs"][run]["expected_instances"],
            **dict(counts),
        }
        if counts["issues"] != summaries[run]["expected_issues"]:
            failures.append(
                {"run": run, "error": "observed issue count differs from frozen expected count"}
            )
    raw = "".join(
        json.dumps({"condition": condition, "id": q, **evidence}) + "\n"
        for (condition, q), evidence in sorted(corpus_evidence.items())
    ).encode()
    (out / "corpora.jsonl").write_bytes(raw)
    output_hashes["corpora.jsonl"] = digest(raw)
    result = {
        "schema": "swerank-corpus-membership-v1",
        "integrity_ok": not failures,
        "all_predictions_present": not failures
        and all(not r.get("missing", 0) for r in summaries.values()),
        "all_recovered_present": not failures
        and all(not r.get("recovered_missing", 0) for r in summaries.values()),
        "corpus_indices_sha256": index_hashes,
        "correction_audit_sha256": digest(correction_raw),
        "inputs_sha256": input_hashes,
        "outputs_sha256": output_hashes,
        "source_sha256": {
            p: digest((ROOT / p).read_bytes())
            for p in (
                "scripts/audit_swerank_membership.py",
                "scripts/correct_swerank.py",
                "scripts/swerank_import.py",
                "scripts/swerank_export.py",
            )
        },
        "runs": summaries,
        "failures": failures,
        "limitations": [
            "Membership is in the supplied saved exports, not a reconstruction of missing originals.",
            "Historical retrieval did not pin corpus hashes; this audit cannot prove these bytes are the original inference inputs.",
            "Ambiguous export IDs can identify multiple declarations; membership alone does not repair identity or labels.",
            "No predictions rerun, no outcomes rescored, and no labels removed or repaired.",
        ],
    }
    (out / "summary.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--short", type=Path, required=True)
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument(
        "--corrections", type=Path, default=ROOT / "results/research/corrections/import-v1"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.short, args.full, args.corrections, args.out)
    print(
        json.dumps(
            {
                "integrity_ok": result["integrity_ok"],
                "runs": result["runs"],
                "failures": len(result["failures"]),
            },
            indent=2,
        )
    )
    return 0 if result["integrity_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
