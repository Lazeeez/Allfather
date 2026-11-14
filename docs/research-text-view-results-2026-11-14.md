# Controlled text-view results and validation handoff

Updated 2026-11-14. PACE job **7035289**, commit `609f2fe`, completed all 23 fit
cases. Its transferred archive has been independently verified and scored. The
result is a **one-case fit improvement**, with no demonstrated novelty or validated
routing benefit. No labels were changed, cases removed, or new weights trained.

## Integrity and scope

- Archive: `reports/fit-text-views-7035289.tar.gz`, 5,675,761 bytes;
  SHA256 `b475d5bf445195752bcc37746a1b9f6914b498d5bebff03636c956b1b32c679b`.
- All 26 regular archive files and 23 compressed trace hashes verified. The archive
  is read directly without extraction; extra/missing members are rejected.
- All 46 recorded Python source hashes match the recorded Git commit.
- Every selected token ID, span and input hash matches the frozen pre-run local
  preparation. All 368 rankings were rebuilt from raw scores and the original blend.
- All **46 original prefix baselines** reproduce exactly: no score differences or
  ranking changes. Each variant preserves its pool's original token-position count.
- Cohort: 23 distinct underlying issues, 12 projects, 52 labeled targets. All labels
  are uniquely identified by the complete symbol audit; no gold-file parser flags.
  Strict-symbol and name-group results are identical. No validation cases are scored.

Machine-readable [analysis](../results/research/corrections/text-view-analysis-v1/analysis.json),
[per-case results](../results/research/corrections/text-view-analysis-v1/rows.jsonl),
and [complete table](../results/research/corrections/text-view-analysis-v1/table.txt)
retain input hashes, all outcomes, target ranks and limitations. The evaluator is
`scripts/analyze_text_views.py`. The full Python suite passes **248 tests**.

## Every frozen condition

Query prefix reads 512 tokens; query head/tail reads first/last 256. Document prefix
reads 256; head/tail reads first/last 128. Lexical and random controls select one
256-token window. Short texts are unchanged. Recall is mean per-issue gold recall;
all@10 counts issues with every labeled target in the first ten slots.

Rescues and harms are relative to the corresponding pool's prefix/prefix baseline.

| Pool | Query | Document | hit@10 | MRR@10 | Recall@10 | all@10 | Rescues / harms |
|---|---|---|---:|---:|---:|---:|---:|
| Base 50 | prefix | prefix | 18/23 | .5787 | .6908 | 14/23 | 0 / 0 |
| Base 50 | prefix | head/tail | 19/23 | .5791 | .7391 | 15/23 | 1 / 0 |
| Base 50 | prefix | lexical | 18/23 | .6214 | .6908 | 14/23 | 0 / 0 |
| Base 50 | prefix | random | 18/23 | .6066 | .6908 | 14/23 | 0 / 0 |
| Base 50 | head/tail | prefix | 19/23 | .5765 | .7681 | 16/23 | 1 / 0 |
| Base 50 | head/tail | head/tail | 19/23 | .5982 | .7681 | 16/23 | 1 / 0 |
| Base 50 | head/tail | lexical | 18/23 | .6156 | .7246 | 15/23 | 0 / 0 |
| Base 50 | head/tail | random | 19/23 | .6143 | .7319 | 14/23 | 1 / 0 |
| Wide 200 | prefix | prefix | 18/23 | .5417 | .6908 | 14/23 | 0 / 0 |
| Wide 200 | prefix | head/tail | 19/23 | .5630 | .7391 | 15/23 | 1 / 0 |
| Wide 200 | prefix | lexical | 17/23 | .5942 | .6473 | 13/23 | 0 / 1 |
| Wide 200 | prefix | random | 17/23 | .5957 | .6546 | 13/23 | 0 / 1 |
| Wide 200 | head/tail | prefix | 19/23 | .5721 | .7681 | 16/23 | 1 / 0 |
| Wide 200 | head/tail | head/tail | 19/23 | .5838 | .7464 | 15/23 | 1 / 0 |
| Wide 200 | head/tail | lexical | 17/23 | .5870 | .6812 | 14/23 | 0 / 1 |
| Wide 200 | head/tail | random | 18/23 | .5982 | .6884 | 13/23 | 1 / 1 |

Every hit@10 rescue is **immich-app/immich#31079**. The oracle union over all 16
conditions is also **19/23**, the same success set reached by several fixed controls.
This does not provide incremental hit@10 headroom for a router on the fit cohort.
One added hit is +4.35 percentage points. Its descriptive pointwise project-bootstrap
95% interval is [0, 13.04] points; this is neither simultaneous inference over 16
conditions nor confirmation after inspecting failures and selecting interventions.

Regressions are visible despite equal or improved MRR: wide lexical loses
`immich-app/immich#31348`; wide prefix-query/random-document loses `tt-a1i/archify#515`;
wide head/tail-query/random-document loses `Significant-Gravitas/AutoGPT#14008`.
The final condition rescues one case and harms another, hiding the exchange in its
unchanged aggregate hit count. Random selection uses only one frozen seed.

## What the two motivating cases establish

For Immich's `configureExpress`, base-50 ranks are:

| Query / document | Target rank |
|---|---:|
| prefix / prefix | 13 |
| prefix / head-tail | 7 |
| head-tail / prefix | 5 |
| head-tail / head-tail | 5 |
| prefix / lexical | 38 |

