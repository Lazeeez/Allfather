# Research status and codebase map

Updated 2026-11-14. Current scope: localization and selective escalation; no repair or
developer-productivity claim. See [ADR 0037](decisions/0037-research-corrections.md).

Latest step: the [fit audit and frozen text-view experiment](research-fit-evidence-2026-11-14.md)
are ready. All 23 fit cases pass offline source/token-view preparation; 236 Python
tests pass. GPU execution and numerical parity are pending. This tests visibility
under fixed token budgets, not a proven novel method. No router is trained: the
previous six-action menu supplied no incremental fit-set rescues.

## What has been inspected

The first structural pass reads and hashes all 1,444 tracked files at starting commit
`99e4cdf57e7bc99bffd303e93cc04b1d6ed46a84`. All 118 tracked Python files AST-parse; all
986 JSON and 97 JSONL files parse. Binary assets are hashed. The inventory contains
Python imports, top-level definitions and Markdown headings.

This is not a claim that every line has been manually audited. Detailed inspection so
far concentrates on parsing/indexing interfaces, gold extraction, experiment harnesses,
baseline import/export, scoring, statistics, costs, paper generation and their tests.
The browser and deployment code have received structural and selected entry-point review.
GPU training, full historical reconstruction and live service behavior are not certified.

## Codebase map

| Area | Role and important boundaries |
|---|---|
| `src/allfather/repos.py` | Bare Git mirrors, commit/tree lookup, blob prefetch and batch reads. Base snapshots determine the candidate universe. |
| `parsing/python_symbols.py`, `parsing/symbols.py` | Symbol extraction, language registry, qualified names, source/test exclusions. Names can collide for overloads; classes and other types are included. |
| `index/chunker.py`, `snapshot.py`, `store.py` | Retrieval units; content-addressed parsed blobs; lexical indexes and call graph; persistent cache fingerprints. Parser changes can change both labels and candidates. |
| `search/` | Code tokenization, BM25, static/dense embeddings, fusion, path features and graph expansion. `retriever.py` exposes the ranking interface and preparation boundary. |
| `rank/` | Browser features and learned rankers, mention evidence, history/past issues, confidence calibration, cross-encoder training/tuning. Training targets and runtime stage must be distinguished. |
| `eval/` | Dataset loading, diff-to-symbol labels, holdouts, external scoring protocols, metrics, run provenance and tuning. `resolution.py` is a draft independent resolver, not yet the active historical scorer. |
| `scripts/browser_ltr.py`, `live_eval.py` | Train browser rankers and replay the browser recipe in Python. `Site.rank` exposes the semantic stage used by confidence. Python execution is not browser timing. |
| `scripts/fresh_set.py`, `fresh_website.py`, `frontier.py`, `open_agent.py` | Mine/seal issue–PR snapshots; collect local and agent results; normalize and score predictions. These are the main fresh-study validity boundaries. |
| `scripts/swerank_*` | Shared-chunker BEIR export, retrieval, full-report query replacement and import. SweRankEmbed evaluates a component, not full SweRank. |
| `scripts/fresh_analysis.py`, `paper_tables.py`, `check_readme.py` | Statistics, gate evaluation, cost estimates and generated claims. The last script checks internal consistency, not scientific validity. |
| `scripts/more_data.py`, `multilang_data.py`, `ce_multilang.py`, `rerank_choice.py`, `allfather_max.py` | Training collections, multilingual adapters, selection and historical model experiments. Test outcomes must not enter new method selection. |
| Other `scripts/` | Baseline protocols, frozen reports, exports, holdouts, parity, latency and GitHub Action orchestration; all entry points are in the inventory. |
| `web/src/engine`, `worker` | TypeScript retrieval/ranking, WASM parsing, downloads, worker pool, semantic inference, IndexedDB caches and optional GPU calls. |
| `web/src/pages`, `components`, `lib` | User interface, benchmark displays, reports, navigation and sharing. Published fresh-study claims still require propagation of the final corrections. |
| `proxy`, `deploy`, `web/api`, `action.yml` | Hosting/relay boundaries, optional GPU service and Action configuration. Local code execution/privacy varies by configuration. |
| `data`, `models`, `results` | Gold/splits/manifests, frozen model recipes and retained runs. Treat original evidence as immutable. |
| `cluster`, `benchmarks`, `.github`, `tests`, `web/test` | Cluster jobs, performance experiments, CI and correctness/parity checks. Passing these does not validate labels or confirm a hypothesis. |
| `docs`, `PLAN.md` | Historical decisions, experimental notes and manuscript. This document is the current worklist; old ADR outcomes remain historical. |

