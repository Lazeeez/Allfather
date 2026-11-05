# 0033: Research protocol: a cheap localizer against the industry frontier

## Status

Proposed, 2026-11-02. Written before any experiment it describes. I spend money and PACE time only after approving it myself (ground rule 11); the systems, test set, metrics, analysis and success criteria below are fixed now and may change only by an amendment dated before the test set is first scored.

## Context

[ADR 0032](0032-freeze-allfather-fast.md) froze allfather-fast and stopped the research track on 2026-10-20. On 2026-11-02 I reopened it as my research project for a Georgia Tech special problems course, aimed at testing Allfather against the industry frontier. A literature review and claim audit the same day found:

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

## Budget, for my approval

Estimates, to be confirmed against list prices before anything is spent:

- **T2.** Embedding about 100 repositories once, then only changed functions: on the order of a few hundred million tokens across both models. Reranking: 600 calls.
- **T3.** About 30,000 to 60,000 input tokens per issue, so 18 to 36 million for 600 issues, per variant.
- **T4.** Published frontier-agent localization costs are $0.5 to $1.7 per issue ([docs/cost.md](../cost.md)); 200 issues for two agents plus the variance runs is roughly 500 agent runs.
- **PACE.** SweRank's 7B and 32B rerankers on 600 issues: a few GPU-hours.

I choose which tiers to fund. The cheapest version that still answers RQ1 to RQ3 is T0, T1, T3 with one model, and T4 with one agent.

## Success, and what counts as a result

Every RQ has a publishable negative outcome: the frontier is far ahead even on cost-adjusted terms, or the gate cannot be calibrated across projects. The study succeeds if it reports RQ1 to RQ4 on fresh-2026 under this protocol, with every run logged.

## What this replaces

Nothing is retracted. Lite and the spent holdout remain as reported, with their caveats; fresh-2026 becomes the test set for every claim in this study.

## Amendment, 2026-11-02: subscriptions instead of paid APIs

I have Claude Pro (with Claude Opus 5.5) and a Gemini plan, so tiers T3 and T4 run through the vendors' own command-line tools instead of paid APIs: Claude Code 2.1.316 and Gemini CLI 0.66.0, signed in with my accounts. Scripting the vendors' web chat is not used. `scripts/frontier.py` runs them:

