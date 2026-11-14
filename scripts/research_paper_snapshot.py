"""Build a versioned working-paper number snapshot from corrected, saved analyses only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "paired": "results/research/corrections/inventory-paired-v1.json",
    "pilot": "results/research/corrections/development-analysis-v1/analysis.json",
    "validation": "results/research/corrections/text-view-validation-analysis-v1/analysis.json",
    "audit": "results/research/corrections/task-audit-analysis-v1/analysis.json",
    "sample": "data/research/task-audit-sample-v1.json",
    "cost": "results/research/corrections/cost-accounting-v1.json",
}


def snapshot(out: Path) -> dict:
    if out.exists():
        raise ValueError("use a new paper snapshot directory")
    raw = {name: (ROOT / path).read_bytes() for name, path in SOURCES.items()}
    data = {name: json.loads(value) for name, value in raw.items()}
    paired = data["paired"]["comparisons"][
        "strict_symbol/all/fresh-full_website-gpu-minus-fresh-full_swerank-embed-large"
    ]
    pilot = data["pilot"]["summaries"]["all/issue_pr/strict_symbol"]
    validation = data["validation"]["summaries"]["strict_symbol"]
    candidate = validation["actions"]["base_head_tail_head_tail"]
    audit, sample, costs = data["audit"], data["sample"]["counts"], data["cost"]["runs"]
    values = {
        "FullIssues": paired["issues"],
        "FullProjects": paired["projects"],
        "GPUHits": paired["b_hits"],
        "LargeHits": paired["a_hits"],
        "GPUHitRate": f"{100 * paired['b_hits'] / paired['issues']:.2f}",
        "LargeHitRate": f"{100 * paired['a_hits'] / paired['issues']:.2f}",
        "DeltaPoints": f"{100 * paired['issue_weighted']['delta_b_minus_a']:.2f}",
        "CILow": f"{100 * paired['issue_weighted']['project_bootstrap_ci95'][0]:.2f}",
        "CIHigh": f"{100 * paired['issue_weighted']['project_bootstrap_ci95'][1]:.2f}",
        "HolmP": f"{paired['issue_weighted']['p_holm']:.2f}",
        "ProjectDelta": f"{100 * paired['project_weighted']['delta_b_minus_a']:.2f}",
        "PilotRows": pilot["rows"],
        "PilotProjects": pilot["projects"],
        "PilotBaseHits": pilot["actions"]["base_ce50"]["hits"],
        "PilotOracleHits": pilot["oracle_hits"],
        "ValidationRows": validation["rows"],
        "ValidationBaseHits": validation["actions"]["base_prefix_prefix"]["hits"],
        "ValidationCandidateHits": candidate["hits"],
        "ValidationRescues": len(candidate["rescues"]),
        "ValidationHarms": len(candidate["harms"]),
        "AuditIssues": audit["issues"],
        "AuditTargets": audit["targets"],
        "AuditDiffs": audit["verified_file_diffs"],
        "IncidentalTargets": audit["role_counts"]["incidental"],
        "IncidentalOnlyHits": sum(
            len(v) for v in audit["strata"]["all"]["incidental_only_hits"].values()
        ),
        "BroaderIssues": sample["selected_issues"],
        "BroaderProjects": sample["eligible_projects"],
        "BroaderFrame": sample["eligible_issues"],
        "CostRuns": len(costs),
        "CostRows": sum(r["rows"] for r in costs.values()),
        "CostUnknown": sum(r["states"].get("unknown", 0) for r in costs.values()),
        "CostRecorded": sum(r["states"].get("recorded", 0) for r in costs.values()),
    }
    tex = (
        "% Generated from corrected exploratory analyses; not a new confirmation result.\n"
        + "".join("\\newcommand{\\" + k + "}{" + str(v) + "}\n" for k, v in values.items())
    ).encode()
    manifest = {
        "schema": "working-paper-evidence-v1",
        "scope": "Number provenance only; does not independently revalidate analyses or make the manuscript submission-ready.",
        "input_sha256": {
            SOURCES[name]: hashlib.sha256(value).hexdigest() for name, value in raw.items()
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "numbers_sha256": hashlib.sha256(tex).hexdigest(),
        "values": values,
    }
    out.mkdir(parents=True)
    (out / "numbers.tex").write_bytes(tex)
    (out / "manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = snapshot(args.out)
    print(
        f"Wrote {len(result['values'])} macros from {len(result['input_sha256'])} corrected artifacts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