## System configurations

| Configuration | Evidence that can legitimately describe it |
|---|---|
| Original research GPU cascade | BM25/Jina/LTR/Qwen experiments under their recorded recipe |
| Frozen `allfather-fast` | Its own frozen configuration and holdout outputs |
| Browser engine | Actual TypeScript/WASM behavior and measured browser performance |
| `website` / `website-gpu` fresh runs | Python `Site` replay, optionally with the recorded multilingual GPU recipe |
| Deployed browser + GPU | Actual deployed stage settings, including language-specific stage skipping |
| GitHub Action | The Action's lighter semantic configuration |

## Correction worklist

Status meanings: **implemented** means code/tests exist; **diagnostic** means a provisional
recomputation; **open** means no completion claim. Ordering follows validity dependencies.

| Priority | Finding / work | Status and acceptance criterion |
|---|---|---|
| P0 | Missing `.mjs/.cjs/.mts/.cts` in import | Implemented shared registry and tests for all 12 extensions. Eight separate corrected runs generated. |
| P0 | Original exported ID membership | Open: verify recovered IDs against original fresh corpora; round trips alone are insufficient. |
| P0 | Unequal prompt/grep source extensions | Implemented access fix. Open: identify and rerun affected inference with a new run identity. |
| P0 | Gold-dependent answer resolution | Draft resolver implemented/tested; 580/580 inventory integrity audit passed on PACE. 65 gold IDs ambiguous, zero missing. Versioned inventory rescoring prepared; PACE results and final identity policy pending. |
| P0 | Invalid predictions silently disappear | Versioned rescorer preserves invalid/ambiguous/duplicate slots and records resolution rates. Open: run and publish sensitivities; historical default scorer unchanged. |
| P0 | Null costs become zero; competing cost paths | Open: one per-record cost module shared by analysis and paper; explicit unknown/measured/estimated states. |
| P0 | Hardware and token accounting | Open: recorded GPU count/type; per-request tier rules; retries/cache/setup boundaries; no difference-of-medians GPU estimate. |
| P0 | Cascade cost uses unconditional mean | Open in paper generation: sum cheap + selected incremental agent costs on exactly the evaluated instances. |
| P0 | Supplied gate threshold mislabeled/evaluated indirectly | Implemented direct threshold evaluation and precision-sensitive regression. |
| P0 | Unsupported headline claims | Correction notice and corrected comparison available. Full manuscript, website and generated table replacement remains open until evaluator/cost freeze. |
| P1 | Paired uncertainty ignores project dependence | Diagnostic paired project intervals in import audit. Open: integrate all metrics/file families, macro-project estimates and cluster-aware test sensitivity. |
| P1 | P-values rounded before Holm | Implemented raw p-values through adjustment. Historical tables retained pending regeneration. |
| P1 | Partial runs use sorted prefixes | Open: save seeded execution manifests for new runs; show exact IDs and project/language coverage for every partial comparison. Audit now exposes comparison IDs. |
| P1 | Duplicate issue with two PRs | Open: issue–PR unit definition, split grouping and deterministic issue-deduplicated sensitivity. Never silently drop an original row. |
| P1 | Pre-merge parent described as report-time snapshot | Open: operational wording, merge/parent provenance and multi-commit/rebase checks. |
| P1 | Symbol granularity / overloaded IDs | Open: version labels, quantify classes/types/overloads; draft resolver marks duplicate inventory IDs ambiguous. |
| P1 | Incomplete gold extraction and GraphQL error handling | Open: retain `GoldEntry.errors`, validate response shape/errors, patch/report hashes and extraction coverage in future mining. |
| P1 | Diff labels are not necessarily causal | Open: blind stratified label audit, including added-only changes, renames, incidental edits and alternate valid locations. |
| P1 | 50-row human check unfilled | Open: qualified human annotation; no fabricated answers or agreement. Retrospective gold-derived hints cannot be gate features. |
| P1 | Confidence predicts the wrong stage/event | Open: development-only target definitions for final success and incremental action benefit, project-grouped calibration. |
| P1 | Failed original RQ3 conjunction | Open manuscript correction: report escalation/cost/quality criteria together and the negative outcome, not a replacement success criterion. |
| P1 | Missing cheap/full/specialized comparators | Open: mention heuristic, BM25/static/LTR ablations; full compatible research pipeline and a specialized agent. |
| P1 | Incomplete routing controls | Exploratory action-overlap audit implemented. Open: confidence/margin/random, learned-benefit and failure-aware policies under matched actual budgets. |
| P1 | Python latency attributed to browser | Open: real cold-download/index/warm-query/GPU timings, median/p95, hardware/cache/version/size boundaries. |
| P1 | Absolute contamination / memorization claims | Open: replace with dated exposure controls, exact-model cutoff evidence and limits; no causal conclusion from the ten-instance pilot. |
| P1 | Weak isolation and provenance | Open: effective model IDs/settings, CLI versions, full permitted traces, archive hashes, enforced network/tool policy and failed-attempt logs. |
| P1 | Chronology / artifacts / stale docs | Open: history verification, ranker-count alignment, AI disclosure, actual anonymous artifact, current venue rules and bibliography checks. |
| P1 | Dataset/model attribution and distribution | Open: fresh-data attribution and source/model license review; no new distribution claim. |
| P2 | Confirmation and sample size | Open: clustered power/noninferiority planning, prospectively frozen new projects/time window. Current exposed fresh runs are exploratory for new methods. |
| P2 | Repair and productivity | Outside selected initial scope; requires separate executable or human study before making those claims. |

