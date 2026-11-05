# The ISSTA 2027 paper

Target: ISSTA 2027 research track (abstract 8 January 2027, paper 11 January 2027). The method is [ADR 0033](../decisions/0033-frontier-comparison-protocol.md) and [ADR 0034](../decisions/0034-gpu-reranker-other-languages.md); [outline.md](outline.md) is the original plan.

## Building

Upload `main.tex`, `refs.bib` and `generated/` to Overleaf (acmart is built in). Every number comes from `generated/`, which one command rewrites from the committed results:

    uv run python scripts/paper_tables.py

A result that has not run yet prints as a red **pending**. Never type a number into `main.tex`; cite it with `\res{<set>}{<system>}{<key>}` or a macro from `generated/numbers.tex`.

`\anontrue` in `main.tex` hides the tool's name and links for double-blind review; `\anonfalse` restores them.

## Before submitting

- [ ] Paid agents on full reports: Claude Opus 5.5 agent, gpt-6-astra agent and one-call (198), Astra one-call (580)
- [ ] Open models one-call on all 580 full reports
- [ ] Strata hand check filled in; kappa into RQ4
- [ ] Check the ISSTA 2027 call: page limit, double-blind rules, data-availability and AI-use statements
- [ ] Verify every `refs.bib` entry with a `VERIFY` note
- [ ] Anonymous artifact (anonymous.4open.science) built from the repository
- [ ] An advisor or another reader goes through it
