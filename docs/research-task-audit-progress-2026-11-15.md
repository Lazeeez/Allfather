# Task audit: first report pass and patch availability

All 23 original fit reports have a frozen, provisional Stage A annotation under
the [fixed rubric](research-task-audit-v1.md). This is a single analyst's review
with prior outcome and some patch exposure, not a blind or independently validated
annotation set. Every supporting quote and anchor is checked against the original
report; quote offsets use Unicode code points. No gold labels or scores changed.

| Report category | Cases |
|---|---:|
| Bug | 19 |
| Feature request | 3 |
| CI maintenance/hardening | 1 |
| Focused scope | 22 |
| Umbrella scope | 1 |

The umbrella case requests completion of a 55-tool catalog. The model-support request
needs external context to specify integration details. Most other reports provide
concrete behavior, and several already include exact symbols or proposed fixes.
This pass therefore does not support attributing every failure to vague reports.
The classifications remain revisable through explicit independent adjudication;
they are not dataset-wide prevalence estimates or evidence of task invalidity.

## First concrete reference-label caveat

AutoGPT PR #14536 requests aggregate validation of stale skip allowances. Its frozen
base-to-merge diff changes two reference targets in `detect_overlaps.py` only by
sorting imported names and removing a redundant `f` prefix from a constant string.
These are provisionally marked incidental to the report. The existing
`validate_junit.py` targets integrate a version-aware policy, while new
`validate_backend_skips.py` functions implement aggregate checking but cannot be
members of a base-symbol candidate universe.

The six original local conditions already hit the relevant `validate_junit.py`
functions. This observation does not overturn their any-hit@10 result. It does show
why treating every touched symbol as equally relevant can distort target recall and
interpretations of newly covered targets. The earlier wide-200 coverage increase on
this case adds `find_file_overlap_candidates`, whose only recorded edit is import order.
Retain the original result and this caveat; do not silently repair gold to improve scores.

This is a source-supported example, not an estimate of how often reference-label
problems occur. Independent review, a broader sample, and a literature review of
reference adequacy remain necessary before framing it as a research contribution.

## Patch availability and next work

All 23 base-to-merge changed-path lists are available: 71 file entries in total.
Thirty-seven file diffs are locally available; 34 need uncached Git objects. Eight
cases have every file diff available. These counts describe availability, not completed
semantic review. Only the AutoGPT case above has a recorded Stage B target-role annotation
in the progress artifact. Missing patches must remain `unavailable`, not `misaligned`.
No lazy fetch, model download, paid inference, or cluster run was performed.

Next: obtain the missing pinned blobs without changing snapshots, complete Stage B
for every fit case, and obtain independent review before drawing stratum-level
conclusions or changing evaluation policy. Avoid another GPU sweep until a concrete
mechanism survives the existing coverage and prior-work checks.

## Artifacts and checks

- [Preparation manifest and case mapping](../results/research/corrections/task-audit-preparation-v1.json).
- [Frozen Stage A annotations](../results/research/corrections/task-audit-stage-a-v1/rows.jsonl)
  and [summary/hash](../results/research/corrections/task-audit-stage-a-v1/summary.json).
- [Stage B availability and source evidence](../results/research/corrections/task-audit-stage-b-progress-v1.json).
- Report-only packets are local in `reports/task-audit-v1`; patch captures are local
  in `reports/task-audit-stage-b-v1`. The preparation script reproducibly regenerates
  report packets; Stage B availability was collected by read-only Git commands
  (`diff --name-status`, then per-path `diff --no-ext-diff --no-textconv --no-renames -U3`)
  with lazy fetching and replacement objects disabled. Case captures and patches are hashed.

Seventeen new focused tests pass across coverage generation, coverage verification,
and report-packet integrity. The full suite passes all 268 tests; Ruff and whitespace
checks also pass. Hash-linked annotation/preparation files retain their original
bytes through explicit Git attributes, so line-ending normalization cannot invalidate
their recorded hashes when transferred to Linux.
