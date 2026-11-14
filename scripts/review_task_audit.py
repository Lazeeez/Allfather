"""Validate and freeze returned audit sheets; compare declared independent initial reviews."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ENUMS = {
    "task_kind": {"bug", "feature", "maintenance", "mixed", "unclear"},
    "scope": {"focused", "multiple_requests", "umbrella", "unclear"},
    "reproduction_evidence": {
        "concrete_steps",
        "example_or_log",
        "assertion_only",
        "not_applicable",
        "unclear",
    },
    "underspecification": {
        "none_identified",
        "missing_acceptance_criteria",
        "multiple_plausible_subtasks",
        "external_context_required",
        "unclear",
    },
    "confidence": {"high", "medium", "low"},
    "alignment": {"direct", "partial_subtask", "broader_than_report", "unclear", "unavailable"},
    "role": {"behavioral", "supporting_integration", "incidental", "unresolved"},
}
MEMBERS = {
    "stage-a/stage-a.csv",
    "wave-1/stage-a.csv",
    "wave-2/stage-a.csv",
    "stage-b/case-alignment.csv",
    "stage-b/target-roles.csv",
}
OPTIONAL = {"notes", "report_anchors", "alternative_locations"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_sheet(data: bytes) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames
    if not fields or len(fields) != len(set(fields)):
        raise ValueError("missing or duplicate CSV headers")
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("CSV row has wrong column count")
        rows.append({k: v.strip() for k, v in row.items()})
    return fields, rows


def keys(rows: list[dict], columns: list[str]) -> dict[tuple, dict]:
    indexed = {tuple(r[k] for k in columns): r for r in rows}
    if len(indexed) != len(rows) or any(not all(k) for k in indexed):
        raise ValueError("duplicate or empty case/target identity")
    return indexed


def validate_sheet(template: bytes, data: bytes) -> tuple[list[dict], list[str]]:
    fields, expected = read_sheet(template)
    actual_fields, rows = read_sheet(data)
    if actual_fields != fields:
        raise ValueError("sheet columns do not match the frozen template")
    columns = ["case", "target"] if "target" in fields else ["case"]
    if set(keys(rows, columns)) != set(keys(expected, columns)):
        raise ValueError("sheet must contain exactly the frozen cases/targets")
    for row in rows:
        for field, value in row.items():
            if field not in OPTIONAL and not value:
                raise ValueError(f"incomplete sheet: {row['case']} {field}")
            if field in ENUMS and value not in ENUMS[field]:
                raise ValueError(f"invalid {field}: {value}")
    if len({r["reviewer"].casefold() for r in rows}) != 1:
        raise ValueError("each sheet must contain one reviewer identity")
    return sorted(rows, key=lambda r: tuple(r[k] for k in columns)), columns


def verified_packet(packet: Path, manifest: Path) -> dict[str, bytes]:
    metadata = json.loads(manifest.read_bytes())
    raw = packet.read_bytes()
    if digest(raw) != metadata["archive_sha256"]:
        raise ValueError("packet archive hash mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(metadata["files_sha256"]):
            raise ValueError("packet member list mismatch")
        files = {name: archive.read(name) for name in names}
    if any(digest(data) != metadata["files_sha256"][name] for name, data in files.items()):
        raise ValueError("packet member hash mismatch")
    return files


def write_json(path: Path, value: dict) -> None:
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


def load_freeze(path: Path) -> tuple[dict, list[dict]]:
    metadata = json.loads((path / "freeze.json").read_bytes())
    if (
        metadata.get("schema") != "audit-review-freeze-v1"
        or metadata.get("reviewer_kind") not in ("human", "automated")
        or type(metadata.get("independent_initial_declared")) is not bool
    ):
        raise ValueError("invalid freeze declaration")
    for name, expected in metadata["files_sha256"].items():
        if name not in {"submitted.csv", "rows.jsonl", "template.csv"}:
            raise ValueError("unexpected freeze member")
        if digest((path / name).read_bytes()) != expected:
            raise ValueError("frozen review hash mismatch")
    if set(metadata["files_sha256"]) != {"submitted.csv", "rows.jsonl", "template.csv"}:
        raise ValueError("incomplete freeze manifest")
    rows = [json.loads(s) for s in (path / "rows.jsonl").read_bytes().splitlines()]
    checked, columns = validate_sheet(
        (path / "template.csv").read_bytes(), (path / "submitted.csv").read_bytes()
    )
    if (
        len(rows) != metadata["rows"]
        or not rows
        or rows != checked
        or columns != metadata["key_columns"]
        or rows[0]["reviewer"] != metadata["reviewer"]
    ):
        raise ValueError("freeze metadata disagrees with submitted sheet")
    return metadata, rows


def freeze(args: argparse.Namespace) -> dict:
    if args.out.exists():
        raise ValueError("use a new output directory")
    files = verified_packet(args.packet, args.manifest)
    if args.member not in MEMBERS or args.member not in files:
        raise ValueError("unsupported sheet member")
    raw = args.sheet.read_bytes()
    rows, columns = validate_sheet(files[args.member], raw)
    parent = None
    if args.member.startswith("stage-b/"):
        if args.stage_a is None:
            raise ValueError("Stage B requires this reviewer's earlier Stage A freeze")
        prior, prior_rows = load_freeze(args.stage_a)
        if prior["member"] != "stage-a/stage-a.csv" or prior["packet_sha256"] != digest(
            args.packet.read_bytes()
        ):
            raise ValueError("Stage A is from a different packet or stage")
        if prior["reviewer"].casefold() != rows[0]["reviewer"].casefold():
            raise ValueError("Stage A reviewer mismatch")
        if not {r["case"] for r in rows} <= {r["case"] for r in prior_rows}:
            raise ValueError("Stage B has cases absent from Stage A")
        if (
            prior["reviewer_kind"] != args.reviewer_kind
            or prior["independent_initial_declared"] != args.independent_initial
        ):
            raise ValueError("reviewer declaration changed between stages")
        parent = digest((args.stage_a / "freeze.json").read_bytes())
    payloads = {
        "submitted.csv": raw,
        "template.csv": files[args.member],
        "rows.jsonl": "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode(),
    }
    metadata = {
        "schema": "audit-review-freeze-v1",
        "received_at": datetime.now(UTC).isoformat(),
        "member": args.member,
        "packet_sha256": digest(args.packet.read_bytes()),
        "packet_manifest_sha256": digest(args.manifest.read_bytes()),
        "rubric_sha256": digest(files["rubric.md"]),
        "script_sha256": digest(Path(__file__).read_bytes()),
        "reviewer": rows[0]["reviewer"],
        "reviewer_kind": args.reviewer_kind,
        "independent_initial_declared": args.independent_initial,
        "key_columns": columns,
        "rows": len(rows),
        "stage_a_freeze_sha256": parent,
        "files_sha256": {name: digest(data) for name, data in payloads.items()},
        "limitations": "Receipt time and declarations do not prove independence, blinding, annotation order, expertise or semantic correctness. Evidence text requires manual verification.",
    }
    args.out.mkdir(parents=True)
    for name, data in payloads.items():
        (args.out / name).write_bytes(data)
    write_json(args.out / "freeze.json", metadata)
    return metadata


def agreement(a: list[str], b: list[str]) -> dict:
    if not a or len(a) != len(b):
        raise ValueError("agreement requires nonempty paired labels")
    ca, cb = Counter(a), Counter(b)
    matched = sum(x == y for x, y in zip(a, b, strict=True))
    observed = matched / len(a)
    expected = sum(ca[v] * cb[v] for v in set(a) | set(b)) / len(a) ** 2
    return {
        "rows": len(a),
        "matched": matched,
        "raw_agreement": observed,
        "kappa": (observed - expected) / (1 - expected) if expected < 1 else None,
        "kappa_note": "Undefined for degenerate marginals; no independent sampling assumption or uncertainty interval is claimed.",
        "confusion": [
            {"a": x, "b": y, "count": n}
            for (x, y), n in sorted(Counter(zip(a, b, strict=True)).items())
        ],
    }


def compare(left: Path, right: Path) -> dict:
    a, ra = load_freeze(left)
    b, rb = load_freeze(right)
    for field in ("member", "packet_sha256", "rubric_sha256", "key_columns"):
        if a[field] != b[field]:
            raise ValueError(f"review comparison mismatch: {field}")
    if a["reviewer"].casefold() == b["reviewer"].casefold():
        raise ValueError("same reviewer cannot supply independent agreement")
    if any(m["reviewer_kind"] != "human" or not m["independent_initial_declared"] for m in (a, b)):
        raise ValueError("requires two declared independent initial human reviews")
    ka, kb = keys(ra, a["key_columns"]), keys(rb, b["key_columns"])
    if set(ka) != set(kb):
        raise ValueError("review case/target mismatch")
    ordered = sorted(ka)
    fields = sorted(set(ENUMS) & set(ra[0]))
    return {
        "schema": "audit-review-agreement-v1",
        "reviewers": [a["reviewer"], b["reviewer"]],
        "member": a["member"],
        "packet_sha256": a["packet_sha256"],
        "freeze_sha256": [digest((p / "freeze.json").read_bytes()) for p in (left, right)],
        "fields": {
            f: agreement([ka[k][f] for k in ordered], [kb[k][f] for k in ordered]) for f in fields
        },
        "disagreements": [
            {
                "identity": list(k),
                "fields": {f: [ka[k][f], kb[k][f]] for f in fields if ka[k][f] != kb[k][f]},
            }
            for k in ordered
            if any(ka[k][f] != kb[k][f] for f in fields)
        ],
        "status": "Descriptive comparison before adjudication; declarations are not independently verified. Original labels are unchanged.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fp = sub.add_parser("freeze")
    for name in ("packet", "manifest", "sheet", "out"):
        fp.add_argument(f"--{name}", type=Path, required=True)
    fp.add_argument("--member", choices=sorted(MEMBERS), required=True)
    fp.add_argument("--reviewer-kind", choices=("human", "automated"), required=True)
    fp.add_argument("--independent-initial", action="store_true")
    fp.add_argument("--stage-a", type=Path)
    cp = sub.add_parser("compare")
    for name in ("left", "right", "out"):
        cp.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(args)
        print(json.dumps({k: result[k] for k in ("rows", "reviewer", "member")}))
    else:
        if args.out.exists():
            raise ValueError("use a new comparison output path")
        result = compare(args.left, args.right)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.out, result)
        print(f"Compared {len(result['fields'])} categorical fields; no adjudication performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
