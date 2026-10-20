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

## Amendment, 2026-10-20, before any evaluation: the rankers' feature fingerprint

The first attempt to run the holdout stopped before scoring anything: the rankers refused to load because the feature code's fingerprint no longer matched the one recorded when they were trained. Nothing was scored or logged, and the holdout allowance is unchanged. The guard had loaded the issue text into memory when the error occurred; it was not printed or written anywhere.

The fingerprint is a hash of the feature modules' source text. It changed twice after training: on 2026-10-15, when the mention parser learned JavaScript, Java, Go and Rust stack traces behind an option that is off for Python issues, and on 2026-10-18, with the rename. Three of the four feature modules are otherwise byte-identical to the trained versions. For the fourth, the mention parser, [scripts/verify_mention_parity.py](../../scripts/verify_mention_parity.py) runs the trained version and the current one on every Python bug report in SWE-bench Lite, the full SWE-bench test set, Verified and SWE-rebench (7,168 reports), and on the 13,865 file paths in the ground truth outside the holdout. Every parsed field and every path comparison is identical ([results/fingerprint/mention_parity.json](../../results/fingerprint/mention_parity.json)).

So every feature the rankers see on a Python issue is unchanged. The four rankers' recorded fingerprints are updated to the current one, with the old value and the reason kept beside them. The ranker files themselves, and the hashes frozen above, do not change. The published rows of `ltr-ce-notests` become reproducible at the current commit again.

## Outcome, 2026-10-20

The four runs ran once each on PACE (an L40S, job of 2026-10-20, from commit `462edec`), as declared. Every declared metric with its interval is in [results/frozen/report.json](../../results/frozen/report.json), recomputed from the per-issue rankings by [scripts/frozen_report.py](../../scripts/frozen_report.py), which also checks them against each result file's own summary.

| allfather-fast, frozen | Bugs | hit@1 | hit@5 | hit@10 | recall@10 | all@10 | MRR |
|---|---|---|---|---|---|---|---|
| **Sealed holdout, function** | 311 | 51.4% | 71.1% | **79.7%** [74.9, 83.9] | 0.623 | 47.3% | 0.602 |
| **Sealed holdout, file** | 321 | 67.0% | **90.3%** [86.9, 93.5] | 94.7% | 0.883 | 81.0% | 0.771 |
| SWE-bench Lite, function | 291 | 43.3% | 72.2% | 78.4% [73.5, 82.8] | 0.761 | 73.5% | 0.543 |
| SWE-bench Lite, file | 300 | 68.3% | 88.7% [84.7, 92.0] | 93.0% | 0.930 | 93.0% | 0.777 |

- **The headline holds on new bugs in unfamiliar projects.** On bugs filed after every model in the cascade was published, from 184 projects nothing was trained or tuned on, function hit@10 is 79.7% and file hit@5 is 90.3%, as high as on Lite (78.4% and 88.7%).
- **Finding every location is harder on the holdout.** Its fixes change 3.0 functions on average, against 1.2 on Lite, and 189 of its 311 have more than one. all@10 is 47.3% against 73.5%, and recall@10 0.62 against 0.76: the cascade finds one of the changed functions as often, but all of them less often.
- **The two sets are not a controlled comparison.** They differ in projects, in fix size and in date; nothing here separates those effects, and no paired test between them is possible.
- **Two things the result files record imperfectly.** Both holdout files show `git_dirty: true` because the guard appended its log line before the provenance was taken; the guard itself had checked the tree was clean before anything ran. Their model list names only the top-level `models/` files, not the `models/more-data/` rankers that were loaded; the retriever name, the frozen commit and ADR 0032's hashes identify them. Both are fixed for later runs, and the files are kept as written.