## Verification and artifacts

Development replay v1 is now implemented; see the [protocol and PACE command](development-replay.md).
It freezes 47 exploratory rows from 24 projects and records complete candidate pools
and six fixed actions without gold inputs. Implementation exposed two linked source
identity bugs: name-keyed text caching and the GPU ID-to-last-row lookup. Both are
fixed for future inference with content keys and retained row indices. Saved results
remain historical; this repair requires new inference to measure its effect.
All 211 Python tests passed, and the six actions passed a synthetic integration check
with the real cached models on the local GPU. PACE smoke job 7017410 stopped before
inference because assets were missing. The login-node checker verifies only the
transferred adapter. Per the author's storage constraint, the batch job downloads
pinned base weights into compute-node temporary storage, verifies file hashes,
runs inference offline and cleans up that temporary directory on exit. The
Git-ignored adapter was successfully transferred and verified in job 7017731.
That job downloaded and verified all base weights in `/tmp`, then failed before
inference because offline snapshot lookup demanded intentionally excluded repository
files. The loader now uses the same file filter as the downloader. Eleven targeted
tests and a real-model offline check from an isolated filtered cache passed; a
successful PACE replay was pending at that point. The author subsequently supplied
job 7018060's summary and log: all six smoke issues completed without failures,
251.22 seconds inside the replay script and 303 seconds Slurm walltime. All six
wide pools are larger. The [reported record](../results/research/corrections/pace-development-smoke-7018060.json)
preserves counts and trace hashes; full trace transfer/independent validation is
pending. A long-token warning occurs before the cross-encoder's explicit token
slicing and does not itself establish an oversized model input. The saved-trace
validator checks hashes, rows, pool inclusion, shared features and stage rankings;
13 targeted validator/replay tests passed. The 47-row run is gated on its success.
The author subsequently supplied a successful validator report (6/6, no failures,
manifest hash `8f0f6ce4e77e429be44f2988bf3225b6311e32d8c5bf01fcfd3f4337d19e1723`)
and submission confirmation for full-pilot job 7019874. The
[saved validation report](../results/research/corrections/pace-development-validation-7018060.json)
matches the earlier summary and all six pool/universe counts. Original trace
transfer and independent local validation/scoring remain pending. First-action
latencies and sequential cache reuse preclude treating these timings as controlled
standalone action costs; substantial script time is outside the saved trace timers.
Full-pilot job 7019874 subsequently reports 47/47 completed without failures,
797.93 seconds inside the script and 856 seconds Slurm walltime. All logged IDs
match the frozen 24-project plan and all wide pools are larger. The
[reported pilot record](../results/research/corrections/pace-development-pilot-7019874.json)
retains all printed trace hashes and counts. Complete trace validation, transfer,
gold joining and outcome analysis remain pending; no routing benefit is established.
Supabase #49940 grows from 165 to 14,359 candidates. The fourfold channel budgets
do not cap the final pool size because file expansion admits all units in selected
files. Keep this behavior visible in resource accounting and failure analysis.

