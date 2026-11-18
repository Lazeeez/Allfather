# Research status and codebase map

Updated 2026-11-18. Scope: issue localization and selective escalation on held-out projects.
Repair success and developer productivity are outside this phase. The scoring and baseline
decisions behind the current numbers are in [ADR 0037](decisions/0037-research-corrections.md);
the research plan and its decision rules are in [research-direction.md](research-direction.md).

## Where the study stands

fresh-2026 contains 580 issue–PR rows from 74 projects in six languages, reported between
August and November 2026. Its results have been examined, so I use them for exploratory
analysis; any new method will be confirmed on new bugs sealed before it runs.

Every prediction is resolved against the complete inventory of declarations in that bug's
base snapshot, without consulting the answer key. A name that matches several declarations
earns no strict credit; invalid and duplicate predictions keep their rank slots. Under this
scoring, strict hit@10 on all 580 bugs is 77.59% for the local pipeline with the GPU
reranker and 76.90% for SweRankEmbed-Large: a paired difference of +0.69 points with a
project-bootstrap interval of −2.69 to +3.95. Neither system is shown to be ahead. On the
198-bug agent subset, the gpt-6-astra agent reaches 86.36% against 76.26% for the browser
pipeline (+10.10 points, interval +4.41 to +15.87). No test in the 60-test sensitivity
family (two identity rules, three cohorts, two weightings) passes Holm-adjusted 0.05.
See the [paired analysis](research-evidence-2026-11-14.md).

### Experiments and outcomes

| Experiment | Outcome |
|---|---|
| [Development pilot](research-development-results-2026-11-14.md): six actions on 47 rows from 24 projects | Reranking the base top 50 reaches 39/47, the same as the best per-issue choice among all six actions. No router trained. |
| [Text views](research-text-view-results-2026-11-14.md): 16 query/document views on 23 fit issues | One fit issue gained (18 to 19 of 23). |
| [Text-view validation](research-text-view-validation-2026-11-15.md): the frozen candidate on 23 validation issues | 20/23 against 21/23 for the prefix baseline; prefix reranking kept. |
| [Coverage probe](research-coverage-probe-2026-11-15.md): new candidate-list controls on fit issues | No control adds coverage on more than one project; no GPU sweep needed. |
| [Long-report reranker](decisions/0036-reranker-reads-the-whole-report.md) | +1.3 points on long reports, below the 2-point rule; site keeps the original. |
| [Task audit](research-task-audit-results-2026-11-15.md): 23 fit cases, 52 reference targets | 3 targets judged incidental; no hit depends on them alone. Single-analyst, provisional. |
| [Baseline export membership](research-swerank-membership-results-7056950.md) (PACE 7056950) | Every saved SweRank prediction ID verified present in the retained exports. |

### Evaluation tooling built in this phase

- **Inventory-based scorer** (`eval/resolution.py`, `scripts/rescore_inventories.py`):
  complete declaration inventories for all 580 snapshots, built and integrity-audited on PACE
  (2,808 unique gold IDs, 65 ambiguous, none missing), with strict-symbol and name-group views.
- **Shared extension registry** for baseline imports and agent source access, covering
  `.mjs/.cjs/.mts/.cts`, with recovered identifiers kept in a separate namespace.
- **Per-record cost accounting** (`eval/costs.py`) with explicit recorded, estimated and
  unknown states; cascades charge the cheap run on every paired issue plus the selected agent
  runs only. Of 14,825 saved run rows, 297 have recorded amounts.
- **Execution manifests** (`eval/execution.py`): seeded, hash-ordered issue membership, frozen
  before any model loads, with strict resume validation.
- **Development replay** (`scripts/development_replay.py`): complete candidate universes,
  pools, features and per-stage rankings for six fixed actions, with no gold inputs.
- **Review tooling** (`scripts/review_task_audit.py`): packet and sheet identity checks, Stage A
  before Stage B, and agreement statistics between independent human reviewers.
- **Statistics:** raw p-values carried through Holm adjustment, project-clustered paired
  intervals, and direct evaluation of a supplied gate threshold.

## Next

1. **Independent human review.** Two reviewers complete the
   [23-case pilot packet](research-review-handoff.md), then the
   [95-issue broader sample](research-broader-audit-preparation-2026-11-15.md) across 50
   projects, selected without outcomes. No reviews have been returned yet.
2. **Freeze the outcome analysis** for the broader sample before joining any model results.
3. **Choose the contribution** from that evidence and close prior work (see
   [research-direction.md](research-direction.md)); a new method claim needs fresh frozen
   confirmation data and matched strong baselines.
4. **Manuscript:** the [working draft](paper/main.tex) reads all numbers from a hashed
   snapshot and compiles to a four-page PDF; venue rules, bibliography screening, an anonymous
   artifact and visual review remain to do.

## Open work

| Area | Remaining work |
|---|---|
| Inference reruns | Rerun inference affected by the source-access and duplicate-name fixes, under new run identities. |
| Identity | Occurrence-level identities for minified code; version labels for overloaded names. |
| Costs and timing | GPU count and type, per-request pricing tiers, retries and setup; real browser cold and warm timings. |
| Labels | Blind stratified label review, including added-only changes, renames and alternative valid locations. |
| Comparators | Mention heuristic, BM25/static/LTR ablations, the full research pipeline and a specialized agent. |
| Routing controls | Confidence, margin, random, learned-benefit and failure-aware policies under matched budgets. |
| Provenance | Effective model IDs, CLI versions, full traces and enforced tool policy for agent runs. |
| Confirmation | Clustered power planning and a prospectively frozen set of new projects and time window. |

