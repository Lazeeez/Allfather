# Inventory rescoring: verified exploratory evidence

The transferred PACE archive is retained as
[`pace-rescore-7012506.tar.gz`](../results/research/corrections/pace-rescore-7012506.tar.gz),
SHA256 `e8da21e56d8b57f9f9dd6eec0da9432c04b4cc283fce24fa6c3fde3eebc5d753`.
All 29 prediction input hashes, scoring source hashes, audit hashes and score-file
hash match. All 25 run summaries reproduce from the transferred per-issue scores.
The complete gold review agrees with the audit and contains 33 issues. Original
snapshot inventory files are not in this archive, so their prior integrity audit
cannot be independently repeated from this transfer alone.

## Paired outcomes

These are strict-symbol hit@10 results on identical issue IDs. Positive deltas
favor B. Intervals resample whole projects and preserve system pairing; they are
pointwise 95% percentile intervals, not simultaneous confidence intervals.

| A → B | Issues / projects | B rescues / harms A | Delta, percentage points | Project-bootstrap interval |
|---|---:|---:|---:|---:|
| SweRankEmbed-Large → website-gpu | 580 / 74 | 41 / 37 | +0.69 | −2.69 to +3.95 |
| website → website-gpu | 580 / 74 | 28 / 12 | +2.76 | +0.37 to +5.34 |
| website → website-gpu, agent subset | 198 / 66 | 6 / 7 | −0.51 | −4.71 to +3.74 |
| website → Astra agent | 198 / 66 | 31 / 11 | +10.10 | +4.41 to +15.87 |
| website → Luna agent | 198 / 66 | 25 / 27 | −1.01 | −7.54 to +5.59 |

This does not establish superiority or equivalence over SweRankEmbed-Large. Equal
project weighting gives website-gpu a −1.14-point difference against it, with an
interval of −6.26 to +3.98. The different weighting answers a different question;
neither estimate should be selected because it favors Allfather.

The analysis reports two identity modes, three cohort views (all matched issues,
all-gold-unique, and deterministic issue-deduplicated), and both issue- and
project-weighted effects. The five comparisons across these choices form a single
60-test Holm family. Strict/all issue-weighted adjusted p-values are 1.0 for GPU
versus SweRankEmbed-Large and 0.126 for Astra versus website. No test in this family
passes 0.05. Positive pointwise intervals do not imply family-adjusted significance.
These are exploratory choices applied to exposed data, not preregistered confirmation.
Project sign-flip inference assumes independent projects and exchangeable paired
differences under the null. Related repositories and upstream model exposure remain
limitations.

The strict/all Astra joint outcomes contain 26 issues where only the agent succeeds,
one where only GPU succeeds, and 11 where both local variants succeed but the agent
fails. An oracle could succeed on 183/198 issues across the three outputs. The oracle
uses the answers; it demonstrates neither learnable action selection nor cost benefit.
Saved top-ten outputs still cannot distinguish an absent candidate from a ranking miss.

## Gold and parser diagnosis

All 78 flagged targets (65 ambiguous names plus 13 targets in parser-error files)
were inspected from cached Git base snapshots without fetching. Every target's
occurrence-kind/line-range multiset matches the PACE audit. Source hashes, parser
versions, start byte columns and parser error spans are retained in
[`gold-source-review-v1.json`](../results/research/corrections/gold-source-review-v1.json).

- Ambiguous target IDs comprise 42 JavaScript, 16 Java, three Python, two TypeScript
  and two Rust names. These language counts are not classifications of root cause.
- Only Traefik's `Provider.buildCORS` has a parser error overlapping its own line
  range. The other 12 targets' file-level errors lie outside their target ranges.
  This does not prove those targets were extracted semantically correctly.
- Next.js has 15 `e.constructor` occurrences on line 1 at different byte columns.
  Appending a line number to an ID would leave this collision unresolved.
- One `claude-mem` issue contributes 40 of the 65 ambiguous gold names and has 453
  gold targets. Its generated bundle warrants specific review; the current audit
  does not identify which occurrences are causally relevant.
- Across the full audit, 53 issues have more than ten gold IDs. Their `all@10` is
  structurally unattainable with a ten-slot answer, independent of model quality.
  Retain that limitation when reporting all-target success rather than silently
  changing the evaluated population.

No labels were deleted, renamed or disambiguated from prediction outcomes. A future
occurrence-level identity needs source spans (including columns/bytes for minified
code), compatible prediction/output contracts, and a patch/label migration. Simply
changing the scorer would not supply the missing occurrence-level gold information.

## Reproduction and next work

Extract the retained archive into a new directory, then run:

```bash
.venv/bin/python scripts/analyze_inventory_scores.py \
  --bundle reports/pace-7012506 --out reports/inventory-paired-reproduction.json
.venv/bin/python scripts/inspect_gold_sources.py \
  --review reports/pace-7012506/inventory-rescore-7012506/review-gold.json \
  --out reports/gold-source-review-reproduction.json
```

The second command requires the corresponding cached base blobs. Both refuse to
overwrite an existing output. The saved statistical analysis is
[`inventory-paired-v1.json`](../results/research/corrections/inventory-paired-v1.json),
with exact cohort IDs, project effects, bootstrap settings, adjusted p-values and
oracle diagnostics. Three regression tests verify project-level resampling,
micro/macro weighting, exact sign flips and outcome-independent issue deduplication.

The next modeling work is development-only stage logging and controlled wider
retrieval/reranking actions. Establish candidate-pool rescue and its predictability
against direct-benefit and simple confidence controls before committing to a routing
method. Freeze the final evaluator and identity interpretation before collecting
new confirmation data. The current results support investigating complementary
errors; they do not establish a novel successful method.
