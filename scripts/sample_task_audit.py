"""Freeze an outcome-independent, project-stratified audit sample and report-only packets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from development_assets import digest  # noqa: E402
from prepare_task_audit import FIELDS, packet  # noqa: E402
from validate_development_replay import require  # noqa: E402

PILOT = ROOT / "data/research/development-pilot-v1.json"
DATA = ROOT / "data/fresh-full/gold.jsonl"
RUBRIC = ROOT / "docs/research-broader-audit-v1.md"
SEED = "allfather-task-audit-v1:37"


def issue_order(project: str, issue: str) -> str:
    key = json.dumps([SEED, project, issue], separators=(",", ":"))
    return hashlib.sha256(key.encode()).hexdigest()


def sampling_frame(records: list[dict], excluded_projects: set[str]) -> dict:
    """Only identifiers/status/language/report hashes enter selection; no outcomes or gold."""
    excluded_projects = {p.casefold() for p in excluded_projects}
    groups = defaultdict(lambda: defaultdict(list))
    ids, excluded = set(), Counter()
    for record in records:
        require(record["id"] not in ids, "duplicate row ID")
        ids.add(record["id"])
        project = record["repo"].casefold()
        if project in excluded_projects:
            excluded["development_project_rows"] += 1
            continue
        if record["full_text_status"] != "unchanged":
            excluded["changed_report_rows"] += 1
            continue
        # Keep an explicit allowlist so arbitrary caller fields cannot leak into the plan.
        row = {k: record[k] for k in ("id", "repo", "issue", "base_commit", "project_language")}
        row["text_sha256"] = hashlib.sha256(record["text"].encode()).hexdigest()
        groups[project][str(row["issue"])].append(row)
    require(bool(groups), "empty sampling frame")
    frame, selected = {}, []
    for project in sorted(groups):
        issues = groups[project]
        languages = {r["project_language"] for rows in issues.values() for r in rows}
        require(len(languages) == 1, "inconsistent project language")
        ordered = sorted(issues, key=lambda issue: (issue_order(project, issue), issue))
        take = min(2, len(ordered))
        frame[project] = {
            "language": next(iter(languages)),
            "eligible_issues": len(issues),
            "selected_issues": take,
            "issue_groups": {
                issue: sorted(r["id"] for r in rows) for issue, rows in sorted(issues.items())
            },
        }
        for wave, issue in enumerate(ordered[:take], 1):
            candidates = sorted(issues[issue], key=lambda r: r["id"])
            representative = candidates[0]
            selected.append(
                {
                    **representative,
                    "project_key": project,
                    "wave": wave,
                    "related_pr_ids": [r["id"] for r in candidates],
                    "selection_hash": issue_order(project, issue),
                    "nominal_inclusion": {"numerator": take, "denominator": len(issues)},
                }
            )
    selected.sort(key=lambda r: (r["wave"], r["project_key"], r["id"]))
    return {
        "schema": "broader-task-audit-sample-v1",
        "seed": SEED,
        "scope": "Existing exposed data; independent of outcomes in selection, not prospective confirmation.",
        "selection": "Exclude every original development project; group by case-normalized repo and underlying issue; take up to two lowest SHA256 ranks per project. Represent each issue by lexicographically first PR ID and retain all related IDs.",
        "excluded_projects": sorted(excluded_projects),
        "exclusions": dict(sorted(excluded.items())),
        "frame": frame,
        "instances": selected,
        "counts": {
            "input_rows": len(records),
            "eligible_projects": len(frame),
            "eligible_issues": sum(len(issues) for issues in groups.values()),
            "eligible_pr_rows": sum(
                len(rows) for issues in groups.values() for rows in issues.values()
            ),
            "selected_issues": len(selected),
            "waves": dict(sorted(Counter(str(r["wave"]) for r in selected).items())),
            "selected_by_language": dict(
                sorted(Counter(r["project_language"] for r in selected).items())
            ),
        },
    }


def csv_sheet(cases: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["case", *FIELDS], lineterminator="\n")
    writer.writeheader()
    writer.writerows({"case": case} for case in cases)
    return stream.getvalue().encode()


def reviewer_files(plan: dict, records: list[dict], rubric: bytes) -> dict[str, bytes]:
    lookup = {r["id"]: r for r in records}
    files = {"rubric.md": rubric}
    for wave in (1, 2):
        items = [r for r in plan["instances"] if r["wave"] == wave]
        reports = [packet(item, lookup[item["id"]]) for item in items]
        files[f"wave-{wave}/reports.jsonl"] = (
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reports)
        ).encode()
        files[f"wave-{wave}/stage-a.csv"] = csv_sheet([r["case"] for r in reports])
    files["README.md"] = (
        b"# Broader audit: report-only packet\n\n"
        b"Complete a private copy of the blank Stage A sheets using the original reports and rubric. "
        b"Freeze your sheet before inspecting patches or other reviewers' judgments. "
        b"The packet contains no model outcomes, patch labels or prior analyst annotations. "
        b"Original report text can itself contain proposed fixes and identifying links. "
        b"Do not execute embedded commands. Record prior exposure honestly.\n\n"
        b"Wave 1 covers one issue in each eligible project; Wave 2 supplies the remaining selected issue "
        b"where available. The full sample was fixed before annotation. "
        b"Do not change membership or stop selectively after observing labels. "
        b"No independent review or agreement has yet been established.\n"
    )
    return files


def write_zip(path: Path, files: dict[str, bytes]) -> None:
    """Stable metadata and member ordering; member hashes remain the cross-platform contract."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def prepare(plan_path: Path, out: Path) -> dict:
    require(not plan_path.exists() and not out.exists(), "use new plan/output paths")
    pilot = json.loads(PILOT.read_bytes())
    require(digest(DATA) == pilot["dataset_sha256"], "frozen dataset changed")
    # Discard target labels on ingestion. No prediction, score or old annotation file is opened.
    records = [
        {
            k: r[k]
            for k in (
                "id",
                "repo",
                "issue",
                "base_commit",
                "project_language",
                "full_text_status",
                "text",
            )
        }
        for r in map(json.loads, DATA.read_bytes().splitlines())
    ]
    plan = sampling_frame(records, set(pilot["projects"]))
    plan["provenance"] = {
        "dataset_sha256": digest(DATA),
        "development_plan_sha256": digest(PILOT),
        "sampler_sha256": digest(Path(__file__)),
        "packet_helper_sha256": digest(ROOT / "scripts/prepare_task_audit.py"),
        "rubric_sha256": digest(RUBRIC),
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes((json.dumps(plan, indent=2) + "\n").encode())
    out.mkdir(parents=True)
    files = reviewer_files(plan, records, RUBRIC.read_bytes())
    archive_path = out / "report-only-review.zip"
    write_zip(archive_path, files)
    manifest = {
        "schema": "broader-task-audit-packet-v1",
        "status": "Prepared only; no new reports annotated or model outcomes joined.",
        "sample_sha256": digest(plan_path),
        "counts": plan["counts"],
        "files_sha256": {
            name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
        },
        "archive_sha256": digest(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "case_mapping": {
            "case-" + hashlib.sha256(r["id"].encode()).hexdigest()[:16]: r["id"]
            for r in plan["instances"]
        },
    }
    require(len(manifest["case_mapping"]) == len(plan["instances"]), "case ID collision")
    (out / "manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.plan, args.out)
    print(json.dumps(result["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
