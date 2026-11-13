# Development replay protocol v1

This is a small exploratory action-diversity pilot on already exposed fresh data,
not a new confirmation set and not a learned routing result. The committed
[`development-pilot-v1.json`](../data/research/development-pilot-v1.json) contains
47 issue–PR rows across 24 projects: 23 fit rows and 24 validation rows, with two
fit and two validation projects per language. Selection uses seed 37 and metadata,
not model outcomes, gold symbols, parser flags or hint strata. Up to two underlying
issues per project are sampled; all PR rows for a selected issue stay together.
Two selected projects have only one eligible issue, and one selected issue has two
PR rows. Execution interleaves languages.

## Correctness prerequisite discovered during implementation

`SnapshotIndexer.unit_texts` previously cached chunks by qualified name. Two rows
with the same name could both receive the last declaration's text, despite having
different indexed content keys. It now retrieves the text matching each row's
stored content hash. An unmatched key fails rather than substituting another text.
`Site.rank` now retains ranked row indices, and the historical GPU runner consumes
those aligned indices instead of rebuilding an ID-to-last-row map.

This repairs future inference; saved outputs and their rescoring are unchanged.
Historical inference affected by duplicate names must be rerun to assess the impact.
The existing line-based chunker still cannot represent all minified declarations
faithfully. This fix does not supply occurrence-level gold or repair line ownership.
The replay preserves duplicate names, row numbers and content keys for diagnosis.

## Fixed actions and observations

Every selected issue executes all six actions:

| Pool | Local ranking | GPU reread depth |
|---|---|---|
| Existing candidate budgets | Exported semantic ranker, then existing MiniLM top-20 stage | None, 50, or 200 |
| Each candidate budget multiplied by four | Same local model recipe | None, 50, or 200 |

The expanded pool must contain the original pool. Existing feature values for shared
rows remain unchanged. The GPU actions use the existing multilingual candidate-A
adapter, fixed rank/CE blend weight 1.0, and 512 query / 256 document tokens. Weight
1.0 applies to every language to keep the experiment fixed; this is not an exact
reproduction of the historical language-specific GPU recipe. Depth 200 on the
original pool controls for spending more rereading effort without wider retrieval.
Depths are capped by available candidates. GPU action order is deterministically
shuffled per issue to expose execution order in the timing record.

The capture function accepts only a query, repository and base commit. Gold,
patches and label-derived hint strata are not provided. Each compressed trace keeps:

- Complete indexed IDs, row numbers, content keys and source-file Git blob IDs.
- Base/wide candidate rows, feature matrices and semantic rankings.
- MiniLM-selected rows, local rankings, GPU-read rows and raw CE scores.
- Shared snapshot/signals time, local-stage time, incremental GPU time and computed
  token counts, plus actual execution order and job ID.

These support a later scoring join that separates targets outside the indexed
universe, outside the candidate pool, outside the GPU-read prefix, and poorly ranked.
Gold identity ambiguities must remain explicit under the inventory scorer's policies.
No controller is fitted and no latency or cost superiority is claimed from this replay.
Sequential cache reuse, Git preparation and model staging require separate accounting;
the records are Python execution times, not browser performance.

## Weights, provenance and resumption

Only locally cached weights are used. Revisions are pinned to the locally tested
snapshots for Potion, MiniLM and Qwen3-Reranker-0.6B in `development_replay.py`.
There is no fallback to an unpinned revision and no automatic weight download.
The PACE job stages existing caches on node-local disk; `HF_STORE` selects the
existing shared cache location. Adapter weights must exist under
`models/ce_multi/A/foldall/` in the PACE checkout.

Each output namespace records model-file hashes, adapter/ranker hashes, all Python
package source hashes, parser/model library versions, device/driver information,
thread count, selected IDs and recipe. Completed traces are atomic gzip writes.
Resuming requires an identical manifest and validates prior trace checksums.
Failed issues remain listed and retryable. Never run two jobs against the same
output directory or shared analysis cache at once. Changing source, weights, limits
or hardware requires a new namespace; a smoke namespace is not silently promoted
to the full pilot.

## Validation and PACE handoff

The full Python suite passed (211 tests), including browser parity checks and
regressions for same-name source lookup, candidate expansion, project grouping,
row-preserving GPU scoring and all-six-action capture. A separate synthetic
three-unit integration check ran all six actions using the real cached models on
the local RTX 4050; it is not a benchmark result. Its
[record](../results/research/corrections/development-real-model-smoke-v1.json)
identifies the tested model revisions.

First run six issues (one per language) on one L40S. Two hours is an allocation
allowance, not an expected runtime:

```bash
cd ~/scratch/Odin
git pull --ff-only origin main
mkdir -p results/research/corrections/pace-logs
sbatch --account=coc --qos=coc-ice --partition=coc-gpu \
  --nodes=1 --ntasks=1 --gres=gpu:l40s:1 \
  --cpus-per-task=8 --mem=32G --time=02:00:00 \
  --job-name=allfather-development-smoke \
  --output=results/research/corrections/pace-logs/development-smoke-%j.log \
  --export=ALL,PILOT_LIMIT=6,PILOT_OUT=results/research/corrections/development-smoke-v1 \
  cluster/research/development-replay.sbatch
```

Return `development-smoke-v1/summary.json` and the job log first. Expected completion
is six traces with no failures. Preserve `manifest.json`, `index.json` and all gzip
traces. If pinned caches or weights are missing, send the log; do not substitute a
different model silently. After inspecting the smoke traces and timings, choose
full-pilot resources and scoring. No training sweep or paid API run is part of this job.
