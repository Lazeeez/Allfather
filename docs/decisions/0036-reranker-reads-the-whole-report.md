# 0036: A GPU reranker that reads the whole bug report

## Status

Proposed, 2026-11-06. Written before any candidate below has been trained or scored.

## Context

The GPU reranker (Qwen3-Reranker-0.6B with candidate A's adapter, [ADR 0034](0034-gpu-reranker-other-languages.md)) reads at most 512 tokens of a bug report, about 2,000 characters, and drops the rest. It was trained the same way. Most training reports fit: of the 5,902 training bugs, the median report is 1,025 characters and 24% are longer than 2,000. Most fresh-2026 reports do not: their median is 2,556 characters and 63% are longer than 2,000.

On fresh-2026 the reranker added 4.5 points of function hit@10 over the browser when every report was cut to 1,500 characters of body, and 2.6 points with the full reports ([ADR 0033](0033-frontier-comparison-protocol.md)). That is consistent with the cut costing accuracy on long reports, but it is an observation on the test set, so it can motivate this test and cannot decide it. Everything below is decided on training bugs.

The reranker reads the report once and reuses its cached keys and values for all 50 candidate functions, so a longer report costs one longer prefix per request, not 50.

## Candidates

- **A (the baseline):** candidate A's five cross-validation adapters, reading 512 tokens of the report, as scored for ADR 0034 (`results/website-rerank/work/scores_cand-A.jsonl`).
- **A-read2048:** the same five adapters, unchanged, reading up to 2,048 tokens of the report. Only the input budget changes.
- **L:** candidate A's recipe (one LoRA adapter on Qwen3-Reranker-0.6B, one epoch, groups of 8, the same records and folds), trained and scored with up to 2,048 tokens of the report.

Each function still contributes at most 256 tokens. Nothing else is tuned; depth 50 and the per-language weights of `results/website-rerank/gpu_config.json` are kept.

## Decision rule

Fixed before any score exists. All comparisons use the same cross-validation as ADR 0034 (five folds that keep each project whole, out-of-fold scores, function hit@10, the exact paired test):

1. **Long reports.** On the training bugs whose report is longer than 2,000 characters, a candidate must gain at least 2.0 points of hit@10 over A, with p < 0.05.
2. **No cost elsewhere.** On all 5,902 bugs together, its hit@10 must not be lower than A's, and in no language may it lose more than 1.0 point.
3. **Speed.** On the Modal GPU the site uses, the median time for a warm request with 50 functions and a 2,048-token report must be at most twice that of the same request with a 512-token report.

If both candidates pass, the one with the larger gain on long reports is chosen; if they are within 0.5 points of each other, A-read2048 is chosen, since it needs no new adapter. If neither passes, the site keeps A, and the result is recorded here as a negative one.

## What happens next

The chosen configuration is frozen in `results/website-rerank/gpu_config.json` before it runs on any fresh-2026 bug. It is then run once on the 580 full reports as `website-gpu-long`, reported in the paper as a post-hoc system, because the idea came from fresh-2026 results, and never in place of the pre-registered `website-gpu`. The confirmatory test is fresh-2026b, a set of bugs reported after this decision, sealed before any system runs on it.

## Amendment, 2026-11-06: the upgrade is reported in the current fresh-2026 study

Written before any candidate has been trained or scored. Instead of waiting for fresh-2026b, the chosen configuration runs once on fresh-2026's full reports, all 580 bugs and the 198-bug agent subset, as `website-gpu-v2`, and the paper reports it in its main tables as an upgrade of Allfather, compared with every system on the same bugs. The pre-registered `website-gpu` stays the primary Allfather system and is reported unchanged next to it. The paper states the upgrade's timeline in one place: the idea came from the interim fresh-2026 analysis (the reranker's gain shrinking on full reports); the candidate was chosen on training bugs by the rule above; its configuration was frozen; and it then ran once on fresh-2026. Its configuration is frozen in `results/website-rerank/gpu_config_v2.json`; `gpu_config.json`, the pre-registered one, is left as it is. If no candidate passes the rule, nothing new runs on fresh-2026, and the paper says so. fresh-2026b remains a later, confirmatory test.

## Outcome, 2026-11-06: neither candidate passes; the site keeps A

Scored on the training bugs' out-of-fold scores at the frozen depth and weights (`scripts/rerank_long.py`, `results/website-rerank/long_reports.json`), function hit@10 against candidate A:

| Candidate | Reports over 2,000 characters | All 5,902 bugs | Per language |
|---|---|---|---|
| A-read2048 | +0.6 points (24 wins, 16 losses, p = 0.27) | +0.1 (p = 0.22) | −0.2 to +0.8 |
| L | +1.3 points (34 wins, 16 losses, p = 0.015) | +0.3 (p = 0.19) | −0.8 (Rust) to +1.4 |

L's gain on long reports is real and significant, but smaller than the 2.0 points the rule asks for, and A-read2048's is within noise. Neither passes, so by the rule the site keeps candidate A, the speed test is not needed, nothing new runs on fresh-2026, and the paper reports this as a negative result: reading more of a long report helps the reranker by about a point on training bugs, not enough to explain the gap between shortened and full reports on fresh-2026. That gap may lie elsewhere, for example in the browser ranker, which the reranker can only reorder.
