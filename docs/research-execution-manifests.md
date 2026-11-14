# Future run execution manifests

`frontier.py run` and `fresh_website.py` now freeze an execution manifest before any
repository export, model loading or provider invocation. This repairs future execution;
it does not reconstruct an execution plan for historical runs.

Each manifest contains exact issue IDs, source repository/base/report hashes, selected
project counts, a fixed seed, limit, recipe and source hashes. Ordering is by SHA256 of
the compact JSON `[seed, id]` array, so partial runs are no longer alphabetical prefixes.
The limit selects membership from that order before execution. All records and failed
attempts carry the manifest hash. The existing `--errors-last` option may reorder attempts
within that fixed membership and is recorded in the recipe; completed partial runs can
still be biased by failures or interruption and must report their exact coverage.

Resuming requires identical inputs, recipe, selected membership and order. Duplicate or
foreign completed rows are rejected. Historical runs without a manifest require a new
`--tag`; they are not silently adopted. Frontier runs no longer automatically reuse old
agent-subset outputs, since those were produced under earlier code/recipes. A fully
completed run exits before loading models or performing a provider billing probe.

Website plans also hash the ranker, confidence model, GPU configuration and local adapter
files when applicable. Website inference now passes empty target sets to ranking and
executes the selected IDs without consulting gold labels. This removes an unnecessary
label-bearing input; it is not a claim that earlier ranking necessarily used gold features.
Agent prompts now describe the supplied pre-merge base commit, rather than claiming that
it is the snapshot from when the report was filed. New evaluation-log entries describe
the exposed data as exploratory.

The default execution seed is 37. Use `--plan-only` to prepare or verify a manifest without
export, inference, API calls or model downloads. Examples for a future, separately justified
experiment (not instructions to rerun exposed benchmarks now):

```bash
python scripts/frontier.py run --set fresh-full-agents --system codex-agent-astra \
  --tag new-recipe-v1 --execution-seed 37 --limit 6 --plan-only
python scripts/fresh_website.py --set fresh-full-agents \
  --tag new-recipe-v1 --execution-seed 37 --limit 6 --plan-only
```

The manifest is a sibling `*.execution.json` of the intended prediction file. Removing
`--plan-only` would invoke the configured runner and may incur costs; no such run was
launched for this change. PACE downloads, when a later experiment is approved and prepared,
must still be confined to compute-node temporary storage.

These manifests do not certify CLI/provider versions, foundation-model immutability,
every remote base-weight byte, hardware allocation, process isolation, repository lineage,
or prospective blinding. They are not a substitute for the pinned development replay
protocol. Future cost-sensitive studies still need per-request usage, actual hardware and
allocation/setup/retry boundaries. New method confirmation still requires fresh frozen
data, independent annotation where needed, and a differentiated hypothesis.

Verification: all 327 local tests pass. Offline entry-point tests confirm plan-only mode
invokes neither a provider nor its billing probe, and website inference receives empty
target sets, follows the frozen order and resumes without repeating completed cases.
Ruff and formatting checks pass. No real inference or new benchmark result was produced.