Changing either the query or document view suffices to cross the hit@10 threshold
on this fit example. Document truncation is therefore not the only viable explanation
for its original miss. The intervention changes every candidate's visible text,
so a ranking change cannot be attributed solely to exposing a particular target line.

Supabase's target remains absent from base-50. In wide-200 it moves from rank 66 to
77 with head/tail documents, and to 56 with lexical windows; all remain misses.
The query is only 504 tokens, so its two query views are identical.

Post-hoc substitutions of the saved independent pair scores clarify the ranking
effects. These use gold to identify a target and are **diagnostic reconstructions,
not deployable policies or new model executions**. We recompute normalization and
the blend after each substitution, for every read labeled row and document control.

| Case / pool / document change | Target raw score | Rank, all scores changed | Rank, only target score changed | Rank, only other candidate scores changed |
|---|---:|---:|---:|---:|
| Immich / base / head-tail | -2.3125 → -2.0 | 13 → 7 | 9 | 13 |
| Supabase / wide / head-tail | -2.5 → -2.0 | 66 → 77 | 52 | 100 |
| Supabase / wide / lexical | -2.5 → -2.5 | 66 → 56 | 66 | 56 |

Supabase's head/tail view raises the target's raw relevance score but improves other
candidates enough to worsen its final rank. Its lexical rank gain occurs with no
target-score improvement. These observations support evaluating whole rankings,
not treating target visibility or target-score increases as sufficient success.

Four cases remain misses under every control: QuantumNous/new-api#7761,
Comfy-Org/ComfyUI#15922, ultraworkers/claw-code#3332, and supabase/supabase#49940.
The first three have no gold target in either frozen read set. A reranking-only
experiment cannot rescue them. The [fit audit](research-fit-evidence-2026-11-14.md)
documents report visibility and feature-extension interpretation issues.

## Cost interpretation

Script duration is 455.70 seconds, including 57.84 seconds of shared preparation,
198.07 seconds across sequential inference calls, and 199.79 seconds outside those
timers. That remainder is not assigned to a cause by the current instrumentation.
Each base-50 variant reports 252,808 computed nonpadding token positions; each
wide-200 variant reports 920,553. These counters are not GPU FLOPs or billable tokens.
Base prefix/prefix has unusually high observed time relative to other base controls;
warm-up/order and unallocated overhead prevent a standalone speedup claim.

## Frozen next decision and PACE job

The [validation protocol](../data/research/text-view-validation-v1.json) now fixes
**base_head_tail_head_tail versus base_prefix_prefix** as the primary comparison.
This is explicitly a fit-selected candidate: it ties the best fit hit count and
query-only gold recall while giving higher MRR than query-only, with no extra
retrieval or learned selector. The other 14 conditions remain diagnostics and will
not replace the primary candidate based on validation outcomes.

Use the original separate validation projects: 24 PR rows, 23 underlying issues,
12 projects. The primary unit is the lexicographically first PR ID per normalized
repository/underlying issue; report all 24 PR rows as a sensitivity. This resolves
the known duplicate markitdown issue independently of outcomes. Earlier baseline
results on these projects were already exposed: this remains **development validation**,
not prospective confirmation. New text-view outcomes have not been inspected.

The [offline preparation record](../results/research/corrections/text-view-validation-preparation-v1.json)
covers all 24 rows without model forward passes. The source
reconstruction, token preparation and capture functions are unchanged from the fit
run; only protocol/split selection and invocation plumbing change. No novel-method
or routing claim is warranted by this small result. A positive validation result
would still need stronger baselines, a differentiated contribution and new confirmation
data. A disappointing result will be reported without tuning against validation.

```bash
cd ~/scratch/Odin
git pull --ff-only origin main
mkdir -p results/research/corrections/pace-logs
sbatch --account=coc --qos=coc-ice --partition=coc-gpu \
  --nodes=1 --ntasks=1 --gres=gpu:l40s:1 \
  --cpus-per-task=8 --mem=32G --time=02:00:00 \
  --job-name=allfather-validation-text-views \
  --output=results/research/corrections/pace-logs/validation-text-views-%j.log \
  --export=ALL,VIEW_PROTOCOL=data/research/text-view-validation-v1.json,VIEW_OUT=results/research/corrections/validation-text-views-v1 \
  cluster/research/text-views.sbatch
```

Model downloads remain exclusively in compute-node `/tmp`; outputs remain in the
project. The walltime request is a limit, not a completion estimate. After completion:

```bash
cat results/research/corrections/validation-text-views-v1/summary.json
tar -czf results/research/corrections/validation-text-views-v1.tar.gz \
  -C results/research/corrections validation-text-views-v1
```

Transfer the archive to local `reports/`, retaining the job log. Preserve any failed
output directory and use a new `VIEW_OUT` path for a rerun.

## Reproduce the completed fit analysis

```bash
.venv/bin/python scripts/analyze_text_views.py \
  --archive reports/fit-text-views-7035289.tar.gz \
  --parent reports/pace-development-7019874/development-pilot-v1 \
  --preparation reports/text-view-prepare-final-v1 \
  --historical-bundle reports/pace-7012506 \
  --out reports/text-view-analysis-reproduction
```

The output directory must not exist. The pre-run preparation archive files remain
local and are anchored by the committed preparation record's hashes; recreating them
from a later code version will not produce identical manifest bytes.
