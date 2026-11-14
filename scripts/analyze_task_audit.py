"""Verify frozen provisional task annotations and join original fit outcomes without relabeling."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from analyze_development_replay import ACTIONS, diagnose  # noqa: E402
from analyze_inventory_scores import verify_bundle  # noqa: E402
from replay_text_views import PROTOCOL, digest, inputs, write_json  # noqa: E402
from validate_development_replay import require  # noqa: E402

from allfather.index.snapshot import unit_key, unit_text  # noqa: E402

ROLES = {"behavioral", "supporting_integration", "incidental", "unresolved"}
ALIGNMENTS = {"direct", "partial_subtask", "broader_than_report", "unclear", "unavailable"}


def verify_annotation(annotation: dict, capture: dict, parent: dict) -> None:
    require(annotation["id"] == capture["id"] == parent["id"], "annotation identity mismatch")
    require(annotation["alignment"] in ALIGNMENTS, "invalid alignment")
    targets = annotation["targets"]
    require(len({t["id"] for t in targets}) == len(targets), "duplicate annotated target")
    require(
        {t["id"] for t in targets} == set(capture["gold_functions"]), "incomplete target annotation"
    )
    changes = {c["path"]: c for c in capture["changes"]}
    for t in targets:
        require(t["role"] in ROLES and bool(t["reason"]), "invalid target role")
        path, name = t["id"].split("::", 1)
        c = changes[path]
        require(c["patch_sha256"] == t["patch_sha256"], "annotation evidence changed")
        contexts = [x for x in c["gold_base_context"] if x["id"] == t["id"]]
        units = [u for u in parent["universe"] if u["id"] == t["id"]]
        require(len(contexts) == len(units) == 1, "ambiguous base target context")
        require(
            unit_key(unit_text(name, contexts[0]["text"])).hex() == units[0]["text_key"],
            "base target differs from frozen retrieval unit",
        )


def summarize(rows: list[dict]) -> dict:
    groups = {"all": rows}
    for field in ("task_kind", "alignment"):
        for value in sorted({r[field] for r in rows}):
            groups[f"{field}/{value}"] = [r for r in rows if r[field] == value]
    return {
        group: {
            "issues": len(selected),
            "projects": len({r["repo"] for r in selected}),
            "ids": [r["id"] for r in selected],
            "original_hit_at_10": {
                a: sum(r["actions"][a]["hit@10"] for r in selected) for a in ACTIONS
            },
            "incidental_only_hits": {
                a: [r["id"] for r in selected if r["actions"][a]["incidental_only_hit"]]
                for a in ACTIONS
            },
        }
        for group, selected in groups.items()
    }


def analyze(captures: Path, parent_dir: Path, annotations: Path, out: Path) -> dict:
    require(not out.exists(), "use a new analysis directory")
    frozen = json.loads((annotations / "freeze.json").read_bytes())
    require(
        digest(annotations / "annotations.jsonl") == frozen["annotations_sha256"],
        "annotations changed",
    )
    for name, key in (
        ("manifest.json", "capture_manifest_sha256"),
        ("index.json", "capture_index_sha256"),
        ("upstream-pet.json", "upstream_pet_sha256"),
    ):
        require(digest(captures / name) == frozen[key], f"capture {name} changed")
    manifest = json.loads((captures / "manifest.json").read_bytes())
    require(
        digest(ROOT / "scripts/prepare_patch_audit.py") == manifest["script_sha256"],
        "collector changed",
    )
    for name, sha in manifest["source_sha256"].items():
        require(digest(ROOT / name) == sha, f"parser source changed: {name}")
    stage_a = ROOT / "results/research/corrections/task-audit-stage-a-v1/rows.jsonl"
    require(
        digest(stage_a) == manifest["stage_a_rows_sha256"] == frozen["stage_a_rows_sha256"],
        "Stage A changed",
    )
    a_rows = {r["case"]: r for r in map(json.loads, stage_a.read_bytes().splitlines())}
    annotated_rows = list(
        map(json.loads, (annotations / "annotations.jsonl").read_bytes().splitlines())
    )
    annotated = {r["id"]: r for r in annotated_rows}
    require(len(annotated) == len(annotated_rows), "duplicate issue annotation")
    selected = inputs(parent_dir, json.loads(PROTOCOL.read_bytes()))
    require([r[0]["id"] for r in selected] == manifest["fit_ids"], "fit membership changed")
    require(set(annotated) == set(manifest["fit_ids"]), "annotation cohort changed")
    index = json.loads((captures / "index.json").read_bytes())
    require(
        not index["failures"] and set(index["completed"]) == set(annotated), "incomplete capture"
    )
    summary = json.loads((captures / "summary.json").read_bytes())
    require(
        summary
        == {
            "expected": len(selected),
            "completed": len(selected),
            "failures": [],
            "downloaded_blobs": len(manifest["downloads"]),
            "unavailable_patches": 0,
        },
        "capture summary mismatch",
    )
    historical = ROOT / "reports/pace-7012506"
    _, gold, audit_verification = verify_bundle(historical)
    audited = {
        r["id"]: r
        for r in map(
            json.loads,
            (historical / "inventory-audit-7012218/instances.jsonl").read_bytes().splitlines(),
        )
    }
    rows, patch_count = [], 0
    for item, query, parent in selected:
        qid = item["id"]
        entry = index["completed"][qid]
        filename = hashlib.sha256(qid.encode()).hexdigest() + ".json"
        require(
            entry["file"] == filename and digest(captures / filename) == entry["sha256"],
            "capture checksum mismatch",
        )
        require(
            annotated[qid]["patch_capture_sha256"] == entry["sha256"], "annotation capture changed"
        )
        capture = json.loads((captures / filename).read_bytes())
        require(
            all(
                capture[k] == gold[qid][k]
                for k in (
                    "id",
                    "repo",
                    "issue",
                    "pr",
                    "base_commit",
                    "merge_commit",
                    "gold_functions",
                )
            ),
            "patch/gold join mismatch",
        )
        for c in capture["changes"]:
            require("unavailable" not in c, "patch unavailable")
            require(
                hashlib.sha256(c["patch"].encode()).hexdigest() == c["patch_sha256"],
                "patch bytes changed",
            )
        require(
            len(capture["changes"]) == entry["changed_files"] and entry["unavailable_patches"] == 0,
            "file count mismatch",
        )
        patch_count += len(capture["changes"])
        verify_annotation(annotated[qid], capture, parent)
        a = a_rows["case-" + hashlib.sha256(qid.encode()).hexdigest()[:16]]
        require(
            a["text_sha256"] == hashlib.sha256(query.encode()).hexdigest(), "Stage A report changed"
        )
        diagnostic = diagnose(parent, gold[qid], audited[qid], item)
        require(diagnostic["all_gold_unique"], "requires explicit ambiguous-target policy")
        roles = {t["id"]: t["role"] for t in annotated[qid]["targets"]}
        actions = {}
        for name, metrics in diagnostic["modes"]["strict_symbol"]["actions"].items():
            found = metrics["found_gold"]
            actions[name] = {
                "hit@10": metrics["hit@10"],
                "found_gold": found,
                "found_by_role": {
                    role: [uid for uid in found if roles[uid] == role] for role in sorted(ROLES)
                },
                "incidental_only_hit": bool(found)
                and all(roles[uid] == "incidental" for uid in found),
            }
        rows.append(
            {
                "id": qid,
                "repo": item["repo"],
                "task_kind": a["task_kind"],
                "alignment": annotated[qid]["alignment"],
                "target_roles": roles,
                "actions": actions,
            }
        )
    result = {
        "schema": "task-audit-analysis-v1",
        "scope": "Exploratory provisional analyst strata; original gold and scores retained. No corrected leaderboard or causal validation.",
        "issues": len(rows),
        "targets": sum(len(r["target_roles"]) for r in rows),
        "verified_file_diffs": patch_count,
        "alignment_counts": dict(Counter(r["alignment"] for r in rows)),
        "role_counts": dict(Counter(role for r in rows for role in r["target_roles"].values())),
        "strata": summarize(rows),
        "provenance": {
            "annotations_sha256": frozen["annotations_sha256"],
            "freeze_sha256": digest(annotations / "freeze.json"),
            "capture_manifest_sha256": digest(captures / "manifest.json"),
            "analysis_source_sha256": digest(Path(__file__)),
            "historical_audit": audit_verification,
        },
        "limitations": [
            "Strata were assigned by an exposed single analyst and are not independently validated.",
            "Small fit-only strata cannot establish dataset-wide prevalence or method superiority.",
            "No target was removed and incidental-only-hit checks do not assess alternative valid locations.",
            "The reviewed dependency change is source evidence, not a macOS runtime reproduction.",
        ],
    }
    out.mkdir(parents=True)
    write_json(out / "analysis.json", result)
    (out / "rows.jsonl").write_bytes(("".join(json.dumps(r) + "\n" for r in rows)).encode())
    lines = [
        "Provisional task audit; original strict hit@10 counts, no relabeling.",
        "stratum | n | " + " | ".join(ACTIONS),
    ]
    for name, group in result["strata"].items():
        lines.append(
            f"{name} | {group['issues']} | "
            + " | ".join(str(group["original_hit_at_10"][a]) for a in ACTIONS)
        )
    (out / "table.txt").write_bytes(("\n".join(lines) + "\n").encode())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument(
        "--annotations",
        type=Path,
        default=ROOT / "results/research/corrections/task-audit-stage-b-v1",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.captures, args.parent, args.annotations, args.out)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "issues",
                    "targets",
                    "verified_file_diffs",
                    "alignment_counts",
                    "role_counts",
                )
            },
            indent=2,
        )
    )
    print((args.out / "table.txt").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
