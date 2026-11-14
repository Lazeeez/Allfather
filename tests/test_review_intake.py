import argparse
import csv
import io
import json
import zipfile

import pytest

from scripts.prepare_task_audit import FIELDS
from scripts.review_task_audit import (
    agreement,
    compare,
    digest,
    freeze,
    load_freeze,
    validate_sheet,
)


def sheet(rows, fields=("case", *FIELDS)):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def annotations(reviewer="synthetic-reviewer-one"):
    return [
        {
            "case": case,
            **dict.fromkeys(FIELDS, "synthetic evidence"),
            "task_kind": "bug",
            "scope": "focused",
            "reproduction_evidence": "assertion_only",
            "underspecification": "none_identified",
            "confidence": "high",
            "reviewer": reviewer,
            "report_anchors": "",
            "notes": "",
        }
        for case in ("case-one", "case-two")
    ]


def packet(tmp_path):
    files = {
        "rubric.md": b"synthetic rubric",
        "stage-a/stage-a.csv": sheet([{"case": c} for c in ("case-one", "case-two")]),
        "stage-b/target-roles.csv": sheet(
            [{"case": "case-one", "target": "a.py::f"}],
            ("case", "target", "role", "reason", "patch_evidence", "reviewer"),
        ),
    }
    archive, manifest = tmp_path / "packet.zip", tmp_path / "manifest.json"
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    manifest.write_text(
        json.dumps(
            {
                "archive_sha256": digest(archive.read_bytes()),
                "files_sha256": {k: digest(v) for k, v in files.items()},
            }
        )
    )
    return archive, manifest, files


def freeze_args(tmp_path, archive, manifest, rows, name):
    path = tmp_path / (name + ".csv")
    path.write_bytes(sheet(rows))
    return argparse.Namespace(
        packet=archive,
        manifest=manifest,
        sheet=path,
        out=tmp_path / name,
        member="stage-a/stage-a.csv",
        reviewer_kind="human",
        independent_initial=True,
        stage_a=None,
    )


@pytest.mark.parametrize("defect", ["missing", "duplicate", "blank", "enum"])
def test_incomplete_or_invented_sheet_entries_are_rejected(defect):
    rows = annotations()
    template = sheet([{"case": r["case"]} for r in rows])
    if defect == "missing":
        rows.pop()
    if defect == "duplicate":
        rows.append(rows[0])
    if defect == "blank":
        rows[0]["evidence_quotes"] = ""
    if defect == "enum":
        rows[0]["scope"] = "invented"
    with pytest.raises(ValueError):
        validate_sheet(template, sheet(rows))


def test_freeze_preserves_submitted_bytes_and_detects_tampering(tmp_path):
    archive, manifest, _ = packet(tmp_path)
    args = freeze_args(tmp_path, archive, manifest, annotations(), "review")
    result = freeze(args)
    assert result["rows"] == 2
    assert (args.out / "submitted.csv").read_bytes() == args.sheet.read_bytes()
    assert load_freeze(args.out)[1] == annotations()
    with pytest.raises(ValueError, match="new output"):
        freeze(args)
    (args.out / "submitted.csv").write_bytes(b"modified")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_freeze(args.out)


def test_compare_keeps_disagreement_and_degenerate_kappa_explicit(tmp_path):
    archive, manifest, _ = packet(tmp_path)
    left = freeze_args(tmp_path, archive, manifest, annotations(), "left")
    rows = annotations("synthetic-reviewer-two")
    rows[0]["task_kind"] = "unclear"
    right = freeze_args(tmp_path, archive, manifest, rows, "right")
    freeze(left)
    freeze(right)
    result = compare(left.out, right.out)
    assert result["fields"]["task_kind"]["raw_agreement"] == 0.5
    assert result["fields"]["scope"]["kappa"] is None
    assert result["disagreements"][0]["fields"] == {"task_kind": ["bug", "unclear"]}
    assert agreement(["a", "b"], ["a", "b"])["kappa"] == 1
    with pytest.raises(ValueError, match="same reviewer"):
        compare(left.out, left.out)


def test_automated_reviews_cannot_be_presented_as_independent_human_agreement(tmp_path):
    archive, manifest, _ = packet(tmp_path)
    left = freeze_args(tmp_path, archive, manifest, annotations(), "left")
    right = freeze_args(tmp_path, archive, manifest, annotations("synthetic-other"), "right")
    right.reviewer_kind = "automated"
    freeze(left)
    freeze(right)
    with pytest.raises(ValueError, match="human reviews"):
        compare(left.out, right.out)


def test_stage_b_requires_same_reviewers_prior_stage_a_freeze(tmp_path):
    archive, manifest, files = packet(tmp_path)
    a = freeze_args(tmp_path, archive, manifest, annotations(), "a")
    b = freeze_args(tmp_path, archive, manifest, annotations(), "b")
    b.member = "stage-b/target-roles.csv"
    fields = tuple(files[b.member].decode().splitlines()[0].split(","))
    b.sheet.write_bytes(
        sheet(
            [
                {
                    "case": "case-one",
                    "target": "a.py::f",
                    "role": "unresolved",
                    "reason": "synthetic",
                    "patch_evidence": "unavailable",
                    "reviewer": "synthetic-reviewer-one",
                }
            ],
            fields,
        )
    )
    with pytest.raises(ValueError, match="earlier Stage A"):
        freeze(b)
    freeze(a)
    b.stage_a = a.out
    result = freeze(b)
    assert result["stage_a_freeze_sha256"] == digest((a.out / "freeze.json").read_bytes())


def test_changed_packet_is_rejected_before_intake(tmp_path):
    archive, manifest, _ = packet(tmp_path)
    args = freeze_args(tmp_path, archive, manifest, annotations(), "review")
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="archive hash"):
        freeze(args)
