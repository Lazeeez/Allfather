# Frozen text-view validation: negative primary result

Updated 2026-11-15 (Asia/Tokyo). PACE job **7049176**, commit `8c71e19`, completed
24/24 validation PR rows with no failures. The transferred archive is verified and
all 16 conditions have been scored under the frozen protocol.

**The selected head/tail query-plus-document candidate did not improve validation.**
Retain the original base-50 prefix baseline. Do not replace the frozen candidate
with a different diagnostic condition or train a context-view router from these results.
This closes the current candidate's improvement claim, not the broader research project.

## Primary comparison and sensitivity

The [pre-run protocol](../data/research/text-view-validation-v1.json) selected
`base_head_tail_head_tail` against `base_prefix_prefix`, using strict-symbol hit@10.
The primary unit is the underlying issue, represented by the lexicographically
first PR ID per case-normalized repository/issue. Consequently markitdown#2342 is
retained and #2356 is excluded from the primary denominator; both appear in the
all-PR sensitivity. This choice was frozen before validation inference.

| Metric / cohort | Original prefix baseline | Frozen head/tail candidate |
|---|---:|---:|
| Primary hit@10, 23 issues / 12 projects | **21/23 (91.30%)** | **20/23 (86.96%)** |
| Primary MRR@10 | .5812 | .5726 |
| Mean per-issue gold recall@10 | .7067 | .6574 |
| All labeled targets in top ten | 14/23 | 12/23 |
| All-PR hit@10 sensitivity | 21/24 (87.50%) | 20/24 (83.33%) |

There are **zero rescues and one harm**, `astral-sh/uv#21275`, whose uniquely
identified `upgrade_tool` target moves from rank 5 to rank 12. Document head/tail
alone ranks it 10; query head/tail alone ranks it 7. Their combination loses the
hit. This demonstrates an interaction in this case, not a universal causal rule
about source positions or tokens.

The primary hit@10 change is -4.35 percentage points. Its descriptive pointwise
project-bootstrap 95% interval is [-13.64, 0] points. This small, previously exposed
development cohort does not establish general inferiority or prospective statistical
confirmation. It does fail to support the candidate's proposed improvement.

All 65 primary targets (66 across all PR rows) have unique audited identities and
no gold-file parser flags. Strict-symbol and name-group results are identical.
Feature requests, misses and regressions remain in the denominators; no gold was edited.

## All diagnostic conditions

Rescues/harms compare each condition to its own pool's prefix baseline. These results
cannot replace the frozen primary comparison after observing validation outcomes.

| Pool | Query view | Document view | hit@10 / 23 | Rescues | Harms |
|---|---|---|---:|---:|---:|
| Base 50 | prefix | prefix | 21 | 0 | 0 |
| Base 50 | prefix | head/tail | 21 | 0 | 0 |
| Base 50 | prefix | lexical | 20 | 0 | 1 |
| Base 50 | prefix | random | 20 | 0 | 1 |
| Base 50 | head/tail | prefix | 21 | 0 | 0 |
| Base 50 | head/tail | head/tail | 20 | 0 | 1 |
| Base 50 | head/tail | lexical | 20 | 0 | 1 |
| Base 50 | head/tail | random | 20 | 0 | 1 |
| Wide 200 | prefix | prefix | 21 | 0 | 0 |
| Wide 200 | prefix | head/tail | 20 | 0 | 1 |
| Wide 200 | prefix | lexical | 20 | 0 | 1 |
| Wide 200 | prefix | random | 19 | 0 | 2 |
| Wide 200 | head/tail | prefix | 21 | 0 | 0 |
| Wide 200 | head/tail | head/tail | 19 | 0 | 2 |
| Wide 200 | head/tail | lexical | 20 | 0 | 1 |
| Wide 200 | head/tail | random | 20 | 0 | 1 |

The all-condition oracle union is **21/23**, exactly the original baseline's success
set. All-PR sensitivity is **21/24**, also the baseline's success set. No condition
rescues any original validation miss. Conditions with two harms additionally lose
`astral-sh/uv#22055`. Some lexical controls raise MRR while losing a hit; changing
the primary metric after seeing that tradeoff would not validate the original claim.