The full transfer has now been received and independently verified locally:
6/6 smoke and 47/47 pilot traces pass; run source hashes match both recorded Git
commits, pinned assets agree, and all six repeated smoke issues have identical
features, CE scores and action rankings. The [development result report](research-development-results-2026-11-14.md)
records the gold join: all 118 pilot targets are audited unique and present in the
retrieval universe. Base hit@10 is 37/47; base CE50 reaches 39/47. Wider retrieval
adds 11 targets to pools but no additional hit@10 successes. The six-action oracle
also reaches 39/47, and both rescues are on validation projects (none in fit).
The current action menu therefore does not support training the proposed benefit
router. Inspect fit failures and action design before further model experiments;
no new routing or novelty claim is established. Twenty-seven relevant tests passed.

First full run after import/statistics changes: **183 Python tests passed**. Web baseline:
**97 tests passed**, TypeScript check passed. Ruff lint/format passed. Windows sandbox
permissions prevented pytest temp access and Vite configuration discovery initially;
the approved reruns passed. After adding the resolver, headroom diagnostic and inventory
builder, **23 targeted tests passed**, including a local Git snapshot inventory fixture.
Final Ruff checks passed; README consistency checked 568 numbers with zero mismatches.
That consistency check still verifies the explicitly archived historical table against
its historical inputs; it does not validate the superseded scientific claims.

The author reports full CPU inventory job 7008760 completed all 580 snapshots with
no failures in 1:59:59. Parser-error files occur in 400 snapshots and colliding IDs
in 512 (372 both; 40 neither). These repository-wide flags do not establish that
the corresponding gold targets are invalid. Full files have not yet been retrieved
locally. The CPU audit verifies hashes/identities/internal counts and measures
gold-specific unique, ambiguous, missing and parser-error-file coverage. It
preserves all labels and records integrity failures
against the full expected denominator. Ten relevant tests passed, including corrupt
hash, mismatched snapshot, unrelated parser flag and ambiguous gold fixtures.
See the [handoff](../cluster/research/README.md).

Follow-up audit job 7012218 passed saved-artifact integrity for all 580 snapshots.
Of 2,873 gold IDs, 2,808 are unique among extracted symbols, 65 ambiguous and none
missing. All gold IDs are unique in 557 issues; 23 have ambiguous targets. Eight
issues have no unique gold target. Thirteen gold IDs in ten issues occur in files
with parser errors, which may be unrelated to the target's own source range.
This does not certify causal gold labels or parser completeness against Git.

Versioned `rescore_inventories.py` now prepares strict-symbol and name-group
sensitivities, with all-observed and explicitly filtered cohort views. Resolution
uses only complete inventories, and invalid/duplicate slots retain rank positions.
It verifies the successful audit's input hashes and every snapshot before scoring;
corrected SweRank imports are required. Original/default metrics remain unchanged.
Fifteen targeted tests passed, including an end-to-end saved-inventory fixture,
stale-audit rejection, duplicate rows, ambiguous IDs, truncated MRR and slot retention.
PACE rescore job 7012506 produced a table supplied by the author. On 580 issues,
strict hit@10 is 0.7759 for website-gpu versus 0.7690 for SweRankEmbed-Large; on 198
agent issues it is 0.7576 for website-gpu, 0.7626 for website, and 0.8636 for Astra.
The corresponding name-group values are 0.7845/0.7793 (580 issues) and
0.7778/0.7828/0.8737 (198). These rounded marginal rates do not establish statistical
superiority, equivalence, predictable escalation benefit or a cost advantage.
The 20-row Sonnet run cannot be compared directly with 198-row totals. The complete
rescore/audit archive has now been received: 29 prediction input hashes and all 25
run summaries verified. Project-paired analysis finds GPU versus SweRankEmbed-Large
has 41 rescues and 37 harms, a +0.69-point strict hit@10 difference with a −2.69 to
+3.95-point project-bootstrap interval. Astra versus browser has 31 rescues and 11
harms on the 198-issue subset. These remain exploratory; no test in the explicitly
defined 60-test sensitivity family passes Holm-adjusted 0.05.