- **T4, agents:** Claude Code with only its Read, Grep and Glob tools; Gemini CLI in its read-only plan mode with web search, web fetch, shell and editing tools excluded. Each run records the tools it used, and a run that used a web tool is flagged and not scored.
- **T3, one call:** the same tools with every tool removed, given the bug report and the repository's list of source files.
- **Checkout:** the repository is exported at the base commit with `git archive`, so there is no history at all; the run's working directory is that export.
- **Billing:** API-key variables (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` and the like) are removed from each tool's environment, so a run can only use the subscription sign-in and never a pay-per-use key.
- **Cost:** subscriptions are not billed per run, so RQ2 uses the list-price cost each tool reports (Claude Code's `total_cost_usd`) or the token counts it reports priced at the vendor's list price on the run date, and says so.
- **Pace:** subscription limits spread the runs over days; every record carries its date and the model that answered.
- **T2** (commercial embedding and rerank APIs) is not covered by either plan and I drop it unless I decide to fund it.

## Development results

- **E1** ([results/research/e1_grouped_cv.json](../../results/research/e1_grouped_cv.json)): with whole projects as folds, function hit@10 is 80.4% (five folds) and 80.5% (one project per fold) against 81.0% with issue folds; no difference is significant after Holm's correction, and file level does not move. Issue-grouped cross-validation is not materially optimistic here.
- **E3** ([results/research/e3_hint_strata.json](../../results/research/e3_hint_strata.json)): on SWE-bench Lite, when the report names a function the fix changes (98 of 291), every learned system finds one in its top 10 93 to 98% of the time; when it names nothing the fix touches (161), allfather-fast finds 71% and SweRankLLM-Large 84%. The frontier's lead is concentrated where the report gives no clue.

## Amendment, 2026-11-02: what Gemini can run

- **My Google AI Plus plan cannot be used.** Gemini CLI stopped serving personal accounts on 2026-06-18 and sends them to Antigravity CLI. Whether Antigravity CLI may be driven by scripts on a consumer plan is unresolved on Google's own forum, and it documents no way to switch off web tools, so it is not used. AI Plus includes no Gemini API credits.
- **The free tier of the Gemini API is used instead,** through Gemini CLI with my API key. `scripts/frontier.py` refuses to run Gemini unless the key is confirmed free-tier (Gemini 3.1 Pro must be refused under a free-tier quota), so no Gemini run can be billed.
- **Gemini 3.1 Pro is not on the free tier,** so the Gemini system is Gemini 3.8 Flash, the strongest model the free tier serves on 2026-11-02, and is reported as such, not as Google's frontier model.
- **The free tier allows 20 requests a day for Gemini 3.8 Flash.** An agent run on one development issue used the whole day, so T4 cannot run on Gemini for free. Gemini runs as T3 only (one request per bug, no tools) on the 200-bug agent subsample, about ten days at the limit. Claude Code remains the T4 agent.
- **Antigravity CLI is not used** (checked 2026-11-02). Its FAQ says wrapping `agy` "inside third-party coding agents or applications... is not supported under consumer plans", and a Google staff answer on 2026-10-28 says that holds even when a coding agent such as Claude Code only prepares the tasks a personal script passes to `agy -p`. I build and run this study with Claude Code, so it falls under that rule. On AI Plus, Antigravity's only Gemini model is Gemini 3.8 Flash, the same model the free API tier serves.
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

## Amendment, 2026-11-03: an open-weight model tier

Added before any system has run on fresh-2026 except the website pipeline. Two open-weight models run on PACE as agents and in one call, on the 198-bug agent subsample: **Qwen3-Coder-Next** (80B parameters, about 3B active per token, built for agentic coding) and **gpt-oss-120b** (Apache 2.0). They are the strongest open models whose weights fit the 300 GB scratch quota that offline compute nodes must load from; DeepSeek V4 Pro (about 1.6T parameters) and GLM-5.2 (about 753B) do not fit there. They answer the "free against free" question with models anyone can rerun, unlike rate-limited free API tiers.

- **Harness:** `scripts/open_agent.py` gives them the same three read-only abilities Claude Code gets (list files by glob, search contents, read a line range), confined to the bug's checkout, with at most 40 turns and temperature 0, through an OpenAI-compatible vLLM server on the same node. The prompts are the ones in `scripts/frontier.py`.
- **Cost:** GPU time on the node, priced at a public A100 rental rate on the run date.
- **Revisions** are pinned in the job's command line and recorded in each result's `requested_model` and in the log.

## Amendment, 2026-11-03: the hand check of the hint strata

`data/fresh/strata_check.csv` holds 50 bugs drawn from fresh-2026 with seed 33, each with its report, the functions the fix changed, and the stratum `scripts/fresh_analysis.py` assigns. A person fills in their own stratum without looking at any system's results; agreement is reported as Cohen's kappa. If kappa is below 0.6, RQ4 is reported as indicative only.

## Amendment, 2026-11-03: the website system gets the GPU reranker in every language

I stopped the website pipeline's run on fresh-2026 after 324 of 580 bugs, without scoring or reading any of it. Running the study's main Allfather system with the GPU reranker switched off for five of its six languages would measure a limitation I intend to fix, not the system I ship. So:

- **The website system is redefined** as the website pipeline with the GPU reranker in every language where [ADR 0034](0034-gpu-reranker-other-languages.md) adopts it, decided only on training bugs by cross-validation. Its configuration (rankers, adapters, depth, weight, languages) is frozen in an amendment here before it runs on fresh-2026.
- **The stopped run is kept, unread,** as `results/research/frontier/fresh_website.jsonl`: the browser pipeline without a GPU. I finish it later and report it as a separate, cheaper system, "website, browser only". The same system's run on the agent subsample (`fresh-agents_website.jsonl`) had already started when I stopped the first one; I let it finish, unread, for the same comparison.
- **Nothing else changes.** Every other system, the test set, the metrics, the threshold and the analysis are as already recorded.

## Amendment, 2026-11-03: Gemini one-call goes straight to the API

The Gemini CLI stopped working for this study: it now falls back to Google-account sign-in, which Google no longer offers for this client ("This client is no longer supported for Gemini Code Assist for individuals"). Its first two answers on fresh-agents came back empty because of it; I set those two records aside unread, and the bugs are run again.

One-call needs no tools, so `gemini-single` now sends the same prompt (`SINGLE`) to the Gemini API's `generateContent` with the same model, `gemini-3.8-flash`, and the same answer schema the Claude one-call run uses, passed as `responseJsonSchema`. Nothing else is added: no system prompt, default sampling. The CLI's own system prompt and tool declarations are gone, which makes the prompt the same text Claude one-call receives. Each record now keeps the API's exact token counts. It still runs on the free tier only, and nothing has been read or scored.

## Amendment, 2026-11-03: an OpenAI tier through Codex CLI

Written before any Codex run on fresh-2026. OpenAI's models join the comparison the same way Claude's do: through OpenAI's own command-line agent, Codex CLI (0.166.0), signed in with my ChatGPT account, so it costs nothing beyond the plan. No API key and no paid usage.

- **Model:** `gpt-6-luna`, the newest model Codex lists for my account (the others are the older `gpt-5.6-terra` and `gpt-5.6-luna`), at its default reasoning effort, `medium`, pinned on the command line. Web search is disabled, the sandbox is read-only, my own Codex configuration and rules files are ignored, and sessions are not saved.
- **codex-single** (tier T3): the same prompt as the other one-call systems (`SINGLE`), with Codex's shell tool turned off so it cannot open files, and the same answer schema passed as `--output-schema`. It runs on all 580 bugs.
- **codex-agent** (tier T4): the agent prompt (`PROMPT`), exploring the checkout through Codex's shell inside its read-only sandbox, on the 198-bug agent subsample. On Windows that sandbox blocks every command, and turning approvals off would run commands outside any sandbox, so codex-agent runs only under Linux (WSL), where the sandbox is enforced by the kernel. `frontier.py` refuses to start it on Windows.
- **Prompts Codex cannot take:** Codex refuses any input longer than 1,048,576 characters before the model sees it. 19 of the 580 one-call prompts (5 of the 198) are longer, because their repositories list that many source files. Those bugs are recorded as no answer, a miss, with the reason kept in the record; I do not shorten the file list for one system, because every one-call system must see the same prompt. Claude and Gemini take all 580.

Nothing else changes, and nothing has been read or scored.

## Amendment, 2026-11-03: OpenAI's frontier model, on ChatGPT Plus

Written before any run of the model it names. I bought one month of ChatGPT Plus (about 3,000 yen) so OpenAI is represented by its strongest model, not only its small one. Codex lists, for that account: `gpt-6-astra` ("Frontier intelligence for the most demanding work"), `gpt-6.1-sol` ("Latest workhorse model for coding and everyday work"), `gpt-6.1-terra`, `gpt-6-sol`, `gpt-6-luna` and older models.

- **The frontier model is `gpt-6-astra`**, the one OpenAI describes as its most capable, matching Claude Opus 5.5 as Anthropic's. It runs as `codex-single-astra` on all 580 bugs and as `codex-agent-astra` on the 198-bug agent subsample (under WSL, as recorded above), with every setting of the `gpt-6-luna` systems unchanged.
- **Reasoning effort is `medium` for every OpenAI system**, pinned on the command line: `gpt-6-luna`'s default and one step above `gpt-6-astra`'s default (`low`). I do not tune it; higher settings exist and are a limitation I report.
- **gpt-6-luna stays as a second, smaller OpenAI system** (`codex-single`, `codex-agent`), for the cost and accuracy comparison of RQ3.
- **Accounts:** the first 88 `codex-single` answers on fresh-agents came from my free ChatGPT account, until its sign-in was revoked; the rest of that run, and every other Codex run, uses the Plus account. The account changes usage limits, not the model, prompt or settings, so I keep those 88 answers, unread.
- **If usage runs out:** each run proceeds in the set's fixed order and stops at the plan's limit; if a run cannot finish before the month ends, I report it on the bugs it completed, a prefix of that fixed order, and say so. I do not switch models partway.

## Amendment, 2026-11-03: the hand-check sheet is made blind

Before anyone filled it in, I noticed the sheet showed the parser's stratum beside the empty answer column, which would anchor the person checking and inflate kappa, and that it listed only function names, so the "file" stratum could not be judged. The same 50 bugs are kept. `data/fresh/strata_check.csv` now shows each bug's report and its changed functions with their files, and nothing else; the parser's strata are in `data/fresh/strata_parser.csv`, to be opened only after every row is filled in. The definitions the person applies are the parser's, in words: **function** if the report names a function or method the fix changed; otherwise **file** if it names a file the fix changed; otherwise **trace** if it contains a stack trace; otherwise **none**.

## Amendment, 2026-11-03: the order the OpenAI runs use the plan's usage

Written before any Codex result has been read. ChatGPT Plus usage is limited per week, so the runs go in this order, and whatever does not fit in the month is reported on the prefix it completed, as already recorded: (1) `codex-agent-astra` and `codex-single-astra` on fresh-agents, side by side; (2) `codex-single` (gpt-6-luna) on fresh-agents, then `codex-agent` (gpt-6-luna) on fresh-agents; (3) `codex-single-astra` on all 580; (4) `codex-single` on all 580. The first weekly allowance ran out at 99 and 85 of the 198 for the two Astra runs; I bought a reset of the weekly limit, which changes nothing about the models or settings.

## Amendment, 2026-11-03: one answer per bug, and a repeatability check

Written before any one-call result has been read.

- **One answer per system per bug.** The 198 agent-subsample bugs are part of the 580, so a one-call system that has answered them on fresh-agents does not answer them again on the full set: `frontier.py` copies those answers into the full-set file, marked `reused_from`, and asks the model only the other 382. It refuses to start the full set until the subsample run is complete, so every reused answer is the first and only one. A model's answers are not deterministic, and a second answer would be another sample, not a better one; taking the first, fixed in advance, keeps each system's answer to a bug the same in every table.
- **Repeatability.** Because the answers are not deterministic, I measure how much that matters: after the runs above, if the plan's usage allows, `codex-single-astra` answers a second time on `fresh-repeat50`, 50 of the 198 drawn with seed 50, as the separate system `codex-single-astra-repeat`. I report how often function hit@10 changes between the two answers and the agreement between them. It is reported beside the main results and replaces nothing.

## Amendment, 2026-11-03: long paths on Windows, and the rest of the runs move to Linux

Found before any result was read. `frontier.py` exports each bug's checkout and, on Windows, leaves out files whose full path would pass Windows' 240-character limit, so a few deep Java and TypeScript paths never reached the systems that ran on Windows: they were missing from the one-call file list and from the Claude agent's checkout. I checked every Windows run against each bug's full file tree. Files were left out for 40 of the Claude agent's 198 bugs, 41 and 40 of the 198 for gpt-6-astra and gpt-6-luna one-call, 3 of Claude one-call's first 30, and 27 of the 69 new bugs of gpt-6-astra one-call's full-set run; **in none of them was a file the fix changed left out**, so every system could still see, or be shown, the file it needed. The Codex agents ran under Linux and saw every file.

- **The answers stand**, unread and unchanged: rerunning only some bugs would replace first answers with second ones.
- **Sensitivity check:** every comparison in the analysis is also reported without the bugs where any system's checkout left files out, so a reader can see whether the difference matters.
- **Every remaining run uses Linux (WSL)**, where nothing is left out: the rest of gpt-6-astra and gpt-6-luna one-call on the full set, the repeatability check, Gemini one-call, and the rest of Claude one-call. The answers already reused from fresh-agents stay as they are.

## Amendment, 2026-11-04: Gemini one-call on the paid tier

Written before any Gemini answer exists. The free tier's 20 requests a day would have taken ten days, and overloaded calls counted against it, so I prepaid the Gemini API instead. Everything else stays: `gemini-single` is `gemini-3.8-flash`, called directly with the same `SINGLE` prompt and answer schema, default settings, on the 198-bug agent subsample, under Linux so every file list is complete. The paid tier changes only usage limits and data use (Google does not train on paid-tier prompts), not the model.

- **Where it sits:** Flash is Google's fast, low-cost model, not its most capable one (Gemini 4 Argon, left out for cost). I report it in the same group as gpt-6-luna, as a smaller model, and say so wherever Gemini appears.
- **Spending cap:** the first 10 bugs run alone and I project the cost of the rest from Google's own token counts (input $0.75 and output, thinking included, $3.75 per million tokens); the run continues only if the projection for the 198 stays under $25. Nothing is read while doing this beyond the token counts.
- **The three requests sent before** on the free tier, which Google refused as overloaded, produced no answers, so every Gemini answer comes from this run.

## Amendment, 2026-11-04: the open models' exact versions and hardware

Written before either open model has answered anything. `gpt-oss-120b` runs at Hugging Face revision `b5c939de8f754692c1647ca79fbf85e8c1e70f8a`, on two A100s with vLLM's tensor parallelism. For Qwen3-Coder-Next I use Qwen's own FP8 release, `Qwen/Qwen3-Coder-Next-FP8`, pinned at submission to the revision Hugging Face reports that day: the full-precision weights are about 160 GB, more than one job may hold under my PACE allocation, while the FP8 weights, about 80 GB, fit four L40S cards, which run FP8 in hardware. FP8 is how this model is commonly served, and I report it as the FP8 version, not as the full-precision model. Each job runs at most four hours on four GPUs, within the per-job GPU-time limit, and is resubmitted until the run finishes; the run resumes where it stopped.

Qwen3-Coder-Next-FP8 was submitted on 2026-11-04 at Hugging Face revision `da6e2ed27304dd39abadd9c82ef50e8de67bdd4c`.

## Amendment, 2026-11-04: what the rest of the ChatGPT Plus month is used for

Written before either run below has started, and with no Codex result read. Every OpenAI run above is complete; the plan's remaining usage goes to two additions, in this order, each stopping at the plan's limit and reported on the prefix of the fixed order it completed:

1. **Agent repeatability.** `codex-agent` with `gpt-6-astra` answers a second time on `fresh-repeat50`, the same 50 bugs as the one-call repeat, as the separate system `codex-agent-astra-repeat`. Agents take many steps and are likely the least stable systems, so I report the same measures as for the one-call repeat. It replaces nothing.
2. **OpenAI's newest coding model.** `gpt-6.1-sol` ("Latest workhorse model for coding"), with every setting of the other Codex systems (reasoning effort `medium`, read-only sandbox, web search off, under Linux), as `codex-single-sol` and then `codex-agent-sol` on the 198-bug agent subsample. It is reported beside gpt-6-astra, which stays OpenAI's frontier system as recorded above, to show whether a newer model changes the comparison; it is not chosen between them after the fact.

## Amendment, 2026-11-04: Gemini calls that never return

Written before any Gemini answer has been read. On some bugs gemini-3.8-flash does not answer within the 20-minute limit of a call, three times in a row (`rust-lang/rust#161131` so far); the prompt is not the reason, since it answered prompts four times longer within minutes. I do not change the model's settings for these bugs. Instead, bugs that timed out are retried after every other bug, and a bug that times out on all three attempts in two separate passes is recorded as no answer, a miss, with the reason kept, as the agent runs already treat a call that times out.

## Amendment, 2026-11-04: the open models' context length, and agents that run out of room

Written before any open-model answer has been read. Each open model is served at its own maximum context length: 262,144 tokens for Qwen3-Coder-Next-FP8 and 131,072 for gpt-oss-120b, instead of the 65,536 my job script used by default, after the first Qwen run stopped when one agent's conversation outgrew 65,536. If a conversation still outgrows the model's context, or the agent uses all 40 turns without answering, the bug is recorded as no answer, a miss, with the reason kept, and is not retried; this is the same treatment as Codex's prompts that are too long. Bugs that failed for other reasons are retried as before.

## Amendment, 2026-11-05: the open-model agent gets an answer channel, and its first Qwen run is set aside

Found before any open-model answer was read, from the run's own records: 132 of Qwen3-Coder-Next-FP8's 198 agent bugs ended with no answer after all 40 turns, and the tools it called show why. It tried to hand in its answer by calling tools that do not exist (`JSON` 64 times, `JSON_output`, `JSON_OUTPUT`), which my harness refused, so it never finished. Claude Code and Codex both receive the answer schema as a structured output (`--json-schema`, `--output-schema`); my open-model harness gave the model no such channel, which is a defect of the harness, not a property of the model.

- **The harness now matches the others:** an `answer` tool carries the same schema; a call to any other unknown tool whose arguments hold a valid `functions` list is taken as the answer; and after the 40th turn one last request, without tools, asks for the final answer, as Claude Code's schema enforcement does when a session ends.
- **Qwen's agent run is redone on all 198 bugs** with the corrected harness, so every answer comes from one harness. The first run is kept, unread, in `results/research/frontier/superseded/` and is never scored. Its one-call run is unaffected (one-call has no tools) and stands; its 5 misses are prompts longer than the model's 262,144-token context, as recorded above.
- gpt-oss-120b has not run yet and uses the corrected harness from the start.

## Amendment, 2026-11-05: the hand-check sheet shows the exact sealed text

Before any row was filled in, I found the sheet cut each report at 1,500 characters of title and body together, while every system received the title and the first 1,500 characters of the body, as this protocol defines; 36 of the 50 rows showed up to about 130 characters less than the systems saw. The sheet's report column is now the sealed text itself, character for character. The person checking judges that text only, not the full issue on GitHub, because the strata describe what the systems were given.

## Amendment, 2026-11-05: a second condition with the full bug reports

Written before the full reports have been fetched, and with no fresh-2026 result read. Every system above received the title and the first 1,500 characters of each issue's body, as defined at the start; 427 of the 580 bodies are longer than that, so most reports reached the systems shortened. Whether the cut changes the results, or changes which system does best, is worth measuring rather than assuming, so the study gets a second condition.

- **fresh-full** is the same 580 bugs, base commits and answer keys; only the text changes, to the issue's title and its full body, still without comments. `scripts/fresh_set.py full` fetches each issue again and keeps a bug only if the full text begins with exactly the sealed text and the issue has not been edited since its fix's pull request opened, so every full report is the one the reporter wrote; any other bug is left out of this condition and counted. `fresh-full-agents` is the agent subsample within it.
- **Every system runs on it with exactly the settings it used on fresh-2026**, in the same order of priority, as plans and budgets allow; each run is reported on the prefix of the fixed order it completed, like every other run.
- **Analysis:** each system is compared with itself, shortened against full report, on the bugs both conditions cover, with the same paired tests; and the main comparisons are repeated on the full reports. The shortened-report condition stays the primary analysis, as pre-registered; the full-report condition is reported beside it, and neither is chosen after seeing which looks better.

## Amendment, 2026-11-05: a free-to-use comparison

Written before any fresh-2026 result has been read. Allfather is free, so besides the full table the analysis reports how it ranks among the systems a user can also use for free: Allfather in every variant, SweRank, the open-weight models (gpt-oss-120b, Qwen3-Coder-Next-FP8), gemini-3.8-flash (the model Google's free tier serves; I paid only to lift the daily limit) and gpt-6-luna (the model ChatGPT's free plan offers). Claude Opus 5.5, gpt-6-astra and gpt-6.1-sol are paid. Membership is fixed by each system's model and plan, listed here before results, and never by how it scored. The frontier systems stay in the main comparison: they are the reference that makes the cost and escalation results (RQ2, RQ3) meaningful.
