# Fit-only candidate coverage controls

The CPU probe completed all 23 original fit issues across 12 projects. None of the
new controls adds coverage on multiple projects. Do not schedule a reranking sweep
or train a router from this result. Keep the original prefix reference.

## Protocol and verification

[The protocol](../data/research/coverage-probe-v1.json) was written before computing
these controls' outcomes, after the fit cases and their failures had been inspected.
This is exploratory development, not a preregistered confirmation experiment.
The capture reconstructs every original candidate unit from base-commit Git blobs,
checks its content key, and reconstructs BM25 with the original path-token recipe.
All 276 comparisons of saved full/title/code relative-score and log-rank features
are exactly equal: 23 cases × two pools × three fields × two features.

Four query fields use the full report, title, backtick code, and quoted strings.
Rank fusion and lexical name references are fixed baselines. The latter starts from
ten fused seeds, prefers same-file definitions and rejects fanout above eight;
comments and string literals can match. It is not a resolved call graph. Existing
chunker call extraction is Python-only, and the browser ranker does not use that graph.

At limits 50 and 200, injection retains the first half of the original read list,
replaces at most the second half with proposed rows outside that list, and fills
unused slots from the original order. A deterministic random injection is a control.
These are candidate-count limits, not equal token or compute budgets.

Generation never consumes target labels. A separate analyzer verifies the complete
capture, original split, source hashes and identity-audit provenance before joining
gold. All 52 fit targets have unique audited identities; none is removed. It rebuilds
action selection from recorded field/reference rankings, rather than independently
recomputing those rankings from source. Capture source hashes identify the exact
working-tree implementation even though the recorded Git HEAD predates the new script.

## Results

The numbers below count issues with at least one target among candidates to be read.
They are **not hit@10**, and increased coverage does not establish better localization.

| Control | Any target, limit 50 | Any target, limit 200 |
|---|---:|---:|
| Original base | 19/23 | 19/23 |
| Original wide | 19/23 | 20/23 |
| Full-report BM25 | 18/23 | 20/23 |
| Field rank fusion | 18/23 | 19/23 |
| Inject rank fusion | 19/23 | 19/23 |
| Inject lexical references | 19/23 | 20/23 |
| Inject random rows | 19/23 | 19/23 |

At 200, all three increases recover the same issue, `supabase/supabase#49940`.
It was already covered by the original wide-200 condition, whose reranker still
missed it. No new issue is covered by any 50-candidate control. Full BM25 and field
fusion lose Zed issue PR #62785 at 50. Each injection also loses one target on
archify PR #515 while retaining another, illustrating why any-target coverage alone
conceals regressions. The full analysis retains all-target coverage, target recall,
per-issue additions/losses and every tested condition.

The frozen gate required newly covered issues in at least two projects with no lost
covered issues at the matching limit. Every condition fails that necessary gate.
This does not prove retrieval expansion cannot help; it rejects prioritizing these
particular controls for a new GPU sweep. The CPU capture took 101.67 seconds summed
over cases on this workstation, excluding input loading and analysis. This is not a
deployment or PACE timing claim. No downloads or inference calls were made.

Artifacts: [table](../results/research/corrections/coverage-analysis-v1/table.txt),
[analysis and provenance](../results/research/corrections/coverage-analysis-v1/analysis.json),
[all scored rows](../results/research/corrections/coverage-analysis-v1/rows.jsonl).
Fifteen coverage tests pass. After the report-audit additions, the full repository
suite passes all 268 tests. Ruff and whitespace checks also pass.

## Prior-work boundary

Targeted primary-source checks on 2026-11-15 further narrow the possible contribution:

| Source | Consequence |
|---|---|
| [CuraLoc, v1](https://arxiv.org/html/2610.31809v1), §§3–4 | Selects starting symbols and structural retrieval actions, then ranks retrieved source. Its controlled expansion study adds missing reference locations, and it distinguishes coverage from final recovery. Planned structural inspection and that diagnostic separation are already close prior art. Its Func@k requires **all** reference edit symbols among distinct predictions, so its published rates are not comparable to our any-hit@k. |
| [Retrieval-Oriented Code Representations, v1](https://arxiv.org/html/2607.11046v1), §3 | Compares source, paths and generated representations, including hypothetical bug reports, with multiple retrievers and fusion/reranking. A representation change alone needs differentiation. |
| [LocAgent, ACL 2025](https://aclanthology.org/2025.acl-long.426/) | Graph-guided repository exploration is established. Lexical references here are a lightweight control, not a reproduction of its agent. |
| [QREX, SANER 2021](https://ojcchar.github.io/publications/17-saner21-qrex) | Query reduction combined with expansion for bug localization is established; field selection is not a new research claim. |

These checks do not establish an unoccupied research gap. The next step is the
[task/report-to-patch audit](research-task-audit-v1.md), with all fit cases retained.
Any pivot toward an evaluation study needs independent annotation and broader evidence;
these small negative experiments alone are not a finished research contribution.

## Reproduction

Use a new output directory for every capture/analysis. The existing parent replay,
verified historical audit and cached base Git blobs must be available locally.
No model cache is needed; lazy Git fetching is disabled.

```bash
python scripts/coverage_probe.py \
  --parent reports/pace-development-7019874/development-pilot-v1 \
  --out reports/coverage-probe-repeat
python scripts/analyze_coverage_probe.py \
  --bundle reports/coverage-probe-repeat \
  --parent reports/pace-development-7019874/development-pilot-v1 \
  --out results/research/corrections/coverage-analysis-repeat
```

Generated artifact hashes/timings change between runs; compare candidate orders and
scored rows rather than expecting the entire timed capture to be byte-identical.
