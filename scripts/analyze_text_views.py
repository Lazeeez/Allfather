"""Verify and score the frozen fit-only context experiment, without inference."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from analyze_development_replay import diagnose, provenance, score_rows  # noqa: E402
from analyze_inventory_scores import paired_clusters, verify_bundle  # noqa: E402
from replay_text_views import POOL_DEPTHS, PROTOCOL, inputs  # noqa: E402
from text_views import DOC_VIEWS, QUERY_VIEWS, token_hash  # noqa: E402
from validate_development_replay import (  # noqa: E402
    digest,
    nonnegative,
    ordered,
    require,
    valid_rows,
    validate_trace,
)

ACTIONS = tuple(f"{p}_{q}_{d}" for p in POOL_DEPTHS for q in QUERY_VIEWS for d in DOC_VIEWS)
METRICS = ("hit@1", "hit@5", "hit@10", "recall@10", "all@10", "mrr@10")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blend_rows(local: list[int], raw: list[float]) -> list[int]:
    """Independent reconstruction of the frozen rank-plus-CE blend."""

    def z(values):
        values = np.asarray(values, dtype=float)
        return (
            (values - values.mean()) / values.std()
            if len(values) and values.std() > 0
            else np.zeros_like(values)
        )

    n = len(raw)
    combined = z(-np.log1p(np.arange(1, n + 1))) + z(raw)
    return ordered(local[:n], combined.tolist()) + local[n:]


def score_substitutions(record: dict, parent: dict, targets: list[dict]) -> list[dict]:
    """Label-dependent post-hoc diagnostics; these hybrids are not runtime policies.

    For each read gold row, substitute its score alone or all other candidate scores.
    Only document views change: all comparisons use the same prefix query.
    """
    results = []
    for pool in POOL_DEPTHS:
        baseline = record["actions"][f"{pool}_prefix_prefix"]
        local = parent["actions"][f"{pool}_local"]["ranked_rows"]
        read = baseline["read_rows"]
        for target in targets:
            for row in target["retrieval_rows"]:
                if row not in read:
                    continue
                position = read.index(row)
                for view in DOC_VIEWS[1:]:
                    variant = record["actions"][f"{pool}_prefix_{view}"]
                    one = list(baseline["raw_scores"])
                    one[position] = variant["raw_scores"][position]
                    others = list(variant["raw_scores"])
                    others[position] = baseline["raw_scores"][position]
                    results.append(
                        {
                            "id": target["id"],
                            "row": row,
                            "pool": pool,
                            "document_view": view,
                            "baseline_score": baseline["raw_scores"][position],
                            "variant_score": variant["raw_scores"][position],
                            "baseline_rank": baseline["ranked_rows"].index(row) + 1,
                            "variant_rank": variant["ranked_rows"].index(row) + 1,
                            "target_score_only_rank": blend_rows(local, one).index(row) + 1,
                            "other_candidate_scores_only_rank": blend_rows(local, others).index(row)
                            + 1,
                        }
                    )
    return results


def read_archive(path: Path, expected: set[str]) -> dict[str, bytes]:
    """Read only the exact expected regular members; never extract archive paths."""
    files, seen = {}, set()
    with tarfile.open(path, "r:gz") as handle:
        for member in handle:
            name = member.name
            parts = PurePosixPath(name).parts
            require(name not in seen, "duplicate archive member")
            seen.add(name)
            require(
                parts
                and parts[0] == "fit-text-views-v1"
                and ".." not in parts
                and "\\" not in name
                and ":" not in name,
                "unsafe archive path",
            )
            if member.isdir():
                require(name == "fit-text-views-v1", "unexpected archive directory")
                continue
            require(member.isfile(), "unsupported archive entry")
            require(len(parts) == 2 and parts[1] in expected, "unexpected archive file")
            require(0 <= member.size <= 100_000_000, "unexpected archive member size")
            with handle.extractfile(member) as stream:
                files[parts[1]] = stream.read()
    require(set(files) == expected, "missing archive files")
    return files


def validate_capture(record: dict, parent: dict, prepared: dict, manifest_hash: str) -> dict:
    """Recompute all blends and parity; token views must equal the pre-run reference."""
    require(record["id"] == parent["id"], "trace identity mismatch")
    require(record["manifest_sha256"] == manifest_hash, "trace manifest mismatch")
    require(record["prepared"] == prepared, "token views differ from frozen preparation")
    require(nonnegative(record["prepare_seconds"]), "invalid preparation time")
    require(set(record["actions"]) == set(ACTIONS), "missing/unexpected action")
    require(
        len(record["execution_order"]) == len(ACTIONS)
        and set(record["execution_order"]) == set(ACTIONS),
        "invalid execution order",
    )
    parity = {}
    for pool, depth in POOL_DEPTHS.items():
        local = parent["actions"][f"{pool}_local"]["ranked_rows"]
        read = local[:depth]
        require(prepared["pools"][pool] == read, "prepared read set changed")
        prior = parent["actions"][f"{pool}_ce{depth}"]
        for q in QUERY_VIEWS:
            query = prepared["queries"][q]
            require(token_hash(query["ids"]) == query["sha256"], "query token hash mismatch")
            require(
                len(query["ids"]) == min(512, prepared["query_tokens_full"]), "query budget changed"
            )
            for d in DOC_VIEWS:
                action = record["actions"][f"{pool}_{q}_{d}"]
                require(action["read_rows"] == read, "candidate read set/order changed")
                raw = action["raw_scores"]
                require(len(raw) == len(read) and np.isfinite(raw).all(), "invalid raw scores")
                valid_rows(action["ranked_rows"], len(parent["universe"]))

                def z(x):
                    x = np.asarray(x, dtype=float)
                    return (x - x.mean()) / x.std() if len(x) and x.std() > 0 else np.zeros_like(x)

                combined = z(-np.log1p(np.arange(1, len(read) + 1))) + z(raw)
                rebuilt = ordered(read, combined.tolist()) + local[len(read) :]
                require(action["ranked_rows"] == rebuilt, "blend or untouched ranking tail changed")
                require(nonnegative(action["seconds"]), "invalid action time")
                require(
                    type(action["tokens_computed"]) is int
                    and action["tokens_computed"] == prior["tokens_computed"],
                    "token budget differs from original baseline",
                )
                for row in read:
                    view = prepared["views"][q][str(row)][d]
                    require(
                        len(view["ids"]) == min(256, prepared["doc_tokens_full"][str(row)]),
                        "document budget changed",
                    )
                    require(
                        token_hash(view["ids"]) == view["sha256"], "document token hash mismatch"
                    )
        baseline = record["actions"][f"{pool}_prefix_prefix"]
        parity[pool] = {
            "rankings_equal": baseline["ranked_rows"] == prior["ranked_rows"],
            "scores_max_abs_difference": float(
                np.max(np.abs(np.asarray(baseline["raw_scores"]) - prior["raw_scores"]), initial=0)
            ),
        }
    require(record["parent_parity"] == parity, "reported parity differs from raw evidence")
    require(
        all(v["rankings_equal"] and v["scores_max_abs_difference"] == 0 for v in parity.values()),
        "baseline parity failed; diagnose before scoring",
    )
    return parity


def score_capture(record: dict, parent: dict, gold: dict, audit: dict, item: dict) -> dict:
    old = diagnose(parent, gold, audit, item)
    targets = set(gold["gold_functions"])
    counts = Counter(u["id"] for u in parent["universe"])
    unique = {g["id"] for g in audit["gold"] if g["status"] == "unique" and counts[g["id"]] <= 1}
    result = {
        k: old[k]
        for k in (
            "id",
            "repo",
            "issue",
            "language",
            "gold_count",
            "all_gold_unique",
            "gold_in_parser_error_files",
        )
    }
    result["modes"] = {}
    for mode, eligible in (("strict_symbol", unique), ("name_group", targets)):
        actions = {}
        for name in ACTIONS:
            action = record["actions"][name]
            metrics = score_rows(action["ranked_rows"], parent["universe"], targets, eligible)
            pool = name.split("_", 1)[0]
            read_gold = sorted(
                {parent["universe"][r]["id"] for r in action["read_rows"]} & targets & eligible
            )
            failure = (
                "success"
                if metrics["hit@10"]
                else (
                    "ranking_miss"
                    if read_gold
                    else old["modes"][mode]["actions"][f"{pool}_ce{POOL_DEPTHS[pool]}"]["failure"]
                )
            )
            actions[name] = {
                **metrics,
                "read_gold": read_gold,
                "failure": failure,
                "seconds": action["seconds"],
                "tokens_computed": action["tokens_computed"],
            }
        result["modes"][mode] = actions
    positions = {
        name: {r: i + 1 for i, r in enumerate(record["actions"][name]["ranked_rows"])}
        for name in ACTIONS
    }
    result["targets"] = [
        {
            **{k: t[k] for k in ("id", "audit_status", "file_has_parser_error", "retrieval_rows")},
            "best_action_ranks": {
                a: min(
                    (positions[a][r] for r in t["retrieval_rows"] if r in positions[a]),
                    default=None,
                )
                for a in ACTIONS
            },
        }
        for t in old["targets"]
    ]
    result["prepare_seconds"] = record["prepare_seconds"]
    result["posthoc_score_substitutions"] = score_substitutions(record, parent, old["targets"])
    result["changed_query"] = (
        record["prepared"]["queries"]["prefix"]["ids"]
        != record["prepared"]["queries"]["head_tail"]["ids"]
    )
    return result


def summarize(rows: list[dict], mode: str) -> dict:
    require(bool(rows), "empty scored cohort")
    groups = {(r["repo"].casefold(), str(r["issue"])) for r in rows}
    require(len(groups) == len(rows), "duplicate underlying issues need a deduplicated sensitivity")
    actions = {}
    for name in ACTIONS:
        baseline = name.split("_", 1)[0] + "_prefix_prefix"
        values = [r["modes"][mode][name] for r in rows]
        base = [r["modes"][mode][baseline] for r in rows]
        paired = paired_clusters(
            [v["hit@10"] for v in base],
            [v["hit@10"] for v in values],
            [r["repo"].casefold() for r in rows],
        )
        for weighting in ("issue_weighted", "project_weighted"):
            paired[weighting].pop("project_sign_flip_p")
        actions[name] = {
            "hits": sum(v["hit@10"] for v in values),
            "metrics": {k: sum(v[k] for v in values) / len(values) for k in METRICS},
            "baseline": baseline,
            "rescues": [
                r["id"]
                for r, a, b in zip(rows, values, base, strict=True)
                if a["hit@10"] and not b["hit@10"]
            ],
            "harms": [
                r["id"]
                for r, a, b in zip(rows, values, base, strict=True)
                if b["hit@10"] and not a["hit@10"]
            ],
            "failure_counts": dict(Counter(v["failure"] for v in values)),
            "tokens_computed": sum(v["tokens_computed"] for v in values),
            "observed_inference_seconds": sum(v["seconds"] for v in values),
            "paired_diagnostic": paired,
        }
    return {
        "rows": len(rows),
        "projects": len({r["repo"].casefold() for r in rows}),
        "gold_count": sum(r["gold_count"] for r in rows),
        "ids": [r["id"] for r in rows],
        "actions": actions,
        "oracle_hits": sum(any(r["modes"][mode][a]["hit@10"] for a in ACTIONS) for r in rows),
        "all_actions_miss": [
            r["id"] for r in rows if not any(r["modes"][mode][a]["hit@10"] for a in ACTIONS)
        ],
    }


def analyze(archive: Path, parent: Path, preparation: Path, historical: Path, out: Path) -> dict:
    require(not out.exists(), "output exists; preserve evidence and choose a new directory")
    protocol = json.loads(PROTOCOL.read_bytes())
    expected = {
        hashlib.sha256(q.encode()).hexdigest() + ".json.gz" for q in protocol["fit_ids"]
    } | {"manifest.json", "index.json", "summary.json"}
    files = read_archive(archive, expected)
    manifest, index, summary = (
        json.loads(files[n]) for n in ("manifest.json", "index.json", "summary.json")
    )
    require(
        manifest["schema"] == "fit-text-views-v1" and manifest["prepare_only"] is False,
        "not an inference run",
    )
    require(
        manifest["protocol"] == protocol and manifest["protocol_sha256"] == digest(PROTOCOL),
        "protocol mismatch",
    )
    require(
        manifest["assets_sha256"] == digest(ROOT / "data/research/development-assets-v1.json"),
        "asset manifest mismatch",
    )
    require(
        summary["prepare_only"] is False and not summary["failures"] and not index["failures"],
        "run incomplete or failed",
    )
    require(
        summary["expected"] == summary["completed"] == len(protocol["fit_ids"])
        and set(index["completed"]) == set(protocol["fit_ids"]),
        "completion denominator mismatch",
    )
    require(summary["slurm_job_id"] == manifest["slurm_job_id"], "job identity mismatch")
    require(nonnegative(summary["script_seconds"]), "invalid total time")
    commit = manifest["git_commit"]
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "invalid recorded commit")
    for path, expected_hash in manifest["source_sha256"].items():
        content = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
        require(sha(content) == expected_hash, f"source differs from recorded commit: {path}")
    reference_path = ROOT / "results/research/corrections/text-view-preparation-v1.json"
    reference = json.loads(reference_path.read_bytes())
    for name, expected_hash in reference["files_sha256"].items():
        require(
            digest(preparation / name) == expected_hash, f"preparation reference changed: {name}"
        )
    prep_manifest = json.loads((preparation / "manifest.json").read_bytes())
    require(prep_manifest == reference["manifest"], "preparation manifest mismatch")
    require(
        prep_manifest["source_sha256"] == manifest["source_sha256"],
        "preparation/run source differs",
    )
    require(
        prep_manifest["protocol_sha256"] == manifest["protocol_sha256"],
        "preparation protocol differs",
    )
    prep_index = json.loads((preparation / "index.json").read_bytes())["completed"]
    require(set(prep_index) == set(protocol["fit_ids"]), "preparation membership mismatch")
    parent_provenance = provenance(parent)
    selected = inputs(parent, protocol)
    _, gold, history_verification = verify_bundle(historical)
    audit_path = historical / "inventory-audit-7012218/instances.jsonl"
    audited = {r["id"]: r for r in map(json.loads, audit_path.read_bytes().splitlines())}
    scored, parity = [], {}
    for item, _, trace in selected:
        qid = item["id"]
        validate_trace(trace, item, protocol["parent_manifest_sha256"])
        entry = index["completed"][qid]
        filename = hashlib.sha256(qid.encode()).hexdigest() + ".json.gz"
        require(
            entry["file"] == filename and sha(files[filename]) == entry["sha256"],
            "returned trace hash mismatch",
        )
        record = json.loads(gzip.decompress(files[filename]))
        require(
            record["parent_trace_sha256"] == protocol["trace_sha256"][qid],
            "parent trace hash mismatch",
        )
        prep = prep_index[qid]
        require(
            prep["file"] == filename and digest(preparation / filename) == prep["sha256"],
            "preparation trace hash mismatch",
        )
        prepared = json.loads(gzip.decompress((preparation / filename).read_bytes()))
        require(
            prepared["id"] == qid
            and prepared["manifest_sha256"] == reference["files_sha256"]["manifest.json"],
            "preparation trace identity mismatch",
        )
        parity[qid] = validate_capture(
            record, trace, prepared["prepared"], sha(files["manifest.json"])
        )
        scored.append(score_capture(record, trace, gold[qid], audited[qid], item))
    require(parity == summary["parent_parity"], "summary parity differs from recomputation")
    preparation_seconds = sum(r["prepare_seconds"] for r in scored)
    inference_seconds = sum(
        v["seconds"] for r in scored for v in r["modes"]["strict_symbol"].values()
    )
    result = {
        "schema": "fit-text-view-analysis-v1",
        "scope": "All frozen fit rows and all 16 controls; exploratory, no training, validation scoring or novelty claim.",
        "summaries": {mode: summarize(scored, mode) for mode in ("strict_symbol", "name_group")},
        "timing": {
            "script_seconds": summary["script_seconds"],
            "shared_preparation_seconds": preparation_seconds,
            "sequential_inference_seconds": inference_seconds,
            "other_script_seconds": summary["script_seconds"]
            - preparation_seconds
            - inference_seconds,
        },
        "integrity": {
            "ok": True,
            "cases": len(scored),
            "actions": len(ACTIONS) * len(scored),
            "exact_baseline_comparisons": 2 * len(scored),
            "prepared_views_exactly_equal": True,
            "recorded_source_files_verified": len(manifest["source_sha256"]),
            "parent_parity": parity,
        },
        "provenance": {
            "archive_sha256": digest(archive),
            "archive_bytes": archive.stat().st_size,
            "archive_files_sha256": {n: sha(b) for n, b in files.items()},
            "run_manifest": manifest,
            "run_summary": summary,
            "parent_replay": parent_provenance,
            "historical_bundle": history_verification,
            "preparation_record_sha256": digest(reference_path),
            "gold_sha256": digest(ROOT / "data/fresh-full/gold.jsonl"),
            "audit_sha256": digest(audit_path),
            "analysis_sources_sha256": {
                p: digest(ROOT / p)
                for p in (
                    "scripts/analyze_text_views.py",
                    "scripts/analyze_development_replay.py",
                    "scripts/analyze_inventory_scores.py",
                    "scripts/validate_development_replay.py",
                    "scripts/replay_text_views.py",
                    "scripts/text_views.py",
                    "scripts/development_assets.py",
                )
            },
        },
        "limitations": [
            "Fit cases informed the interventions; gains are development observations, not confirmation.",
            "No occurrence-level or causal gold repair; feature requests and all target denominators retained.",
            "Pointwise project bootstrap intervals are descriptive, not simultaneous inference over the 16 variants.",
            "Best observed variant and oracle union are optimistic post-hoc summaries, not deployable policies.",
            "Equal model token positions do not establish equal end-to-end cost; CPU preparation is shared across controls.",
            "Random-window control uses one frozen seed; no claims about its expected performance.",
            "Single-target score substitutions use gold and saved pair scores post hoc; they are diagnostic reconstructions, not executed policies or proof about a specific source line.",
            "The new run manifest records verified asset-manifest identity and checking code, not a separate copy of each model-file hash.",
        ],
    }
    out.mkdir(parents=True)
    (out / "analysis.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "rows.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in scored), encoding="utf-8", newline="\n"
    )
    lines = [
        "Exploratory fit-only results; rescues/harms against the same pool's prefix/prefix baseline.",
        "action | hit@10 | MRR@10 | recall@10 | all@10 | rescues | harms",
    ]
    for name, value in result["summaries"]["strict_symbol"]["actions"].items():
        m = value["metrics"]
        lines.append(
            f"{name} | {value['hits']}/{len(scored)} | {m['mrr@10']:.4f} | {m['recall@10']:.4f} | {m['all@10']:.4f} | {len(value['rescues'])} | {len(value['harms'])}"
        )
    (out / "table.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--historical-bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.archive, args.parent, args.preparation, args.historical_bundle, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
