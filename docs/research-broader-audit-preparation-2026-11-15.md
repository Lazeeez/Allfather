# Broader audit preparation, 2026-11-15

The [fixed design](research-broader-audit-v1.md),
[sample manifest](../data/research/task-audit-sample-v1.json), and
[report-only reviewer packet](../results/research/corrections/broader-task-audit-v1/report-only-review.zip)
are prepared. No new cases have been annotated and no model outcomes have been joined.
No independent review has been completed. The existing exposed data cannot serve as a
prospective confirmation set for a new method.

## Sample

Excluding all 24 original development projects leaves 401 issue groups in 50 projects.
Every eligible project contributes up to two issues, selected by a fixed SHA256 order.
The first wave includes 50 cases; the second adds 45. All 95 memberships are fixed now.
The selection reads identifiers, language, report status and original report text only;
it does not consult target counts, gold labels, model outcomes or earlier judgments.

| Project language | Selected issues |
|---|---:|
| Go | 21 |
| Java | 12 |
| JavaScript | 11 |
| Python | 15 |
| Rust | 22 |
| TypeScript | 14 |
| Total | 95 |

These are project-language strata, not per-target parser languages. The primary
descriptive estimand gives each eligible project equal weight. The secondary
issue-weighted estimate uses project sizes in the frozen frame. A pooled rate over
the 95 cases is not automatically an estimate over all 401 eligible issues. Hash ranks
provide reproducibility; their statistical use assumes exchangeability with the
property being measured. Unknown judgments and missing evidence must remain visible.
Repository aliases, forks and cross-issue duplicates remain an audit limitation.

## Review handoff

First use the existing
[23-case pilot review packet](../results/research/corrections/task-audit-reviewer-pack-v1.zip)
to check the rubric with two independent initial reviewers. The analyst's provisional
judgments do not substitute for that review. Preserve both initial sheets before
adjudication, with reviewer identities, exposure disclosures and reasons for changes.

Any rubric revision must be versioned before applying it to the broader sample.
For the new cases, distribute only `report-only-review.zip`; its two wave directories
contain original reports and blank Stage A sheets. Each reviewer freezes Stage A
before inspecting patches or another reviewer's judgments. Original reports can
themselves identify proposed fixes; the packet does not guarantee blinding.

Keep the separate manifest and case mapping with the coordinator. The broader packet
contains no model rankings, gold targets or prior annotations. Stage B evidence and
outcome analysis are later steps. Nobody has been contacted or assigned automatically.
No PACE job or model download is needed for this handoff.

## Provenance and reproduction

The [packet manifest](../results/research/corrections/broader-task-audit-v1/manifest.json)
records every archive member's SHA256 and the private case mapping. The sample records
dataset, original development plan, sampler, packet helper and rubric hashes.

```text
sample SHA256:  a086fe0ddf3dffe45a32291fed364c6e6389b88086e612be27ed5d64bfadc97a
archive SHA256: 03e1503e77da5cc720631a350955c33b80320132368b3d140a0b9f7372ac2da0
archive bytes:  140630
```

To reproduce without overwriting the frozen outputs, use new paths:

```bash
python scripts/sample_task_audit.py \
  --plan reports/broader-audit-repeat/sample.json \
  --out reports/broader-audit-repeat/packet
```

Compare sample and member hashes; ZIP compression bytes can vary across runtimes.
Tests cover invariance to injected outcomes and input order, grouping related PRs,
development-project exclusion, changed-report exclusion, invalid identifiers/languages,
report integrity and the review packet's field allowlist. Research validity still
depends on independent annotations and a frozen analysis, not on passing these checks.
The full local suite passes 282 tests. Reconstructing the sample reproduces it exactly;
all six archive members and the archive itself pass their recorded hash checks.