The remaining primary misses are markitdown#2342 and jadx#3044. The additional
related-PR row markitdown#2356 also remains a miss in every condition. There is no
incremental hit@10 oracle headroom from context-view selection on this cohort.
This does not rule out other retrieval actions or cost-saving policies not tested here.

## Integrity, cost and reproducibility

- Archive: `reports/validation-text-views-v1.tar.gz`, **5,967,475 bytes**;
  SHA256 `90f0c2ad6185c4ce3cac464f065afd05f1bf04376eb0b69da11af27108d215e8`.
- All 27 regular members and 24 compressed trace hashes verified without extraction.
- All 46 recorded Python source hashes match the recorded Git commit.
- Every token view exactly matches the frozen local preparation; all **384** rankings
  were rebuilt from saved raw scores, including unchanged ranking tails.
- All **48** original prefix comparisons match exactly in scores and rankings.
- No new model inference, downloads or training were needed for this analysis.
- **29 focused regression tests pass**, including outcome-independent issue selection,
  duplicate-PR sensitivity, archive identity, parity, input budgets and score checks.
  Rerunning the fit analysis reproduces every scored row and aggregate unchanged.

The script ran for 423.72 seconds: 47.42 seconds of shared preparation, 202.56 seconds
across sequential inference calls, and 173.75 seconds outside those component timers.
Across all 24 executed rows, each base variant counts 266,602 nonpadding token
positions and each wide variant 949,645. Equal counters do not establish equal
end-to-end cost or a deployment speedup; the remainder is not attributed by the
current instrumentation.

The [analysis JSON](../results/research/corrections/text-view-validation-analysis-v1/analysis.json)
includes the frozen primary comparison, all-PR sensitivity, integrity checks and
provenance. [Per-PR rows](../results/research/corrections/text-view-validation-analysis-v1/rows.jsonl)
retain all original slots, target ranks and diagnostic score substitutions. The
[complete metric table](../results/research/corrections/text-view-validation-analysis-v1/table.txt)
reports every condition, including MRR, recall and all-target coverage.

```bash
.venv/bin/python scripts/analyze_text_views.py \
  --protocol data/research/text-view-validation-v1.json \
  --archive reports/validation-text-views-v1.tar.gz \
  --parent reports/pace-development-7019874/development-pilot-v1 \
  --preparation reports/text-view-validation-prepare-v1 \
  --historical-bundle reports/pace-7012506 \
  --out reports/text-view-validation-analysis-reproduction
```

Use a new output directory. The original archive, pre-run preparation and parent
replays are retained unchanged. The preparation's manifest and index hashes are
anchored by the committed preparation record.

## Research decision and next work

The fit gain (18/23 to 19/23) did not transfer: validation loses one case with no
rescue. Pooling the fit gain and validation loss into an aggregate would obscure
the failed frozen comparison. The window-selection method is not a defensible main
contribution on this evidence. Existing prior-work overlap also remains unresolved.

1. Keep base-50 prefix reranking as the research reference. Preserve the negative
   result and controls as an ablation; do not change runtime defaults to head/tail.
2. End this window sweep and defer the proposed context-view router. No further PACE
   job is needed to decide this branch.
3. Return to **fit-only candidate-coverage failures and task validity** before
   designing another action: new-api and ComfyUI lose targets before reranking;
   claw-code's targets lie beyond both read limits. Investigate a mechanism that
   adds relevant candidates and compare it with established retrieval/reformulation
   baselines. Query reformulation alone is not a novel claim.
4. Require evidence of complementary action benefit and a precise prior-work
   distinction before allocating a larger method study. Otherwise narrow toward an
   evaluation study, whose generality and novelty also need to be demonstrated.
5. All current fit and validation data remain exposed development evidence. Any
   later confirmatory claim requires a newly frozen dataset and protocol. Do not
   tune against these validation outcomes and present another run as untouched validation.

No novelty, repair-success or developer-productivity claim follows from this experiment.
