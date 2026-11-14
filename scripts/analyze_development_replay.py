"""Exploratory gold join for verified stage traces; no fitting or inference."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from analyze_inventory_scores import paired_clusters, verify_bundle  # noqa: E402
from validate_development_replay import digest, require, validate_bundle  # noqa: E402

ACTIONS = ("base_local", "wide_local", "base_ce50", "base_ce200", "wide_ce50", "wide_ce200")
MODES = ("strict_symbol", "name_group")


def score_rows(ranked: list[int], universe: list[dict], gold: set[str], eligible: set[str]) -> dict:
    """Keep duplicate/unresolved slots in the top-ten budget; never compact rankings."""
    require(bool(gold), "empty gold set")
    seen, hits = set(), []
    for slot, row in enumerate(ranked[:10], 1):
        uid = universe[row]["id"]
        if uid in eligible and uid in gold and uid not in seen:
            hits.append((slot, uid))
        seen.add(uid)
    return {
        **{f"hit@{k}": int(any(slot <= k for slot, _ in hits)) for k in (1, 5, 10)},
        "recall@10": len(hits) / len(gold),
        "all@10": int(len(hits) == len(gold)),
        "mrr@10": 1 / hits[0][0] if hits else 0.0,
        "found_gold": [uid for _, uid in hits],
    }


def diagnose(trace: dict, gold: dict, audited: dict, item: dict) -> dict:
    qid = gold["id"]
    for key in ("id", "repo", "base_commit"):
        require(
            trace[key] == gold[key] == audited[key] == item[key], f"gold join mismatch: {key}/{qid}"
        )
    require(
        hashlib.sha256(gold["text"].encode()).hexdigest() == trace["text_sha256"],
        "query hash mismatch",
    )
    targets = set(gold["gold_functions"])
    states = {g["id"]: g for g in audited["gold"]}
    require(set(states) == targets and len(states) == len(audited["gold"]), "audit target mismatch")
    universe = trace["universe"]
    counts = Counter(u["id"] for u in universe)
    # Gold identity eligibility is from the complete symbol audit, not from treating
    # the filtered retrieval universe as a complete declaration inventory.
    unique = {u for u in targets if states[u]["status"] == "unique" and counts[u] <= 1}
    result = {
        "id": qid,
        "repo": gold["repo"],
        "issue": gold["issue"],
        "split": item["split"],
        "language": item["language"],
        "gold_count": len(targets),
        "all_gold_unique": unique == targets,
        "gold_in_parser_error_files": audited["gold_in_parser_error_files"],
        "universe": len(universe),
        "base_pool": len(trace["pools"]["base"]["rows"]),
        "wide_pool": len(trace["pools"]["wide"]["rows"]),
        "modes": {},
        "timing": {
            k: trace[k]
            for k in ("snapshot_prepare_seconds", "shared_signals_seconds", "total_seconds")
        },
    }
    positions = {
        action: {row: i + 1 for i, row in enumerate(trace["actions"][action]["ranked_rows"])}
        for action in ACTIONS
    }
    target_rows = defaultdict(list)
    for unit in universe:
        if unit["id"] in targets:
            target_rows[unit["id"]].append(unit["row"])
    result["targets"] = [
        {
            "id": uid,
            "audit_status": states[uid]["status"],
            "file_has_parser_error": states[uid]["file_has_parser_error"],
            "retrieval_rows": target_rows[uid],
            "best_action_ranks": {
                action: min(
                    (
                        positions[action][row]
                        for row in target_rows[uid]
                        if row in positions[action]
                    ),
                    default=None,
                )
                for action in ACTIONS
            },
        }
        for uid in sorted(targets)
    ]
    for mode in MODES:
        eligible = unique if mode == "strict_symbol" else targets
        sets = {"universe": set(counts) & eligible}
        for label, pool in trace["pools"].items():
            sets[f"{label}_pool"] = {universe[row]["id"] for row in pool["rows"]} & eligible
            sets[f"{label}_minilm"] = {
                universe[row]["id"] for row in pool["minilm_rows"]
            } & eligible
        modes = {
            "coverage": {
                label: {
                    "found": sorted(found),
                    "count": len(found),
                    "any": int(bool(found)),
                    "all": int(found == targets),
                    "recall": len(found) / len(targets),
                }
                for label, found in sets.items()
            },
            "actions": {},
        }
        for action in ACTIONS:
            value = trace["actions"][action]
            metrics = score_rows(value["ranked_rows"], universe, targets, eligible)
            label = action.split("_", 1)[0]
            read = {universe[row]["id"] for row in value.get("read_rows", [])} & eligible
            if metrics["hit@10"]:
                failure = "success"
            elif not eligible:
                failure = "identity_unresolved"
            elif not sets["universe"]:
                failure = "universe_miss"
            elif not sets[f"{label}_pool"]:
                failure = "candidate_miss"
            elif "read_rows" in value and not read:
                failure = "read_prefix_miss"
            else:
                failure = "ranking_miss"
            modes["actions"][action] = {
                **metrics,
                "failure": failure,
                "read_gold": sorted(read) if "read_rows" in value else None,
                "seconds": value["seconds"],
                "tokens_computed": value.get("tokens_computed"),
            }
        result["modes"][mode] = modes
    return result


def summaries(rows: list[dict]) -> dict:
    result = {}
    for split in ("all", "fit", "validation"):
        selected = [r for r in rows if split == "all" or r["split"] == split]
        for view in ("issue_pr", "issue_deduplicated"):
            chosen, seen = [], set()
            for row in sorted(selected, key=lambda r: r["id"]):
                group = (row["repo"].casefold(), str(row["issue"]))
                if view == "issue_pr" or group not in seen:
                    chosen.append(row)
                seen.add(group)
            if not chosen:
                continue
            for mode in MODES:
                values = [r["modes"][mode] for r in chosen]
                actions = {}
                for action in ACTIONS:
                    scored = [v["actions"][action] for v in values]
                    rescued = [
                        r["id"]
                        for r in chosen
                        if r["modes"][mode]["actions"][action]["hit@10"]
                        and not r["modes"][mode]["actions"]["base_local"]["hit@10"]
                    ]
                    harmed = [
                        r["id"]
                        for r in chosen
                        if not r["modes"][mode]["actions"][action]["hit@10"]
                        and r["modes"][mode]["actions"]["base_local"]["hit@10"]
                    ]
                    actions[action] = {
                        "hits": sum(s["hit@10"] for s in scored),
                        "metrics": {
                            k: sum(s[k] for s in scored) / len(scored)
                            for k in ("hit@1", "hit@5", "hit@10", "recall@10", "all@10", "mrr@10")
                        },
                        "rescues_vs_base": rescued,
                        "harms_vs_base": harmed,
                        "failure_counts": dict(Counter(s["failure"] for s in scored)),
                        "observed_action_seconds": sum(s["seconds"] for s in scored),
                        "tokens_computed": sum(s["tokens_computed"] for s in scored)
                        if "_ce" in action
                        else None,
                    }
                    if action != "base_local":
                        paired = paired_clusters(
                            [v["actions"]["base_local"]["hit@10"] for v in values],
                            [s["hit@10"] for s in scored],
                            [r["repo"].casefold() for r in chosen],
                        )
                        # Descriptive pointwise intervals only; no post-hoc testing family.
                        for weighting in ("issue_weighted", "project_weighted"):
                            paired[weighting].pop("project_sign_flip_p")
                        actions[action]["paired_diagnostic"] = paired
                result[f"{split}/{view}/{mode}"] = {
                    "rows": len(chosen),
                    "projects": len({r["repo"].casefold() for r in chosen}),
                    "ids": [r["id"] for r in chosen],
                    "gold_count": sum(r["gold_count"] for r in chosen),
                    "coverage": {
                        label: {
                            "any_rows": sum(v["coverage"][label]["any"] for v in values),
                            "all_rows": sum(v["coverage"][label]["all"] for v in values),
                            "target_count": sum(v["coverage"][label]["count"] for v in values),
                        }
                        for label in values[0]["coverage"]
                    },
                    "actions": actions,
                    "oracle_hits": sum(
                        any(v["actions"][a]["hit@10"] for a in ACTIONS) for v in values
                    ),
                    "all_actions_miss": [
                        r["id"]
                        for r in chosen
                        if not any(r["modes"][mode]["actions"][a]["hit@10"] for a in ACTIONS)
                    ],
                }
    return result


def provenance(bundle: Path) -> dict:
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    summary = json.loads((bundle / "summary.json").read_bytes())
    commit = summary["git_commit"]
    for path, expected in manifest["source_sha256"].items():
        actual = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
        require(
            hashlib.sha256(actual).hexdigest() == expected,
            f"recorded source differs from run commit: {path}",
        )
    assets = ROOT / "data/research/development-assets-v1.json"
    require(digest(assets) == manifest["assets_sha256"], "asset manifest mismatch")
    spec = json.loads(assets.read_bytes())
    for name, model in spec["models"].items():
        require(
            manifest["model_identity"][name] == model, f"pinned model identity mismatch: {name}"
        )
    require(
        manifest["adapter_sha256"]["adapter_model.safetensors"]
        == spec["adapter"]["weights_sha256"],
        "adapter mismatch",
    )
    require(
        manifest["ranker_sha256"] == digest(ROOT / "web/src/assets/ranker.json"), "ranker mismatch"
    )
    expected_recipe = {
        "pool_scale": 4,
        "ce_depths": [50, 200],
        "ce_weight": 1.0,
        "query_tokens": 512,
        "doc_tokens": 256,
        "minilm_tokens": 256,
    }
    require(manifest["recipe"] == expected_recipe, "recipe mismatch")
    return {
        "commit": commit,
        "verified_source_files": len(manifest["source_sha256"]),
        "files_sha256": {
            name: digest(bundle / name) for name in ("manifest.json", "index.json", "summary.json")
        },
    }


def verify_transfer(bundle: Path, archive: Path) -> dict:
    files = {}
    root = bundle.resolve()
    with tarfile.open(archive, "r:gz") as handle:
        names = set()
        for member in handle.getmembers():
            path = (root / member.name).resolve()
            require(path.is_relative_to(root), "unsafe archive path")
            require(member.name not in names, "duplicate archive entry")
            names.add(member.name)
            require(member.isfile() or member.isdir(), "unsupported archive entry")
            if member.isfile():
                with handle.extractfile(member) as stream:
                    expected = hashlib.sha256(stream.read()).hexdigest()
                require(digest(path) == expected, f"extracted file differs: {member.name}")
                files[member.name] = expected
    return {
        "archive_sha256": digest(archive),
        "archive_bytes": archive.stat().st_size,
        "original_bundle_files_sha256": files,
    }


def analyze(bundle: Path, historical: Path, out: Path, archive: Path) -> dict:
    transfer = verify_transfer(bundle, archive)
    integrity = {
        name: validate_bundle(bundle / name)
        for name in ("development-smoke-v1", "development-pilot-v1")
    }
    require(all(r["ok"] for r in integrity.values()), "replay integrity failed")
    require(
        json.loads((bundle / "development-pilot-7019874-integrity.json").read_bytes())
        == integrity["development-pilot-v1"],
        "PACE/local validation disagreement",
    )
    verified = {name: provenance(bundle / name) for name in integrity}
    _, gold, old_verification = verify_bundle(historical)
    audit_path = historical / "inventory-audit-7012218/instances.jsonl"
    audited = {r["id"]: r for r in map(json.loads, audit_path.read_bytes().splitlines())}
    full = bundle / "development-pilot-v1"
    manifest = json.loads((full / "manifest.json").read_bytes())
    index = json.loads((full / "index.json").read_bytes())["completed"]
    pilot_report = json.loads(
        (ROOT / "results/research/corrections/pace-development-pilot-7019874.json").read_bytes()
    )
    require(
        pilot_report["summary"] == integrity["development-pilot-v1"]["summary"],
        "reported pilot summary differs",
    )
    for entry in pilot_report["records"]:
        require(index[entry["id"]]["sha256"] == entry["sha256"], "printed pilot checksum differs")
    smoke = bundle / "development-smoke-v1"
    smoke_index = json.loads((smoke / "index.json").read_bytes())["completed"]
    smoke_report = json.loads(
        (ROOT / "results/research/corrections/pace-development-smoke-7018060.json").read_bytes()
    )
    require(
        all(smoke_index[r["id"]]["sha256"] == r["sha256"] for r in smoke_report["records"]),
        "printed smoke checksum differs",
    )
    rows, repeat = [], []
    for item in manifest["instances"]:
        qid = item["id"]
        trace = json.loads(gzip.decompress((full / index[qid]["file"]).read_bytes()))
        rows.append(diagnose(trace, gold[qid], audited[qid], item))
        if qid in smoke_index:
            old = json.loads(gzip.decompress((smoke / smoke_index[qid]["file"]).read_bytes()))
            repeat.append(
                {
                    "id": qid,
                    "same_universe": old["universe"] == trace["universe"],
                    "same_files": old["files"] == trace["files"],
                    "same_pools_features_scores": old["pools"] == trace["pools"],
                    "same_action_rankings": {
                        a: old["actions"][a]["ranked_rows"] == trace["actions"][a]["ranked_rows"]
                        for a in ACTIONS
                    },
                    "max_ce_score_difference": {
                        a: float(
                            np.max(
                                np.abs(
                                    np.asarray(old["actions"][a]["raw_scores"])
                                    - trace["actions"][a]["raw_scores"]
                                ),
                                initial=0,
                            )
                        )
                        for a in ACTIONS
                        if "_ce" in a
                    },
                }
            )
    result = {
        "schema": "development-action-analysis-v1",
        "scope": "Exploratory exposed-data pilot; no controller fitted and no confirmation claim.",
        "policies": {
            "strict_symbol": "Exact recorded row IDs; audited ambiguous targets and multiply indexed target names receive no credit, with all targets retained in denominators.",
            "name_group": "Exact path/name groups; does not establish occurrence-level correctness.",
            "slots": "Duplicate/nonmatching rows consume their original rank slots; MRR is truncated at ten.",
            "issue_deduplication": "Lexicographically first ID per case-normalized repository and underlying issue; outcome independent.",
        },
        "limitations": [
            "No occurrence-level or causal gold repair.",
            "Complete declaration inventories were not transferred; gold identities use the previously verified audit.",
            "Parser errors may hide declarations, including in apparently unique cases.",
            "Pointwise project-bootstrap intervals on small exploratory cohorts are not confirmatory tests or simultaneous intervals.",
            "Sequential cache reuse and unallocated overhead preclude standalone cost-superiority claims.",
            "Pilot selection is metadata-only but the dataset was already exposed; project validation is development, not independent confirmation.",
        ],
        "summaries": summaries(rows),
        "repeat_smoke": repeat,
        "provenance": {
            "transfer": transfer,
            "replays": verified,
            "historical_bundle": old_verification,
            "gold_sha256": digest(ROOT / "data/fresh-full/gold.jsonl"),
            "audit_sha256": digest(audit_path),
            "analysis_sha256": digest(Path(__file__)),
        },
    }
    out.mkdir(parents=True, exist_ok=False)
    (out / "analysis.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "rows.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n"
    )
    for name, report in integrity.items():
        (out / f"{name}-integrity.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    print("split | action | hit@10 | rescues / harms vs base")
    for split in ("all", "fit", "validation"):
        summary = result["summaries"][f"{split}/issue_pr/strict_symbol"]
        for action, value in summary["actions"].items():
            print(
                f"{split} | {action} | {value['hits']}/{summary['rows']} | {len(value['rescues_vs_base'])} / {len(value['harms_vs_base'])}"
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--historical-bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.bundle, args.historical_bundle, args.out, args.archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
