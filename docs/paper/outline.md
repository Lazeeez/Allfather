# Paper outline: Allfather on fresh-2026

A working outline. The method is already written, in [ADR 0033](../decisions/0033-frontier-comparison-protocol.md) (the comparison) and [ADR 0034](../decisions/0034-gpu-reranker-other-languages.md) (the reranker); this file says what goes where, and which part of `results/research/analysis_fresh.json` and `analysis_fresh-agents.json` fills each table and figure. Nothing in it reports a fresh-2026 result: those are read only once every system has run.

**Working title:** Can a free bug localizer in the browser keep up with frontier AI agents on bugs they cannot have memorized?

## 1. Introduction

- The problem: given a bug report and a repository, find the functions the fix will change.
- Why now: frontier models answer SWE-bench from memory. On the SWE-bench Verified pilot, Claude Opus 5.5 with only the file list did as well as the agent that could read code (0.9 hit@10), so older benchmarks no longer separate the systems.
- What I did: built fresh-2026, 580 bugs fixed after the models' training cutoffs in 74 projects and six languages, sealed before any system ran, and compared a free, browser-based localizer against frontier agents, frontier one-call answers, open-weight models and a published research system, under a protocol fixed in advance.
- Contributions:
  1. fresh-2026 and its sealing and vetting procedure;
  2. a pre-registered comparison across four tiers, with every deviation recorded before results were read;
  3. a free localizer that runs in the browser, with a GPU reranker shown to transfer from Python to five other languages;
  4. measurements of cost, run-to-run stability and the effect of what a report names.

## 2. Related work

From my literature review: information-retrieval bug localization; learning to rank; cross-encoder rerankers; SWE-bench and its contamination; agentic localization (SWE-agent, Agentless and their successors); SweRank. One paragraph each, ending on what each leaves open that this study addresses.

## 3. fresh-2026

ADR 0033's cutoff, sampling (up to 100 per language, at most 12 per project), vetting for bot and AI-written issues and pull requests, the seal (sha256 `f8b6194f…`), the agent subsample of 198, and the hint strata with my hand check.

- **Table 1:** bugs, projects and median repository size per language.
- The strata hand check: kappa from `strata_hand_check`; if it is below 0.6, RQ4 is reported as indicative only.

## 4. Systems

- **Table 2:** every system, by tier, with model, version, hardware, plan or price, and the set it ran on.

| Tier | Systems |
|---|---|
| T0 Allfather | website, browser only; website with the GPU reranker (configuration frozen from ADR 0034); allfather-fast (Python) |
| T1 research | SweRankEmbed-Large and -Small |
| T3 one-call | Claude Opus 5.5, gpt-6-astra, gpt-6-luna, gemini-3.8-flash |
| T4 agents | Claude Code (Opus 5.5), Codex (gpt-6-astra, gpt-6-luna) |
| Open weights | gpt-oss-120b and Qwen3-Coder-Next-FP8, as agent and one-call |

## 5. Method

From ADR 0033: metrics (hit@1, 5, 10, all@10, MRR at function level); project-clustered bootstrap intervals; exact McNemar tests on yes/no metrics and a sign-flip test on MRR, Holm-adjusted across each table; the escalation threshold fixed beforehand (0.7899); reuse of each one-call system's agent-subsample answers; the repeatability check.

## 6. Results

- **RQ1, accuracy.** Table 3 from `systems` (every system, with intervals) and `paired` (each against Allfather, Holm-adjusted). Figure 1 from `by_language`: hit@10 per language and system, with intervals.
- **RQ2, cost.** Figure 2 from `systems` (`cost_usd`, `seconds`) and `pareto`: accuracy against cost, with the systems nothing beats on both.
- **RQ3, escalation.** Figure 3 from `escalation`: sending only the bugs Allfather is least sure about to an agent, against sending the same number at random, with the operating point fixed in advance.
- **RQ4, hints.** Table 4 from `strata`: hit@10 by what the report names.
- **Stability.** From `repeatability`: how often gpt-6-astra's hit@10 outcome changes when it is asked again.
- **The reranker, on training data.** From ADR 0034: the Python-trained reranker's gain in each other language, and what training on all six adds.

## 7. Threats to validity

- Contamination: the cutoff postdates training, but projects and code may be known; I report the per-project bootstrap.
- Consumer plans: models run through Claude Code and Codex on paid plans, not raw APIs, so their system prompts and tool wrappers are part of each system, as a developer would use them.
- Non-determinism: one answer per bug, fixed in advance; measured on 50 bugs.
- Windows long paths: some early runs omitted deep files (never a changed one); `sensitivity_without_long_path_bugs` repeats every comparison without those bugs.
- Partial runs: a run that could not finish is reported on the prefix of the fixed order it completed.
- Model coverage: Google's flagship is absent for cost; gemini-3.8-flash is reported as a smaller model.

## 8. Discussion and conclusion

What the results mean for developers choosing a tool, and what a free, private-by-default localizer can and cannot replace.

## Checklist before writing results

- [ ] Every system in Table 2 complete or capped, and committed
- [ ] ADR 0034 decided and frozen in ADR 0033; website with the GPU reranker run on all 580
- [ ] Strata hand check filled in
- [ ] `uv run python scripts/fresh_analysis.py --set fresh --threshold 0.7899` and the same for `fresh-agents`
