# Fit failure audit and next controlled experiment

Updated 2026-11-14. This is exploratory development on exposed data, not confirmation
or an established novel method. The [47-row pilot](research-development-results-2026-11-14.md)
gave no incremental fit-set hit@10 rescues from the existing six-action menu.
We inspected the five persistent **fit** failures before training any router.
No validation-case source was used to design the following controls.

## Audit findings

The [machine-readable audit](../results/research/corrections/fit-evidence-v1.json)
profiles all 23 fit reports and reconstructs all 14 labeled units in the five failures.
Base Git blob IDs and retrieval text keys match PACE. Pinned tokenizer/model assets
are hash checked. Ten reports exceed Qwen's 512-token query prefix, 21 exceed
MiniLM's 256-token input, and 11 exceed Potion's 512-token input. These are different
tokenizers; their character cutoffs are not comparable token counts.

| Fit case | Observation from report and base source | Interpretation and limitation |
|---|---|---|
| QuantumNous/new-api#7761 | The phrase `pricing is disabled` starts at character 1555; CE sees through 974, MiniLM 352 and Potion 710. The title already mentions the pricing endpoint. The 114-token labeled function fits the document budget but is absent from both candidate pools. | Query visibility is suspect, but reranking existing pools cannot recover an absent candidate. A retrieval intervention would be needed. |
| Comfy-Org/ComfyUI#15922 | The short report requests SenseNova-U1.5 support. The merge adds implementation files and modifies existing integration points. All six base-snapshot targets are absent from both pools. | This is feature-extension localization. New-only symbols are outside the label/candidate space; retained labels identify changed existing code. This is not automatically an invalid example. |
| ultraworkers/claw-code#3332 | A broad issue requests many missing tools; this change introduces read selectors and edits existing file-read interfaces. The best target ranks 264 in base and 427 in wide, outside either CE read set. | The umbrella issue may underspecify this particular change. Four of five labeled units fit the document limit, so truncation alone is not an adequate explanation. |
| immich-app/immich#31079 | `configureExpress` has 590 Qwen tokens; the 256-token view ends at character 1088. `app.listen` starts at 2063 and `server.requestTimeout` at 2109. The patch adds socket error handling there. CE50 reads the target but ranks it 13. | Test document visibility with fixed candidates and weights. The patch identifies a diagnostic region, not an inference feature. |
| supabase/supabase#49940 | `MultipleCodeBlock` has 523 tokens; its view ends at character 1038. The existing `overflow-scroll` class starts at 1711 and is edited by the fix. The target enters wide CE200 at rank 177 and finishes at 66. | The broader pool exposes the target, but the document prefix hides the edited CSS. Test a window intervention rather than assuming it will help. |

Character positions are zero-based in the actual query/indexed text. Indexed text
includes the qualified-name prefix. Token offsets describe visible text, not what
the model understood. The Immich error term already appears in the visible report.
These observations **do not prove that truncation caused any failure**.

Three requested post-merge file patches were unavailable in local partial Git mirrors:
two ComfyUI paths and one claw-code path. The audit records these failures without
fetching or inferring their contents. All base target texts and changed-path lists
were available. Full local review material is in `reports/fit-evidence-reviewed-v1/`,
with checksums in the committed summary. Gold and merge information remain diagnostic
only; no labels were edited or dropped.

## Prior-work boundaries

This targeted novelty check is not a systematic literature review. Primary sources
already cover several tempting broad claims:

