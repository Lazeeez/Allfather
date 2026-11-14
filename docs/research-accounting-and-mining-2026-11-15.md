# Accounting and mining corrections, 2026-11-15

The active analysis and paper-generation paths now share per-record monetary accounting.
Missing amounts remain unknown. Historical local-compute zeros are recognized as
placeholders, and future website replays explicitly record unknown monetary cost.
Historical datasets, prediction files, analyses and generated manuscript tables are
preserved. These changes do not validate the historical evaluator or establish a cost
advantage.

## Recorded cost evidence

The [versioned audit](../results/research/corrections/cost-accounting-v1.json) covers
47 saved runs in the four fresh-data conditions, totaling 14,825 run rows. These include
reused subset rows and are not independent observations or unique issues. Only 297 rows
across four runs have recorded monetary amounts; 14,528 are unknown under the corrected
accounting. Recorded amounts are harness reports, not independently verified bills.

The shared module distinguishes `recorded`, `estimated` and `unknown`. Estimates require
an explicit amount, basis and accounting scope through `cost_accounting` schema
`run-cost-v1`; supplying that metadata is not independent verification of an estimate.
No new token-price or GPU-rental estimates are made here. Historical aggregate token
counts cannot determine per-request long-context tiers, and the saved open-model wall
times do not establish exclusive allocation, GPU count, setup or retry attribution.

Incomplete cohorts have a null mean, with known counts/subtotals reported separately.
Different accounting scopes cannot be summed into a complete mean. Both analysis and
paper generation charge the cheap run for every paired issue and the incremental agent
run only for the selected issues. They use exactly the same IDs and threshold. An unknown
agent cost on an unselected issue does not invalidate the cascade total; an unknown
required component does. Descriptive cost frontiers group identical cohorts and accounting
boundaries, and exclude unknown costs. This is not a statistical superiority claim.

Missing timing data likewise remain unknown. Python replay times are still not browser
latencies. Unsupported rental multipliers and differences of medians have been removed
from paper generation. A local rendering smoke check generated all 17 files in
`reports/paper-cost-smoke-v1`; those files combine historical accuracy analyses with
corrected accounting and are not publication-ready tables.

To regenerate the accounting audit, choose a new path:

```bash
python scripts/audit_research_costs.py --out reports/cost-audit-repeat.json
```

The analysis and paper CLIs now require `--out` and refuse existing destinations. For
example, `python scripts/paper_tables.py --out reports/paper-review-v2`. This prevents
accidental replacement of historical artifacts. The paper's final accuracy tables still
need migration to the frozen inventory-based scorer and explicit claim review.

## Future mining

`fresh_set.py` now accepts a null `lastEditedAt` only within a complete successful
GraphQL response. Missing objects/fields, malformed timestamps and error responses
cannot become evidence of an unedited report. HTTP rate/access limits and GraphQL
`RATE_LIMITED` stop collection through the existing resumable limit path. GitHub documents
that primary rate limits can return HTTP 200 with an error, so HTTP success alone is
insufficient ([GitHub API documentation](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)).

Newly mined records retain the complete `GoldEntry`, including errors, added files,
module-level files and non-indexed files. Any extraction error marks the candidate
ineligible, while retaining partial evidence for diagnosis. New provenance stores report
and patch text hashes, the validated edit timestamp and all merge parents. The base is
explicitly the merge commit's first parent, not necessarily a report-time snapshot.
These are hashes of returned UTF-8 text, not proofs that GitHub supplied a complete diff.

All 312 local tests pass, including regressions for partial GraphQL responses, unknown
costs, local zero placeholders, selected-call accounting, mismatched cost cohorts and
preservation of partial gold evidence. Ruff checks and the 17-file table-rendering smoke
check pass. No live API mining or model inference was needed for verification.

No historical mining was rerun and no legacy label was repaired. Historical edit checks
and discarded extraction errors cannot be retroactively certified by this code change.
Parser coverage, truncated API diffs, multi-commit/rebase interpretation, repository
lineage, and all benchmark labels' causal adequacy remain separate evidence requirements.