The pasted gold review begins inside a record; only three complete issue records
were recovered. Offline inspection of cached base blobs reproduces 15 Next.js
`e.constructor` occurrences at distinct byte columns on line 1, with no parser
errors. Thus path/name/line is insufficient to distinguish these declarations.
Traefik's parser errors overlap the gold method's lines; Zed's sole parser error is
far outside the gold method. This distinguishes collision and parser-coverage cases
without changing labels. Source hashes, parser versions, columns and error spans
are recorded. The complete review subsequently supplied contains 33 issues and
78 flagged targets; all 78 were inspected from cached sources with no failures,
and their occurrence-kind/line multisets agree with PACE. Of 13 targets in files
with parser errors, only Traefik's target overlaps an error by line range. The
other 12 still require semantic scrutiny. Fifty-three issues have over ten gold
IDs, making all@10 structurally unattainable on those rows. No gold was edited.
See the [verified evidence and limitations](research-evidence-2026-11-14.md).

PACE hardware probe job 7009034 successfully allocated an L40S (46,068 MiB VRAM,
driver 615.71.09) under `coc` / `coc-ice`. The supplied QoS output shows a 50-job
pending/running limit. GPU preflight job 7009198 passed model-library imports and
CUDA float32/float16/bfloat16 checks on the cluster at commit `4731578`. The supplied
report records PyTorch 2.14.0+cu130 and Transformers 5.17.0. Its 211-second Slurm
walltime is environment-check duration, not model inference latency. No model weights
were loaded and no research outcome was measured.

Offline split audit v1 finds all 10 historical pilot issues (five projects) in the
browser ranker's reconstructed declared training pool. None match available eligible
CE records. The 580 full-report fresh rows (74 projects) have no ID, snapshot or
case-normalized project overlap with either reference. This permits exploratory
unseen-project analysis relative to those references, not prospective confirmation:
fresh results were already exposed. Two PR rows share `microsoft/markitdown` issue
2340 and must stay in one split. Exact historical trained-row provenance, foundation
model exposure, renamed/forked repositories and semantic duplicates remain unaudited.
The script records input hashes, overlap IDs and missing reference availability;
its three synthetic overlap/grouping regression tests passed.

- [Structural inventory](../results/research/corrections/repository-inventory-2026-11-13.json)
- [Import correction audit](../results/research/corrections/import-v1/audit.json)
- [Exploratory joint outcomes](../results/research/corrections/headroom-v1.json)
- [Split and training-pool overlap audit](../results/research/corrections/split-audit-v1.json)
- [User-supplied PACE preflight result](../results/research/corrections/pace-preflight-7009198.json)
- [User-supplied completed inventory summary](../results/research/corrections/pace-inventories-7008760.json)
- [User-supplied inventory integrity/gold audit](../results/research/corrections/pace-inventory-audit-7012218.json)
- [User-supplied rescoring table](../results/research/corrections/pace-rescore-7012506-table.txt)
- [Partial gold review recovered from paste](../results/research/corrections/review-gold-partial-v1.json)
- [Offline source inspection of the three complete records](../results/research/corrections/gold-source-review-partial-v1.json)
- [Complete transferred PACE archive](../results/research/corrections/pace-rescore-7012506.tar.gz)
- [Paired project analysis](../results/research/corrections/inventory-paired-v1.json)
- [Complete flagged-target source inspection](../results/research/corrections/gold-source-review-v1.json)
- [Research direction and falsification plan](research-direction.md)

No new paid inference, GPU training, external publication or deployment has been performed.