## Codebase map

| Area | Role and important boundaries |
|---|---|
| `src/allfather/repos.py` | Bare Git mirrors, commit/tree lookup, blob prefetch and batch reads. Base snapshots determine the candidate universe. |
| `parsing/python_symbols.py`, `parsing/symbols.py` | Symbol extraction, language registry, qualified names, source/test exclusions. Names can collide for overloads; classes and other types are included. |
| `index/chunker.py`, `snapshot.py`, `store.py` | Retrieval units; content-addressed parsed blobs; lexical indexes and call graph; persistent cache fingerprints. Parser changes can change both labels and candidates. |
| `search/` | Code tokenization, BM25, static/dense embeddings, fusion, path features and graph expansion. `retriever.py` exposes the ranking interface and preparation boundary. |
| `rank/` | Browser features and learned rankers, mention evidence, history/past issues, confidence calibration, cross-encoder training/tuning. |
| `eval/` | Dataset loading, diff-to-symbol labels, holdouts, external scoring protocols, metrics, inventory resolution, costs, execution manifests and run provenance. |
| `scripts/browser_ltr.py`, `live_eval.py` | Train browser rankers and replay the browser recipe in Python. `Site.rank` exposes the semantic stage used by confidence. Python execution is not browser timing. |
| `scripts/fresh_set.py`, `fresh_website.py`, `frontier.py`, `open_agent.py` | Mine and seal issue–PR snapshots; collect local and agent results; normalize and score predictions. |
| `scripts/swerank_*`, `correct_swerank.py`, `verify_swerank_membership.py` | Shared-chunker BEIR export, retrieval, full-report queries, import and export-membership checks. SweRankEmbed evaluates a component, not full SweRank. |
| `scripts/rescore_inventories.py`, `analyze_*.py`, `audit_*.py` | Inventory scoring, paired project analysis, development and audit analyses. |
| `scripts/fresh_analysis.py`, `paper_tables.py`, `research_paper_snapshot.py`, `check_readme.py` | Statistics, gate evaluation, cost summaries, the manuscript's number snapshot and README consistency. |
| `scripts/more_data.py`, `multilang_data.py`, `ce_multilang.py`, `rerank_choice.py`, `allfather_max.py` | Training collections, multilingual adapters, selection and earlier model experiments. Test outcomes do not enter new method selection. |
| `web/src/engine`, `worker` | TypeScript retrieval/ranking, WASM parsing, downloads, worker pool, semantic inference, IndexedDB caches and optional GPU calls. |
| `web/src/pages`, `components`, `lib` | User interface, benchmark displays, reports, navigation and sharing. |
| `proxy`, `deploy`, `web/api`, `action.yml` | Hosting/relay boundaries, optional GPU service and Action configuration. |
| `data`, `models`, `results` | Gold/splits/manifests, frozen model recipes and retained runs. Original evidence is immutable. |
| `cluster`, `benchmarks`, `.github`, `tests`, `web/test` | Cluster jobs, performance experiments, CI and correctness/parity checks. |
| `docs` | Decision records, dated experiment reports and the manuscript. This document is the current worklist. |

## System configurations

| Configuration | Evidence that describes it |
|---|---|
| Research GPU cascade | BM25/Jina/LTR/Qwen experiments under their recorded recipe |
| Frozen `allfather-fast` | Its own frozen configuration and holdout outputs |
| Browser engine | Actual TypeScript/WASM behavior and measured browser performance |
| `website` / `website-gpu` fresh runs | Python `Site` replay, optionally with the recorded multilingual GPU recipe |
| Deployed browser + GPU | Actual deployed stage settings, including language-specific stage skipping |
| GitHub Action | The Action's lighter semantic configuration |

## Verification

All 341 Python tests pass, as do 97 web unit tests, 71 end-to-end tests and the TypeScript
check; the README consistency check verifies 422 numbers. PACE work so far: hardware probe
7009034 and GPU preflight 7009198 (L40S, PyTorch 2.14.0+cu130, Transformers 5.17.0);
inventory build 7008760 and audit 7012218 (580/580 snapshots); rescoring 7012506; development
smoke 7018060 and pilot 7019874; text views 7035289 and 7049176; SweRank export membership
7056950. Every transferred archive is hash-verified locally before analysis; model weights are
downloaded only into compute-node temporary storage and checked against pinned hashes.

## Result files

- [Structural inventory](../results/research/corrections/repository-inventory-2026-11-13.json)
- [Baseline import audit](../results/research/corrections/import-v1/audit.json)
- [Joint outcomes across systems](../results/research/corrections/headroom-v1.json)
- [Split and training-pool overlap audit](../results/research/corrections/split-audit-v1.json)
- [PACE preflight](../results/research/corrections/pace-preflight-7009198.json)
- [Inventory build summary](../results/research/corrections/pace-inventories-7008760.json)
- [Inventory integrity and gold audit](../results/research/corrections/pace-inventory-audit-7012218.json)
- [Rescoring table](../results/research/corrections/pace-rescore-7012506-table.txt) and [archive](../results/research/corrections/pace-rescore-7012506.tar.gz)
- [Paired project analysis](../results/research/corrections/inventory-paired-v1.json)
- [Flagged-target source inspection](../results/research/corrections/gold-source-review-v1.json)
- [Cost accounting audit](../results/research/corrections/cost-accounting-v1.json)
- [Development analysis](../results/research/corrections/development-analysis-v1/analysis.json)