| Work | Relevant overlap | Consequence |
|---|---|---|
| [Reformulate, Retrieve, Localize](https://arxiv.org/html/2512.07022v1), 2025 preprint / 2026 workshop | Extracts and summarizes report information before agentic BM25 localization. | Query cleanup or identifier extraction alone is not new. |
| [BLAgent](https://arxiv.org/html/2605.17965v2), July 2026 version | Structural/behavioral query views, AST/path-aware chunks, bounded candidate inspection/reranking, and context-size experiments. | Bounded evidence inspection or a query-plus-reranking pipeline is insufficient differentiation. |
| [SweRank+](https://arxiv.org/html/2512.20482v1) | Multilingual retrieval/reranking and iterative search/aggregation. | Multilingual coverage and follow-up search are not new by themselves. |
| [SHERLOC](https://arxiv.org/html/2606.24820v2) | Structured agent localization and failure analysis, including seeing relevant code but selecting incorrectly. | A coverage-versus-selection taxonomy alone is insufficient. |
| [Adaptive Re-Ranking](https://arxiv.org/html/2606.25249v1), ICTIR 2026 | Utility-based routing among sparse, lightweight and heavier neural ranking. | A cheap-to-expensive router already has close prior art. |
| [RCL](https://arxiv.org/pdf/2609.11023), 2026 preprint | Structural coverage and novelty signals trigger retrieval or review for code generation, starting from an insertion point. | Retrieval-sufficiency gating has close prior art. Unknown-target localization differs in task setup, which does not by itself establish novelty. |
| [Intra-Document Cascading](https://ciir-publications.cs.umass.edu/pub/web/getpdf.php?id=1413), SIGIR 2021 | Cheap passage selection before expensive scoring, with positional and term-match controls. | Passage selection is not new; our window variants are diagnostic baselines. |

The immediate question is narrower: **does spending the same reranker input budget
on different evidence help this localization pipeline, and how does that interact
with the candidate read budget?** A useful result would justify a larger study;
it would not alone establish a new algorithm.

## Frozen fit-only experiment

The [protocol](../data/research/text-view-pilot-v1.json) fixes the 23 fit IDs, parent
manifest and every input trace hash before new model scoring. Runtime model inputs
and selectors use no gold or merge information.

- Same pinned Qwen 0.6B and existing adapter; no training.
- Existing base top 50 and wide top 200 read sets. Within each set, candidates and
  their read order are fixed; scores use the original blend.
- Query views: first 512 tokens; first 256 plus last 256.
- Document views: first 256; first 128 plus last 128; best lexical 256-token window;
  deterministic pseudo-random 256-token window.
- Contiguous windows advance 128 tokens and include the final full window. BM25
  selects within each unit's windows using existing identifier tokenization, k1=1.2,
  b=0.75, and earliest-window ties. It only sees the chosen query view. This lexical
  tokenizer is English/identifier oriented.
- Short texts are unchanged. All variants use exactly the same number of token
  positions per candidate. Explicit token slices avoid decode/retokenize changes;
  head/tail joins add no separator tokens.
- All 16 pool/query/document combinations run on every fit row in a seeded order.
  No validation scoring or per-case method selection.
- Exact selected token IDs, spans, hashes, scores, execution order and times are
  saved. Full-source tokenization/window selection are shared CPU preparation, not
  free work. Sequential GPU timings are not deployed-policy latency.

Primary exploratory outcome: strict-symbol hit@10 over **all 23 fit rows**. Report
every variant and rescues/harms against its pool's prefix baseline, plus MRR@10,
gold recall@10 and all-gold hit@10. Retain feature tasks, pool misses and regressions.
Do not select a winner using only the motivating examples. Multiple variants and
retrospective case inspection preclude a confirmatory claim.

Before interpreting outcomes, compare rerun prefix/prefix scores and rankings with
the original PACE trace. Discrepancies need diagnosis; completion is distinct from
baseline parity. Later claims need stronger passage-selection/full-context controls,
project-level validation and new confirmation data. A routing claim additionally
needs complementary actions and predictable benefit. One rescued fit example is
insufficient justification for a learned router.

This experiment cannot recover a target absent from both frozen read sets. It tests
one mechanism and does not purport to fix all five failures.

## Implementation and checks

`scripts/audit_fit_evidence.py` performs the offline diagnostic audit.
`scripts/text_views.py` implements deterministic controls.
`scripts/replay_text_views.py` verifies frozen inputs, reconstructs base-source units
by content key, and captures model outputs separately from scoring. Git lazy fetching
is disabled. The cross-encoder's explicit-token entry point uses the existing prompt,
cache implementation and enforced limits.

The full Python suite passes **236 tests**, including token-budget, prompt-parity,
same-name source-identity, missing-content-key and all-variant capture checks.
Offline preparation verifies all 23 cases without model forward passes. The
[preparation record](../results/research/corrections/text-view-preparation-v1.json)
preserves the manifest and trace-index hashes. GPU numerical parity remains pending.

## PACE submission and return

Run from the existing checkout. Downloads/caches are forced to compute-node `/tmp`
and cleaned at exit. Results stay in the project directory. One L40S, eight CPU
cores, 32 GB RAM and a two-hour walltime limit are requested; this is not a runtime
prediction.

```bash
cd ~/scratch/Odin
git pull --ff-only origin main
mkdir -p results/research/corrections/pace-logs
sbatch --account=coc --qos=coc-ice --partition=coc-gpu \
  --nodes=1 --ntasks=1 --gres=gpu:l40s:1 \
  --cpus-per-task=8 --mem=32G --time=02:00:00 \
  --job-name=allfather-fit-text-views \
  --output=results/research/corrections/pace-logs/fit-text-views-%j.log \
  cluster/research/text-views.sbatch
```

After completion:

```bash
cat results/research/corrections/fit-text-views-v1/summary.json
tar -czf results/research/corrections/fit-text-views-v1.tar.gz \
  -C results/research/corrections fit-text-views-v1
```

Transfer the archive into the local project's `reports/` directory and provide the
job log. We will verify traces and baseline parity before scoring. Output directories
must be new; preserve any failed run and use
`--export=ALL,VIEW_OUT=results/research/corrections/fit-text-views-v2` for a rerun.
