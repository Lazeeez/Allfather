# Complete provisional fit task audit

All 23 fit cases now have verified patch evidence, a provisional report–patch alignment
judgment, and a role annotation for every one of the 52 reference targets. This completes
the analyst pass, not independent adjudication or causal validation. No gold labels,
candidate universes, original scores, or validation decisions were changed.

## Evidence recovered

The collector retrieved 34 missing blobs (9,530,960 bytes per completed capture) from
exact public repository commits into temporary storage. Every byte sequence was checked
against its Git tree's blob ID; existing mirrors remained read-only. Temporary objects
were removed afterward. All 71 changed-file diffs are available. Binary archive diffs
remain binary-change indicators; their internal contents were not unpacked or audited.

The final capture records parser source hashes and versions and skips symbol parsing
for unsupported files. Its 71 patch hashes exactly match the initial successful capture.
All 52 old-symbol contexts also match the original retrieval units by content key.
The analyzer checks cohort membership, frozen annotations, source/evidence hashes,
complete target coverage and historical audit provenance before joining outcomes.

## Provisional findings

| Report–patch alignment | Cases |
|---|---:|
| Direct | 18 |
| Partial subtask | 1 |
| Broader than report | 3 |
| Unclear link to specific subtask | 1 |

| Reference-target role | Targets |
|---|---:|
| Behavioral edit | 22 |
| Supporting/integration edit | 27 |
| Incidental edit | 3 |

These are exposed single-analyst judgments, not independent consensus, prevalence
estimates for the full dataset, or a partition into valid and invalid targets.
Supporting edits can be legitimate localization outputs. Added declarations may be
new behavior or refactoring; neither their number nor their absence from a base-symbol
universe establishes benchmark invalidity.

Concrete boundaries identified:

- **Archify #991:** the patch changes a misleading status message. Its added test
  explicitly keeps a newly connected client without an artifact, while the report
  requests restoration of that artifact. This supports a partial-subtask judgment.
- **Claw-code #3332:** the patch implements read selectors; the report requests
  completion of a broad tool catalog without naming that specific enhancement.
  The subtask link remains unclear, not proven wrong.
- **ComfyUI #15922:** most model implementation is newly added. Existing gold captures
  integration points and a class whose own change only removes a docstring. The latter
  is provisionally incidental; separately indexed method edits remain relevant.
- **AutoGPT #14536:** two gold targets change only import order and a redundant string
  prefix. New aggregate-validation code is outside the base-symbol gold universe.
- **Zed #62534:** the in-repository gold edits adapt an API call and enum handling to a
  PET upgrade. Inspecting the [pinned upstream comparison](https://github.com/microsoft/python-environment-tools/compare/9e61a22af989fe54937bf07c9f9cff1bc53d9056...bb8e04607b96a3865d6aa4bb2a5a5a82ce05b5f0)
  reveals removal of direct system-Python probing in the Command Line Tools locator
  and filesystem-based alias resolution. This is supporting source evidence for the
  dependency fix, not a macOS runtime reproduction. The upgrade also includes other work.
- **Taste-skill #165:** the sole base-symbol target is an unchanged viewport classifier
  relocated into a new module; screenshot uniqueness is implemented in a new helper
  and top-level call sites. A touched base symbol can be a useful integration pointer
  without containing the actual new behavior.

## Effect on existing results

All original fit scores reproduce: base CE50 remains **18/23**. Every local condition's
incidental-only-hit list is empty. Therefore the three incidental annotations do not
overturn any observed any-hit@10 success. They still matter for target recall and
interpretation of candidate coverage. Do not publish a repaired leaderboard from these
provisional judgments.

| Stage A task category | Cases | Original base CE50 hits |
|---|---:|---:|
| Bug | 19 | 16 |
| Feature | 3 | 1 |
| Maintenance/hardening | 1 | 1 |

The bug-only slice still contains three misses. Task heterogeneity does not explain
away the remaining localization failures. These small post-hoc strata do not establish
method superiority or justify choosing an easier evaluation subset.

## Research decision and prior work

Keep the prefix reference, retain original denominators, and continue to defer a router.
The completed audit strengthens measurement boundaries; it does not establish a novel
localization method or show that label noise explains the negative experiments.

Label tangling is established prior art. [Herbold et al., EMSE 2022](https://link.springer.com/article/10.1007/s10664-021-10083-5)
provide fine-grained annotations of bug-fixing commits, with four annotators per line
and agreement-based consensus. Finding incidental edits alone is not a new contribution.
[König et al., 2026](https://arxiv.org/abs/2609.21616) also study local open-weight models
for bug-fix commit labeling; only its abstract was inspected here. An automated labeler
would need differentiation and independent validation, not merely a new prompt.

A possible empirical contribution would have to demonstrate how report scope, reference
roles, base-snapshot admissibility and cross-repository fixes affect conclusions about
retrieval coverage and escalation. That remains a research question, not a confirmed gap.
It needs a broader outcome-independent sample, independent annotation, and comparisons
with existing labeling/benchmark-validity work before any novelty claim is defensible.

## Independent-review handoff

The [independent-review packet](../results/research/corrections/task-audit-reviewer-pack-v1.zip) contains the original reports, blank
Stage A sheets, Stage B source evidence, and blank alignment/target-role sheets. It
excludes model outcomes and prior analyst judgments. Reviewers first freeze their report
assessment, then open patch evidence. Two independent initial reviews and explicit
adjudication remain necessary before claiming agreement. Nobody has been contacted and
no independent review has yet occurred. Original report/source text may reveal identities
or hints, and masking cannot undo a reviewer's prior exposure.

Next work is independent adjudication and an outcome-independent audit sampling plan;
more GPU inference is not needed to settle these measurement questions. The concrete
review packet is ready, so this requirement does not depend on additional implementation.

## Artifacts and reproduction

- [Frozen Stage B annotations](../results/research/corrections/task-audit-stage-b-v1/annotations.jsonl)
  and [freeze hashes](../results/research/corrections/task-audit-stage-b-v1/freeze.json).
- [Verified analysis](../results/research/corrections/task-audit-analysis-v1/analysis.json),
  [all-case outcome join](../results/research/corrections/task-audit-analysis-v1/rows.jsonl),
  and [all original-condition strata](../results/research/corrections/task-audit-analysis-v1/table.txt).
- [Independent-review packet checksums](../results/research/corrections/task-audit-reviewer-pack-v1.json).
- [Complete frozen patch evidence](../results/research/corrections/task-audit-evidence-v1.tar.gz)
  and [archive checksums](../results/research/corrections/task-audit-archives-v1.json).

Use a fresh capture directory and the existing cached Git trees. Downloaded source blobs
go to the OS temporary directory, never into the original mirrors. No model is loaded.

```bash
python scripts/prepare_patch_audit.py --download-missing --out reports/task-audit-patch-repeat
```

The analysis additionally verifies the frozen upstream PET comparison and exact captured
evidence. To reproduce the join from the committed evidence archive:

```bash
mkdir reports/task-audit-reproduction
tar -xzf results/research/corrections/task-audit-evidence-v1.tar.gz -C reports/task-audit-reproduction
python scripts/analyze_task_audit.py \
  --captures reports/task-audit-reproduction/task-audit-stage-b-v3 \
  --parent reports/pace-development-7019874/development-pilot-v1 \
  --out results/research/corrections/task-audit-analysis-repeat
```

Keep original captures with their freeze manifest rather than replacing them with a
different run. Nine new focused tests and the full **277-test** suite pass. The tests
check evidence and scoring invariants, not the correctness of semantic annotations.
