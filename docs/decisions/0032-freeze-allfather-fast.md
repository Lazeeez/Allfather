# 0032: allfather-fast is frozen and spends its one holdout run

## Status

Accepted, 2026-10-20. Written before allfather-fast was evaluated on the sealed holdout, and before its one run on SWE-bench Lite as a frozen configuration.

## Context

The owner narrowed the project's goal on 2026-10-20: it is to be presented in job interviews, not published. The research track (allfather-max beyond its first lever, escalation, downstream resolution, further benchmarks) stops. One question still deserves a measured answer: does allfather-fast hold up on bugs filed after every one of its models was published, in projects it never saw? That is what the sealed holdout ([ADR 0013](0013-sealed-holdout.md)) was built for.

[ADR 0017](0017-holdout-freeze-and-contamination-set.md) allows the freeze once three conditions are met. This ADR records how each is met.

## Decision

### The freeze conditions

- **Deterministic ties** ([ADR 0016](0016-deterministic-ties.md)): done.
- **The SweRank reproduction, and any indexing change it motivates**: the reproduction is done ([docs/comparison.md](../comparison.md)). It located a gap of about nine points in how Allfather indexes and feeds a retriever. Closing it is an open research question, and is not pursued.
- **The cheap levers, each decided on validation**: more training data for the LambdaMART rankers is adopted ([ADR 0019](0019-more-ranker-training-data.md)), with the reranker's depth, weights and skip margin re-chosen by the `ce-tune` rule against those rankers. More training data for the reranker and the Action-ranker features are not pursued. Nothing else is open.

### The frozen configuration

`allfather-fast` is the retriever `ltr-ce-more-data-notests`:

| Part | What | Pinned by |
|---|---|---|
| Sparse retrieval | code-aware BM25, test files excluded | the frozen commit |
| Dense retrieval | `jinaai/jina-code-embeddings-0.5b`, published 2025-08-19 | revision `4db235132dafbe56a8b9c5f59b59795ecf58a4a7` |
| Fusion | `DEV_SELECTED_FUSION` | the frozen commit |
| Rankers | LambdaMART, `models/more-data/ltr_function.txt` and `ltr_file.txt` | sha256 `752840e5…2e68` and `35bb3bf7…a2a1` |
| Reranker | two LoRA adapters on `Qwen/Qwen3-Reranker-0.6B`, published 2025-05-29, with the recipe `models/more-data/reranker.json` (depth 20, function weight 2.0, file weight 2.0, skip margin 2.0) | adapters by `models/adapters.json` (revision `0117dc4f…0012`); base revision `e61197ed45024b0ed8a2d74b80b4d909f1255473`; recipe sha256 `1fbef4ee…9769` |

The newest model was published on 2025-08-19, before the holdout's cutoff (2025-09-01), so every holdout issue is eligible. `data/holdout/allowed.json` records the retriever, the commit it is frozen at and that date.

### What is run, once each

- **The sealed holdout**, at function level and at file level: `allfather eval --dataset holdout --unseal --config allfather-fast --retriever ltr-ce-more-data-notests`. The guard refuses a second run of either level.
- **SWE-bench Lite**, at function level and at file level: the frozen configuration's one run on Lite, for comparison with published systems and with the rows already reported.

### What is reported, declared now

For each of the four runs, every metric the evaluation writes is reported as it comes out: hit@k, recall@k and all@k at k = 1, 5 and 10, and MRR, with the number of issues. Each comes with a 95% bootstrap interval over issues. The headline is function hit@10 and file hit@5 on the holdout, stated next to the same metrics on Lite. A lower number on the holdout than on Lite is reported as such, and is not followed by any change to the configuration. No intermediate stage is reported: the guard writes only the final ranking. Each run is one line in [results/test-evals.log](../../results/test-evals.log).

## Consequences

- allfather-fast cannot change after this ADR without a new name and a new holdout entry, which ADR 0013 would first have to allow.
- The published rows of the original configuration (`ltr-ce-notests`, including the README's 79.4%) still reproduce: its rankers and recipe are untouched.
- allfather-max and allfather-escalation keep their holdout entries unused.
