"""Verify a transferred membership audit against local predictions without extracting its tar."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from correct_swerank import recover  # noqa: E402
from swerank_export import swerank_id  # noqa: E402

SOURCES = (
    "scripts/audit_swerank_membership.py",
    "scripts/correct_swerank.py",
    "scripts/swerank_import.py",
    "scripts/swerank_export.py",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_archive(path: Path) -> dict[str, bytes]:
    files, names, roots = {}, set(), set()
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        require(
            len(members) <= 64 and sum(m.size for m in members) <= 256_000_000,
            "unexpected archive size",
        )
        for member in members:
            parts = PurePosixPath(member.name).parts
            require(
                not member.name.startswith("/")
                and not any(p in ("..", ".") for p in parts)
                and "\\" not in member.name,
                "unsafe archive member",
            )
            require(member.name not in names and bool(parts), "duplicate or empty archive member")
            names.add(member.name)
            roots.add(parts[0])
            if member.isdir():
                require(len(parts) == 1, "unexpected archive directory")
                continue
            require(
                member.isfile() and len(parts) == 2 and ":" not in member.name,
                "unexpected archive member type/path",
            )
            files[parts[1]] = archive.extractfile(member).read()
    require(len(roots) == 1 and "summary.json" in files, "archive must have one audit root")
    return files


def json_rows(raw: bytes) -> list[dict]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def verify_line_endings(working: bytes, committed: bytes, expected: str) -> bytes:
    """Accept only a demonstrated CRLF checkout difference from the exact Git blob."""
    require(
        digest(committed) == expected and working.replace(b"\r\n", b"\n") == committed,
        "correction audit differs beyond verified Git line endings",
    )
    return committed


def verify_rows(
    rows: list[dict], expected: list[dict], corpora: dict, changes: list[dict], condition: str
) -> tuple[Counter, list[dict]]:
    lookup = {r["id"]: r for r in expected}
    require(len(lookup) == len(expected), "duplicate expected prediction ID")
    require(
        len(rows) == len(expected) and [r["id"] for r in rows] == [r["id"] for r in expected],
        "membership row IDs/order differ from predictions",
    )
    recovered = {(c["id"], c["slot"]) for c in changes}
    counts, ambiguous = Counter(), []
    for row in rows:
        q = row["id"]
        require(row["condition"] == condition, "wrong report condition")
        evidence = corpora[(condition, q)]
        require("error" not in evidence, "corpus evidence unavailable")
        predictions = (lookup[q].get("answer") or {}).get("functions", [])
        require(len(row["slots"]) == len(predictions), "missing or extra rank slots")
        counts["issues"] += 1
        counts["corpora_available"] += 1
        for position, (slot, prediction) in enumerate(
            zip(row["slots"], predictions, strict=True), 1
        ):
            doc = (
                swerank_id(prediction["file"], prediction["name"])
                if prediction.get("name")
                else prediction["file"]
            )
            require(doc in evidence["requested_counts"], "corpus record omits requested ID")
            occurrence = evidence["requested_counts"][doc]
            status = "missing" if occurrence == 0 else "unique" if occurrence == 1 else "ambiguous"
            was_recovered = (q, position) in recovered
            require(
                slot
                == {
                    "slot": position,
                    "document_id": doc,
                    "recovered": was_recovered,
                    "occurrences": occurrence,
                    "membership": status,
                },
                "membership slot disagrees with prediction/corpus evidence",
            )
            counts["slots"] += 1
            counts[status] += 1
            if was_recovered:
                counts["recovered_slots"] += 1
                counts["recovered_" + status] += 1
                if status == "ambiguous":
                    ambiguous.append({"id": q, **slot})
    return counts, ambiguous


def verify(path: Path) -> dict:
    files = read_archive(path)
    summary = json.loads(files["summary.json"])
    require(summary["schema"] == "swerank-corpus-membership-v1", "unexpected audit schema")
    require(
        summary["integrity_ok"] is True and summary["failures"] == [],
        "PACE audit did not finish cleanly",
    )
    correction_path = ROOT / "results/research/corrections/import-v1/audit.json"
    correction_raw = correction_path.read_bytes()
    transport = []
    if digest(correction_raw) != summary["correction_audit_sha256"]:
        relative = correction_path.relative_to(ROOT).as_posix()
        committed = subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT)
        checked = verify_line_endings(correction_raw, committed, summary["correction_audit_sha256"])
        transport.append(
            {
                "path": relative,
                "working_sha256": digest(correction_raw),
                "committed_sha256": digest(checked),
                "difference": "CRLF checkout versus LF Git blob only",
                "git_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
            }
        )
        correction_raw = checked
    correction = json.loads(correction_raw)
    runs = set(correction["runs"])
    require(
        runs == set(summary["runs"]) == set(summary["inputs_sha256"]), "run membership mismatch"
    )
    require(set(summary["source_sha256"]) == set(SOURCES), "unexpected source fingerprint set")
    for name in SOURCES:
        require(
            digest((ROOT / name).read_bytes()) == summary["source_sha256"][name],
            f"source hash mismatch: {name}",
        )
    expected_outputs = {r + ".jsonl" for r in runs} | {"corpora.jsonl"}
    require(
        set(summary["outputs_sha256"]) == expected_outputs
        and set(files) == expected_outputs | {"summary.json"},
        "archive output membership mismatch",
    )
    for name in expected_outputs:
        require(
            digest(files[name]) == summary["outputs_sha256"][name], f"output hash mismatch: {name}"
        )
    corpus_rows = json_rows(files["corpora.jsonl"])
    corpora = {(r["condition"], r["id"]): r for r in corpus_rows}
    require(len(corpora) == len(corpus_rows), "duplicate corpus evidence")
    for r in corpus_rows:
        require(
            "error" not in r and bool(re.fullmatch("[0-9a-f]{64}", r["sha256"])),
            "missing/invalid corpus fingerprint",
        )
        for k in ("bytes", "documents", "distinct_ids", "colliding_ids"):
            require(type(r[k]) is int and r[k] >= 0, "invalid corpus count")
        require(
            r["colliding_ids"] <= r["distinct_ids"] <= r["documents"]
            and r["colliding_ids"] <= r["documents"] - r["distinct_ids"],
            "inconsistent corpus totals",
        )
        require(
            all(
                type(n) is int and 0 <= n <= r["documents"] for n in r["requested_counts"].values()
            ),
            "invalid ID occurrence count",
        )
    total, verified_runs, ambiguous, expected_corpora = Counter(), {}, [], set()
    recovered_pairs = set()
    for run in sorted(runs):
        original_path = ROOT / "results/research/frontier" / (run + ".jsonl")
        corrected_path = correction_path.parent / (run + ".jsonl")
        raw_original, raw_corrected = original_path.read_bytes(), corrected_path.read_bytes()
        require(
            digest(raw_original)
            == summary["inputs_sha256"][run]["original"]
            == correction["inputs_sha256"][original_path.relative_to(ROOT).as_posix()],
            "original predictions hash mismatch",
        )
        require(
            digest(raw_corrected) == summary["inputs_sha256"][run]["corrected"],
            "corrected predictions hash mismatch",
        )
        reproduced, changes = recover(json_rows(raw_original))
        expected = json_rows(raw_corrected)
        require(
            reproduced == expected and changes == correction["runs"][run]["changes"],
            "correction cannot be reproduced",
        )
        condition = "full" if correction["runs"][run]["set"].startswith("fresh-full") else "short"
        expected_corpora.update((condition, r["id"]) for r in expected)
        rows = json_rows(files[run + ".jsonl"])
        counts, run_ambiguous = verify_rows(rows, expected, corpora, changes, condition)
        recomputed = {"expected_issues": correction["runs"][run]["expected_instances"], **counts}
        require(
            recomputed == summary["runs"][run]
            and counts["issues"] == recomputed["expected_issues"],
            f"summary count mismatch: {run}",
        )
        verified_runs[run] = recomputed
        total.update(counts)
        ambiguous.extend({"run": run, **row} for row in run_ambiguous)
        recovered_pairs.update(
            (r["id"], s["document_id"]) for r in rows for s in r["slots"] if s["recovered"]
        )
    require(expected_corpora == set(corpora), "extra or missing corpus evidence")
    require(
        summary["all_predictions_present"] is (total["missing"] == 0)
        and summary["all_recovered_present"] is (total["recovered_missing"] == 0),
        "presence flags disagree with slots",
    )
    short_ids = {q for condition, q in corpora if condition == "short"}
    full_ids = {q for condition, q in corpora if condition == "full"}
    require(short_ids == full_ids, "short/full corpus cohorts differ")
    paired_equal = sum(
        corpora[("short", q)]["sha256"] == corpora[("full", q)]["sha256"] for q in short_ids
    )
    ambiguous_pairs = {(r["id"], r["document_id"]) for r in ambiguous}
    return {
        "schema": "swerank-membership-verification-v1",
        "verified": True,
        "archive_sha256": digest(path.read_bytes()),
        "archive_bytes": path.stat().st_size,
        "summary_sha256": digest(files["summary.json"]),
        "verifier_sha256": digest(Path(__file__).read_bytes()),
        "verified_checkout_differences": transport,
        "verification": {
            "source_files": len(SOURCES),
            "prediction_files": 2 * len(runs),
            "output_files": len(expected_outputs),
            "run_summaries": len(runs),
            "corpus_records": len(corpora),
        },
        "counts": dict(total),
        "distinct_issue_document_pairs_recovered": len(recovered_pairs),
        "distinct_ambiguous_recovered_pairs": len(ambiguous_pairs),
        "short_full_corpus_pairs": len(short_ids),
        "short_full_hashes_equal": paired_equal,
        "runs": verified_runs,
        "ambiguous_recovered_slots": ambiguous,
        "limitations": summary["limitations"]
        + [
            "The corpus bytes and index files were not transferred; local checks verify hashes and internal consistency of the PACE evidence, not an independent rescan of those files.",
            "Totals count run slots and include repeated predictions and reused subsets; they are not distinct issues or independent observations.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), "use a new verification output path")
    result = verify(args.archive)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "verified",
                    "verification",
                    "counts",
                    "distinct_issue_document_pairs_recovered",
                    "distinct_ambiguous_recovered_pairs",
                    "short_full_hashes_equal",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
