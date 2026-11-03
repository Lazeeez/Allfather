# 0034: the GPU reranker for JavaScript, TypeScript, Go, Java and Rust

## Status

Proposed, 2026-11-03. Written before anything in it is measured.

## Context

The website searches six languages, but its GPU reranker re-reads results only for Python repositories ([ADR 0021](0021-website-server-reranker.md), amended 2026-11-02), because I trained and measured its two LoRA adapters on Python bugs only. For the other five languages the last step is the browser's small language model, which added nothing measurable on projects it never saw ([ADR 0026](0026-skip-browser-language-model.md)). On Python the GPU reranker added 2.6 points of function hit@10 in cross-validation and 2.7 on unseen projects. That gap between Python and everything else is the site's largest remaining limitation.

The website rankers already train on 2,728 bugs from 61 projects in the five languages (Multi-SWE-RL, [ADR 0025](0025-more-languages.md)). Those bugs are training data, so I can measure on them by cross-validation without touching a test set. SWE-bench Multilingual and SWE-PolyBench have already been scored 5 and 4 times, and fresh-2026 belongs to [ADR 0033](0033-frontier-comparison-protocol.md), so none of them decides anything here.

## Decision

Two steps, the second only if the first does not settle every language.

### Step 1: do the Python adapters already help?

- **Tasks:** `uv run python scripts/website_rerank.py tasks --multilang` writes, for every one of the 2,728 bugs, the website pipeline's out-of-fold top 100 (rankers cross-validated with whole projects as folds, as they ship) and the code text of the top 50.
- **Scores:** `uv run python scripts/allfather_max.py score --name zero-shot-multilang --tasks results/website-rerank/work/tasks_multilang.jsonl --adapter models/ce_adapter_v1 models/ce_adapter` scores them with the two shipped adapters, unchanged.
- **Evaluation:** `uv run python scripts/website_rerank.py evaluate --multilang --name zero-shot-multilang`, exactly as in ADR 0021: the depth and weight are chosen on one half of the projects and applied to the other, and the halves are pooled.
- **Rule, per language:** the GPU reranker is turned on for a language if, on that language's bugs, function hit@10 improves by at least 2.0 points and the exact paired test's p-value, Holm-adjusted across the five languages, is below 0.05. A language that fails stays as it is and goes to step 2.

### Step 2: a multilingual adapter, for the languages step 1 leaves out

- **Training:** on PACE, one more LoRA adapter on `Qwen/Qwen3-Reranker-0.6B` with the recipe of [ADR 0007](0007-fine-tuned-cross-encoder.md) (listwise loss, hard negatives from the website's out-of-fold rankings), on the Python and the five-language training bugs together.
- **Measurement:** five folds with whole projects held out; each fold's adapter scores only its held-out projects, and the same choose-on-one-half, apply-to-the-other evaluation runs on the pooled scores.
- **Rule:** the same as step 1, per language, against the website pipeline without a GPU. If the multilingual adapter also beats the current pair on Python by the same rule, it replaces them for Python too; otherwise Python keeps the current pair.

### What does not change

- [ADR 0033](0033-frontier-comparison-protocol.md)'s website system is the pipeline as sealed on 2026-11-03 (ranker sha256 starting `df8659ea`), which its runs score without the GPU. Changing the live site's GPU languages does not change those runs.
- `forServer` in `web/src/engine/server.ts` gains a language list taken from this ADR's outcome; nothing else in the site changes.

## Consequences

- If step 1 passes for some languages, they get the GPU reranker with no training and no PACE time.
- Every result file is written to `results/website-rerank/`, and this ADR gets an outcome section with the numbers, whichever way they go.
