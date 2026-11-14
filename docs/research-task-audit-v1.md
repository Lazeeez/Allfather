# Report-to-patch audit: development protocol v1

Status: prepared on 2026-11-15; annotations are not complete. This is an exploratory
audit of all 23 original fit issues, across 12 projects, with the original labels
and denominators retained. It follows the negative text-view validation and
[candidate-coverage probe](research-coverage-probe-2026-11-15.md).

## Question and boundaries

Does a failure reflect missing retrievable evidence, or a mismatch between the
report's requested change and the linked patch used as its answer key? Neither a
feature request nor a broad issue is automatically invalid. Patch-modified code
is a reference edit set, not proof of a unique causal fault or the only valid solution.

We have already inspected model outcomes and selected patches. Therefore annotations
by the current analyst cannot be called blind. Preparing report-only packets limits
additional exposure; it does not undo existing knowledge. A defensible larger study
needs independent reviewers and a fresh, outcome-independent audit sample. This
23-case development audit cannot estimate dataset-wide defect prevalence.

## Stage A: report only

Review every original fit report in full, without opening model predictions, gold
symbols, linked patches or repository search results. Preserve original text and
record concise supporting quotes; do not infer missing requirements from the eventual
patch. Mark unknowns explicitly. The packet can contain links and fixes already
present in the original report, so it is masked to added outcomes, not guaranteed
free of solution hints.

| Field | Values / rule |
|---|---|
| `task_kind` | `bug`, `feature`, `maintenance`, `mixed`, or `unclear`. Bug describes undesired existing behavior; feature requests new capability. |
| `scope` | `focused`, `multiple_requests`, `umbrella`, or `unclear`. Umbrella coordinates several possible subchanges rather than specifying one deliverable. |
| `requested_behavior` | Neutral description of what the report asks to change, without guessed implementation. |
| `observed_behavior` | Reported current behavior or `not_stated`. |
| `expected_behavior` | Reported intended behavior or `not_stated`. |
| `reproduction_evidence` | `concrete_steps`, `example_or_log`, `assertion_only`, `not_applicable`, or `unclear`; explain mixed evidence in notes. |
| `report_anchors` | Literal file/symbol/API/error/config names supplied by the report. Do not add names learned from a patch. Empty is allowed. |
| `underspecification` | `none_identified`, `missing_acceptance_criteria`, `multiple_plausible_subtasks`, `external_context_required`, or `unclear`; describe the missing information. This is a reviewer assessment, not ground truth. |
| `evidence_quotes` | Short exact report excerpts supporting the categories; retain offsets when practical. |
| `confidence` | `high`, `medium`, or `low`; confidence is not used to remove cases. |
| `reviewer`, `prior_exposure`, `notes` | Reviewer identifier, known prior exposure, and unresolved interpretation. |

Save and hash completed Stage A sheets before Stage B. Do not silently revise a
Stage A judgment after seeing the patch: retain the original and log any correction
as a separate adjudication with its reason. Two independent initial reviews are
required before claiming agreement; report confusion/counts and disagreements,
then reconcile with a documented adjudicator. One automated review is a provisional
annotation, not independent consensus.

## Stage B: report, base snapshot and linked patch

After freezing Stage A, inspect available patch provenance and base source. Record:

- Patch alignment: `direct`, `partial_subtask`, `broader_than_report`, `unclear`, or
  `unavailable`, with concrete report/patch evidence and uncertainty.
- Whether the reference edits existing declarations, adds new declarations, or both.
  Explicitly identify added-only behavior omitted by base-symbol scoring.
- For each target, whether the change appears behavioral, supporting/integration,
  incidental, or unresolved. These are descriptive judgments, not causal labels.
- Whether the report admits plausible alternative implementation locations; describe
  the reasoning without adding unverified alternatives to official gold.
- Missing blobs, patch fragments and external context as missing evidence. Do not
  infer a patch is misaligned because it is unavailable or a localizer missed it.

Only then join model outcomes. Publish an all-case table, annotation uncertainty,
task-stratified coverage and ranking outcomes, and sensitivity to unresolved categories.
Small strata are descriptive. Do not remove hard cases or claim a method improvement
from an easier post-hoc subset.

## Decision after the audit

If several projects have concrete report evidence missed by the candidate generators,
define one mechanism for recovering that evidence, then freeze new controls and a
cost-accounted experiment. A new method must be distinguished from planned structural
inspection, query reformulation and representation-based retrieval already in the
literature. Candidate presence alone is insufficient; test downstream ranking too.

If ambiguity or report–patch scope dominates, develop an evaluation study of reference
adequacy and stage-specific failure measurement. First check its own prior art, expand
to an outcome-independent sample and obtain independent annotation. Do not describe
the present exploratory audit as a validated new benchmark or novel method.

Validation cases remain excluded from mechanism tuning. Future confirmation needs
fresh frozen data; previously exposed development results cannot become a test set.

## Preparing the packet

```bash
python scripts/prepare_task_audit.py --out reports/task-audit-v1
```

Use a new output directory. The script verifies the frozen dataset/query hashes,
projects records to report fields, exports `reports.jsonl` and a blank `stage-a.csv`,
and records provenance separately in `manifest.json`. Give the first two files and
this rubric to a report reviewer; withhold the case-to-PR mapping and outcome files
during Stage A. No paid inference, PACE job, or model download is needed to prepare it.
