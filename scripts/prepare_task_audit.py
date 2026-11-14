"""Prepare report-only fit review packets; never export patches, gold or model outcomes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from development_assets import digest  # noqa: E402
from validate_development_replay import require  # noqa: E402

PLAN = ROOT / "data/research/development-pilot-v1.json"
DATA = ROOT / "data/fresh-full/gold.jsonl"
RUBRIC = ROOT / "docs/research-task-audit-v1.md"
FIELDS = (
    "task_kind",
    "scope",
    "requested_behavior",
    "observed_behavior",
    "expected_behavior",
    "reproduction_evidence",
    "report_anchors",
    "underspecification",
    "evidence_quotes",
    "confidence",
    "reviewer",
    "prior_exposure",
    "notes",
)


def packet(item: dict, record: dict) -> dict:
    """Allowlist query fields; other keys must not leak into review material."""
    for key in ("id", "repo", "base_commit"):
        require(item[key] == record[key], f"report join mismatch: {key}")
    require(
        hashlib.sha256(record["text"].encode()).hexdigest() == item["text_sha256"], "report changed"
    )
    return {
        "case": "case-" + hashlib.sha256(item["id"].encode()).hexdigest()[:16],
        "repo": record["repo"],
        "base_commit": record["base_commit"],
        "text_sha256": item["text_sha256"],
        "text": record["text"],
    }


def prepare(out: Path) -> dict:
    require(not out.exists(), "use a new audit directory")
    plan = json.loads(PLAN.read_bytes())
    require(digest(DATA) == plan["dataset_sha256"], "dataset changed")
    selected = [r for r in plan["instances"] if r["split"] == "fit"]
    wanted = {r["id"] for r in selected}
    # Discard labels at ingestion. No outcome files are opened.
    records = {
        r["id"]: {k: r[k] for k in ("id", "repo", "base_commit", "text")}
        for r in map(json.loads, DATA.read_bytes().splitlines())
        if r["id"] in wanted
    }
    packets = [packet(item, records[item["id"]]) for item in selected]
    require(len({r["case"] for r in packets}) == len(selected), "case identity collision")
    out.mkdir(parents=True)
    report_path = out / "reports.jsonl"
    report_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in packets), encoding="utf-8"
    )
    sheet = out / "stage-a.csv"
    with sheet.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case", *FIELDS])
        writer.writeheader()
        writer.writerows({"case": r["case"]} for r in packets)
    manifest = {
        "schema": "task-audit-preparation-v1",
        "cases": len(packets),
        "status": "Prepared only; no annotations or independent-review claim.",
        "plan_sha256": digest(PLAN),
        "dataset_sha256": digest(DATA),
        "rubric_sha256": digest(RUBRIC),
        "script_sha256": digest(Path(__file__)),
        "reports_sha256": digest(report_path),
        "blank_sheet_sha256": digest(sheet),
        "case_mapping": {p["case"]: item["id"] for p, item in zip(packets, selected, strict=True)},
        "review_boundary": "Give reviewers reports.jsonl and stage-a.csv, not this mapping or outcome/patch files. Original report text can itself mention PRs or fixes. Prior analyst exposure prevents claiming analyst blinding.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.out)
    print(json.dumps({k: manifest[k] for k in ("cases", "status", "reports_sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
