# The ISSTA 2027 paper

**Not submission-ready.** The draft and generated tables still reflect the historical
evaluation. The significant SweRank superiority claim is withdrawn; normalization,
cost accounting and sampling/annotation wording need correction. Do not regenerate the
main tables from mixed evaluator versions. Follow [ADR 0037](../decisions/0037-research-corrections.md)
and [the current worklist](../research-status.md). The new research direction is a proposal,
not an established result.

Target: ISSTA 2027 research track (abstract 8 January 2027, paper 11 January 2027). The method is [ADR 0033](../decisions/0033-frontier-comparison-protocol.md) and [ADR 0034](../decisions/0034-gpu-reranker-other-languages.md); [outline.md](outline.md) is the original plan.

## Building

The format is ISSTA's: `acmart` with `acmsmall,screen,review,anonymous`, single column, 18 pages excluding references and the Data Availability section (2026 call; the 2027 call is not out yet). Build with Overleaf (upload `main.tex`, `refs.bib` and `generated/`) or locally with `tectonic -X compile main.tex`. Every number comes from `generated/`, which one command rewrites from the committed results:

    uv run python scripts/paper_tables.py

A result that has not run yet prints as a red **pending**. Never type a number into `main.tex`; cite it with `\res{<set>}{<system>}{<key>}` or a macro from `generated/numbers.tex`.

`\anontrue` in `main.tex` hides the tool's name and links for double-blind review; `\anonfalse` restores them.

## Before submitting

- [ ] Paid agents on full reports: Claude Opus 5.5 agent, gpt-6-astra agent and one-call (198), Astra one-call (580)
- [ ] Open models one-call on all 580 full reports
- [ ] Strata hand check filled in; kappa into RQ4
- [ ] Check the ISSTA 2027 call when it is published (the 2026 rules are applied now)
- [ ] Write the AI-use disclosure under the ACM Policy on Authorship
- [ ] Verify every `refs.bib` entry with a `VERIFY` note
- [ ] Anonymous artifact (anonymous.4open.science) built from the repository
- [ ] An advisor or another reader goes through it
