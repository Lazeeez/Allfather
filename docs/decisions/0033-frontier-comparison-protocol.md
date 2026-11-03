# 0033: Research protocol: a cheap localizer against the industry frontier

## Status

Proposed, 2026-11-02. Written before any experiment it describes. Spending money and PACE time needs the owner's approval (ground rule 11); the systems, test set, metrics, analysis and success criteria below are fixed now and may change only by an amendment dated before the test set is first scored.

## Context

[ADR 0032](0032-freeze-allfather-fast.md) froze allfather-fast and stopped the research track on 2026-10-20. On 2026-11-02 the owner reopened it as a research project for a Georgia Tech special problems course, aimed at testing Allfather against the industry frontier. A literature review and claim audit the same day found:

- Allfather matches 2025 LLM agents at function level on SWE-bench Lite (76.3% against LocAgent's 77.4%, all-locations Acc@10) at about $0.0002 per issue, and trails SweRank by about 12 points.
- Nobody has measured a sub-second, sub-cent learned ranker against the coding agents and frontier models that industry now uses for localization (Claude Code, Codex, Cursor-style agentic search), on the same fresh bugs, with cost.
- Whether localization helps agents is contested (Shi et al. 2026 against SHERLOC and Loc2Repair); the follow-up question those papers raise is when an expensive localizer is worth calling.
- SWE-bench Lite is unusable as a clean test here (92 logged evaluations, projects in training, a dense model trained on SWE-bench), and the sealed holdout is spent.

## Questions

- **RQ1, accuracy.** On fresh bugs no compared model could have seen, how far is each tier of the frontier above or below allfather-fast at function and file level?
- **RQ2, cost.** What does the accuracy-against-cost frontier look like, with cost per issue measured on one basis for every system?
- **RQ3, escalation.** Can a calibrated gate that sends only the bugs Allfather is unsure of to a frontier agent reach close to the agent's accuracy at a fraction of its cost?
- **RQ4, where the gap is.** How does the gap vary with whether the report names its location, the number of functions the fix changes, and the language?

## Systems

Exact model identifiers and versions are pinned in the run manifest on the day of the run, with the date, because closed models change.

| Tier | System | Runs on |
|---|---|---|
| T0 | allfather-fast, frozen ([ADR 0032](0032-freeze-allfather-fast.md)); the website pipeline, with the GPU reranker for Python | laptop, PACE |
| T1 | BM25 (code-aware); SweRankEmbed-Small and -Large; SweRankLLM rerankers over the same top 100 | PACE |
| T2 | Commercial retrieval APIs: two embedding models for code and one rerank API over Allfather's top 100 | paid API |
| T3 | One frontier LLM, one call per issue, given the issue and a repository map (paths and signatures), returning ten functions; a second variant also gets Allfather's top 50 | paid API |
| T4 | Frontier coding agents asked only to list the ten functions most likely to need the fix: Claude Code (headless) and one other vendor's agent, with web access off | paid API |

T2 to T4 are sized in the budget below; any can be dropped without changing the others.

## Test set: fresh-2026

- **Projects.** About 100 public projects (17 per language, the most-starred active ones with issues enabled that pass the exclusion) in Python, JavaScript, TypeScript, Go, Java and Rust, disjoint from every project in any training, development, test, holdout or live set, compared by GitHub repository ID so forks and renames are caught.
- **Bugs.** Issues created after the latest published training cutoff of every compared model, closed by one merged pull request, with the issue opened before the pull request. The answer key is the functions and files the merge diff changes, tests excluded, by the live-accuracy rule ([ADR 0023](0023-live-accuracy.md)). Issues whose fix changes no function are kept for file level only.
- **Size.** 600 bugs for T0 to T3. T4 runs on a random 200 of them, stratified by language. With about 20% of pairs discordant, 200 detects a 9-point difference and 600 about a 5-point one (paired, α = 0.05, power 0.8).
- **Text.** The issue's title and the first 1,500 characters of its body, without comments. GitHub serves only the current text, so an issue whose body was edited after its fix's pull request was opened (GraphQL `lastEditedAt`) is excluded.
- **Sealing.** The manifest (issue IDs, base commits, answer-key hashes) is committed and hashed before any system is run on it; `results/test-evals.log` records every run. Nobody reads the answer keys before the freeze.

## Tooling

`scripts/fresh_set.py` builds the set in four steps (exclusions, projects, mine, seal) and runs no localizer. It needs a GitHub token: mining 600 bugs takes thousands of API calls.

## Contamination controls

- Every repository is checked out at the base commit with no later history: no future refs, tags or reflog.
- Agents run with no network access except the model API, and with web search and fetch tools off.
- Each model's stated training cutoff is recorded. A model without one is reported with that caveat.
- The prompts, the repository-map format and the gate are developed on development data only (SWE-bench Verified minus Lite and the 608-issue unseen-project fold of [ADR 0020](0020-odin-max-larger-reranker.md)), and frozen before the test set is scored.

## Measurement

- **Outputs.** Every system returns a ranked list of at most ten functions. Agent and LLM answers (names, paths, line ranges) are mapped to Allfather's function IDs with Tree-sitter at the base commit; an answer that maps to nothing counts as a miss, and the unmapped rate is reported per system.
- **Accuracy.** Function hit@1, hit@5, hit@10, all@10, recall@10 and MRR; file hit@1 and hit@5.
- **Cost.** Dollars per issue at list prices on the run date: tokens for API systems, GPU-seconds at a public rental price for GPU systems, including indexing a new repository, which is the realistic first-issue cost.
- **Latency.** Wall time per issue, with the hardware named.
- **Variance.** Agents and LLMs are run three times on a random 50 of the 200, to report run-to-run variance.

## Analysis

- **Tests.** Paired comparisons against allfather-fast: exact McNemar for hit@k and all@10, a paired randomization test for MRR and recall@10, Holm's correction across each table's family. Intervals: bootstrap resampling by project, the unit that is not exchangeable.
- **RQ2.** The Pareto frontier of accuracy against cost.
- **RQ3.** The gate is the confidence model of [ADR 0029](0029-confidence.md), recalibrated on development data. Its threshold is chosen on development data to meet a stated accuracy; the test reports the realised accuracy, the share escalated and the cost, plus a random-escalation baseline at the same share. Hypothesis, fixed now: escalating at most 40% of bugs gets within 3 points of the agent's function hit@10 at under 30% of its cost. The result is reported whether or not it holds.
- **RQ4.** Results split by hint stratum (the issue names a fixed function, names a fixed file, has a stack trace through the fix, or none), parser-defined and checked by hand on 50 bugs; by number of changed functions; and by language.

## Before the test set: three development experiments

None touches a test set. Each is reported whatever it shows.

1. **E1, how optimistic issue-grouped cross-validation is.** Re-run ADR 0006's ranker cross-validation on the 1,941 SWE-bench training issues with folds grouped by project, and compare with the issue-grouped numbers.
2. **E2, how much the dense model's SWE-bench training matters.** On the 608-issue unseen-project fold, compare hybrid retrieval using jina-code-embeddings with the same pipeline using an embedding model not trained on SWE-bench.
3. **E3, hint strata on existing results.** Descriptive only: SWE-bench Lite results of every stored system, split by hint stratum.

## Budget, for approval

Estimates, to be confirmed against list prices before anything is spent:

- **T2.** Embedding about 100 repositories once, then only changed functions: on the order of a few hundred million tokens across both models. Reranking: 600 calls.
- **T3.** About 30,000 to 60,000 input tokens per issue, so 18 to 36 million for 600 issues, per variant.
- **T4.** Published frontier-agent localization costs are $0.5 to $1.7 per issue ([docs/cost.md](../cost.md)); 200 issues for two agents plus the variance runs is roughly 500 agent runs.
- **PACE.** SweRank's 7B and 32B rerankers on 600 issues: a few GPU-hours.

The owner chooses which tiers to fund. The cheapest version that still answers RQ1 to RQ3 is T0, T1, T3 with one model, and T4 with one agent.

## Success, and what counts as a result

Every RQ has a publishable negative outcome: the frontier is far ahead even on cost-adjusted terms, or the gate cannot be calibrated across projects. The study succeeds if it reports RQ1 to RQ4 on fresh-2026 under this protocol, with every run logged.

## What this replaces

Nothing is retracted. Lite and the spent holdout remain as reported, with their caveats; fresh-2026 becomes the test set for every claim in this study.

## Amendment, 2026-11-02: subscriptions instead of paid APIs

The owner has Claude Pro (with Claude Opus 5.5) and a Gemini plan (with Gemini 3.1 Pro), so tiers T3 and T4 run through the vendors' own command-line tools instead of paid APIs: Claude Code 2.1.316 and Gemini CLI 0.66.0, signed in with those accounts. Scripting the vendors' web chat is not used. `scripts/frontier.py` runs them:

- **T4, agents:** Claude Code with only its Read, Grep and Glob tools; Gemini CLI in its read-only plan mode with web search, web fetch, shell and editing tools excluded. Each run records the tools it used, and a run that used a web tool is flagged and not scored.
- **T3, one call:** the same tools with every tool removed, given the bug report and the repository's list of source files.
- **Checkout:** the repository is exported at the base commit with `git archive`, so there is no history at all; the run's working directory is that export.
- **Billing:** API-key variables (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` and the like) are removed from each tool's environment, so a run can only use the subscription sign-in and never a pay-per-use key.
- **Cost:** subscriptions are not billed per run, so RQ2 uses the list-price cost each tool reports (Claude Code's `total_cost_usd`) or the token counts it reports priced at the vendor's list price on the run date, and says so.
- **Pace:** subscription limits spread the runs over days; every record carries its date and the model that answered.
- **T2** (commercial embedding and rerank APIs) is not covered by either plan and is dropped unless the owner funds it.

## Development results

- **E1** ([results/research/e1_grouped_cv.json](../../results/research/e1_grouped_cv.json)): with whole projects as folds, function hit@10 is 80.4% (five folds) and 80.5% (one project per fold) against 81.0% with issue folds; no difference is significant after Holm's correction, and file level does not move. Issue-grouped cross-validation is not materially optimistic here.
- **E3** ([results/research/e3_hint_strata.json](../../results/research/e3_hint_strata.json)): on SWE-bench Lite, when the report names a function the fix changes (98 of 291), every learned system finds one in its top 10 93 to 98% of the time; when it names nothing the fix touches (161), allfather-fast finds 71% and SweRankLLM-Large 84%. The frontier's lead is concentrated where the report gives no clue.

## Amendment, 2026-11-02: what Gemini can run

- **The owner's Google AI Plus plan cannot be used.** Gemini CLI stopped serving personal accounts on 2026-06-18 and sends them to Antigravity CLI. Whether Antigravity CLI may be driven by scripts on a consumer plan is unresolved on Google's own forum, and it documents no way to switch off web tools, so it is not used. AI Plus includes no Gemini API credits.
- **The free tier of the Gemini API is used instead,** through Gemini CLI with the owner's API key. `scripts/frontier.py` refuses to run Gemini unless the key is confirmed free-tier (Gemini 3.1 Pro must be refused under a free-tier quota), so no Gemini run can be billed.
- **Gemini 3.1 Pro is not on the free tier,** so the Gemini system is Gemini 3.8 Flash, the strongest model the free tier serves on 2026-11-02, and is reported as such, not as Google's frontier model.
- **The free tier allows 20 requests a day for Gemini 3.8 Flash.** An agent run on one development issue used the whole day, so T4 cannot run on Gemini for free. Gemini runs as T3 only (one request per bug, no tools) on the 200-bug agent subsample, about ten days at the limit. Claude Code remains the T4 agent.
- **Antigravity CLI is not used** (checked 2026-11-02). Its FAQ says wrapping `agy` "inside third-party coding agents or applications... is not supported under consumer plans", and a Google staff answer on 2026-10-28 says that holds even when a coding agent such as Claude Code only prepares the tasks a personal script passes to `agy -p`. This study is built and run with Claude Code, so it falls under that rule. On AI Plus, Antigravity's only Gemini model is Gemini 3.8 Flash, the same model the free API tier serves.
- **Pilot, 10 SWE-bench Verified development issues** ([results/research/analysis_pilot.json](../../results/research/analysis_pilot.json)): Claude Opus 5.5 as an agent and in one call with only the list of file names both put a fixed function first for 8 and in the top 10 for 9; the website pipeline did so for 4 and 7. The one-call run never opened a file, so on public SWE-bench issues the model largely recalls the fix. This is the contamination fresh-2026 is built to remove, and the pilot numbers are not evidence about accuracy.

## Amendment, 2026-11-02: the cutoff date

fresh-2026 takes issues created on or after **2026-08-01**. The latest stated training cutoff among the compared models is Claude Opus 5.5's, June 2026; August leaves a margin for data that reaches training after a stated cutoff. Every other compared model is older.

## Amendment, 2026-11-03: how the 600 are drawn

Written after mining and before sealing; no system has run on any mined bug. Mining found 4,357 usable bugs (4,072 with a function to find) from 79 projects, but a few projects dominate: the largest in each language has 118 to 384 bugs, and one Java project holds 341 of 492. Several fast-growing, unfamiliar projects have hundreds of bugs in three months, which suggests issues or fixes written by bots or AI coding agents. Two rules replace "a random sample stratified by language":

- **Sampling:** only bugs with a function to find; up to 100 per language, drawn at random with seed 0, at most 12 from any one project. Under that cap Java has at most 83 eligible bugs (13 projects, mostly small), so it contributes what passes vetting and the set is about 580 bugs; the cap is kept because one project would otherwise be most of Java. The agent subsample is 200, stratified by language from the 600.
- **Vetting:** each drawn bug's issue and pull request are fetched again. A bug is excluded, and the next random one taken, if either was opened by a bot or a known AI coding-agent account, or if either says it was AI-written (for example "Generated with Claude Code" or "Co-Authored-By: Claude"). Every decision is kept in `data/fresh/vetted.jsonl`. AI-assisted work that carries no marker cannot be detected and remains a threat to validity: a fix written by an AI model may favour the models being tested.

## Amendment, 2026-11-03: the seal is redone once

The first seal (gold sha256 `683df0541fa70c42306d0fec64cbbcad41973d1823c5adc682b871210afca76a`) counted the 12-per-project cap separately within each language, so a project with bugs in two languages contributed up to 23. That broke the rule above. No system had run on it. `scripts/fresh_set.py` now counts the cap across languages, and the set is sealed again with the same seed; the vetting decisions already made are reused. The first seal's files are not kept.

Vetting: 745 drawn bugs were checked and 111 excluded, 70 of them because the fix's pull request said it was AI-written and the rest because a bot or agent account opened the issue or the pull request.

**Sealed, 2026-11-03:** 580 bugs (100 each in Go, JavaScript, Python, Rust and TypeScript; 80 in Java) from 74 projects, none contributing more than 12; issues opened 2026-08-01 to 2026-11-02; agent subsample of 198 (34 per language, 28 in Java). `data/fresh/gold.jsonl` sha256 `f8b6194fd8d378249b317efaab351bcbed04a9bcde1a11e2fc645c3f77fa1f0b`, recorded in `data/fresh/manifest.json`. From here, nothing about the systems, prompts or analysis may change except by a dated amendment, and every run is logged.

## Amendment, 2026-11-03: the escalation threshold

Fixed before any fresh-2026 result is read. RQ3's gate escalates a bug when the website pipeline's confidence (the model in `web/src/assets/confidence.json`, ADR 0029) is below **0.7899**: the 40th percentile of its predictions on the 747 development bugs of the 30 unseen projects (`results/confidence/unseen.json`), so that about 40% of bugs are escalated, the share named in the hypothesis. On those development bugs the website pipeline's function hit@10 is 59.9% below the threshold and 87.7% above it. The analysis is run with `--threshold 0.7899`; the full curve is reported as well.
