# Broader task audit: frozen design v1

Prepared 2026-11-15 before inspecting or annotating the newly selected cases. This is
an audit of the existing exposed fresh dataset, not a new confirmation set for a
localization method. The prior pilot's judgments remain provisional and are excluded
from estimates for this new frame.

## Population and sample

Exclude all 24 original development projects, including both fit and validation
projects, using case-normalized repository identifiers. Keep reports marked `unchanged`.
Group related PR rows by repository and underlying issue. Represent each issue by
its lexicographically first PR ID; retain other IDs for traceability. Repository
aliases/forks and report duplicates across issues are not yet audited.

The eligible frame contains 401 underlying issues in 50 projects. Include every
eligible project and select up to two issues within each. Rank issue groups by SHA256
of the compact JSON array `["allfather-task-audit-v1:37", project_key, issue_string]`,
breaking hash ties by issue string. No gold, prediction, score, failure description,
previous annotation, or target count enters selection. The source file is projected
to metadata and report text immediately on ingestion.

This produces 95 selected issues. Wave 1 has one issue per project (50); Wave 2 adds
the second issue in projects with at least two (45). Both waves are frozen together.
Waves organize review effort, not adaptive stopping. Retain unresolved cases and
unavailable patches; never replace a case because it is difficult or inconvenient.
If work stops early, report the incomplete wave and its missingness explicitly.

## Estimands and limits

The primary descriptive target is the mean project-level rate of each annotated
property across these 50 eligible projects. Within project p, estimate its rate by
the mean of its m_p selected issues; average those project means with weight 1/50.
For the secondary issue-weighted eligible-frame rate, weight each project mean by
N_p/401, where N_p is its eligible issue count. Store nominal inclusion m_p/N_p and
use the complete frozen sample, not a simple pooled 95-row rate mislabeled as the
401-issue population rate. Hash ranking is a reproducible pseudorandom design;
statistical interpretation of these weights assumes exchangeability of hash ranks
with the property being measured.

These estimands concern only the eligible frame, not all 580 original rows or arbitrary
future projects. Sampling variability, annotation uncertainty and unresolved judgments
are separate. Do not report a precision/power guarantee from sample size alone.
Unknown categories remain explicit; report bounds treating unresolved judgments both
ways for binary prevalence statements. No significance tests, performance comparisons,
or method selection are planned before annotations are independently reviewed and the
outcome-analysis protocol is frozen. Metadata-only frame and hash checks are permitted.

## Two-stage independent annotation

Each reviewer completes a private Stage A sheet from reports only. Do not open
patches, model outputs, prior analyst annotations or the other reviewer's sheet.
Record prior exposure; original report text may itself identify symbols or propose
solutions. Masking cannot reverse prior knowledge. Freeze and hash each completed
Stage A sheet before Stage B.

Use these Stage A fields:

| Field | Coding |
|---|---|
| `task_kind` | `bug`, `feature`, `maintenance`, `mixed`, `unclear` |
| `scope` | `focused`, `multiple_requests`, `umbrella`, `unclear` |
| `requested_behavior` | Report's requested change without guessed implementation |
| `observed_behavior`, `expected_behavior` | Describe what the report states; use `not_stated` when absent |
| `reproduction_evidence` | `concrete_steps`, `example_or_log`, `assertion_only`, `not_applicable`, `unclear`; distinguish proposed steps from an observed reproduction in notes |
| `report_anchors` | Literal symbols, paths, APIs, errors or configuration names already in the report |
| `underspecification` | `none_identified`, `missing_acceptance_criteria`, `multiple_plausible_subtasks`, `external_context_required`, `unclear` |
| `evidence_quotes` | Short exact excerpts; include character offsets when practical |
| `confidence` | `high`, `medium`, `low`; never an exclusion rule |
| `reviewer`, `prior_exposure`, `notes` | Reviewer identity, exposure and unresolved reasoning |

A bug reports undesirable existing behavior; a feature requests new capability;
maintenance concerns internal upkeep/hardening. Mixed is available when neither
dominates. An umbrella coordinates multiple potential deliverables. Missing a source
symbol does not imply underspecification, and a feature request is not automatically
invalid for localization. `none_identified` is not proof of report sufficiency.

For Stage B, inspect the exact base/merge patch and source, after Stage A is frozen:

- Case alignment: `direct`, `partial_subtask`, `broader_than_report`, `unclear`, or
  `unavailable`. Explain the report/patch link with concrete evidence.
- Each original target's edit role: `behavioral` (directly changes the reported
  behavior), `supporting_integration` (schema, wiring, compatibility or relocation
  supporting the change), `incidental` (unrelated/cosmetic edit), or `unresolved`.
  These are descriptions, not proof of causality or a replacement answer key.
- Record added implementation outside the base-symbol universe, dependency-boundary
  fixes, and plausible alternate implementation sites. Distinguish added functionality
  from refactoring and parser artifacts. Do not infer counts of new behavior from AST IDs.
- Record missing evidence. A missing patch is not a misaligned patch. Do not execute
  report or patch code during annotation without a separate reproduction plan.

Two independent initial reviews precede adjudication. Preserve both original sheets,
report disagreement and missingness by category, and record adjudication reasons.
Do not claim independent agreement from repeated work by the already-exposed analyst.
No reviewer has been assigned by this design and nobody is contacted automatically.

## Interpretation and next gate

This study tests whether report/reference boundaries materially affect interpretations
of localization evidence. Tangled fixes, noisy labels, and automated bug-fix labeling
already have prior art; finding examples is not itself novel. A differentiated claim
requires independently supported findings, a complete related-work comparison and a
frozen analysis showing their consequences. Original labels and scores remain immutable.
The new audit cohort is not available for tuning the earlier corrective-search methods.

Start by independently reviewing the prepared 23-case pilot packet to check the rubric.
The broader sample membership is already fixed. Any rubric revision must be versioned
before applying it to the new cases; do not adapt categories to produce desired outcomes.
Stage B preparation and scoring remain separate from this report-only packet.
