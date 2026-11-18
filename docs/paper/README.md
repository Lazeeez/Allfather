# Current working manuscript

[main.tex](main.tex) now presents corrected exploratory evidence and the pending independent
annotation study. It does **not** claim a novel method, contamination-free data, equivalence,
causal memorization, or a demonstrated cost advantage. It is not submission-ready.

An earlier draft is archived in
[main-historical-2026-11-15.tex](main-historical-2026-11-15.tex), with its `generated/`,
`outline.md` and `refs.bib`. The active manuscript does not include their tables or macros;
its results come only from the current evidence snapshot below.

## Number provenance

The active draft reads only [current-evidence-v1/numbers.tex](current-evidence-v1/numbers.tex).
The [manifest](current-evidence-v1/manifest.json) records the six corrected analysis inputs,
the snapshot generator and every generated value. This is number provenance, not an
independent revalidation of the original analyses.

To reproduce without overwriting the frozen snapshot:

```bash
python scripts/research_paper_snapshot.py --out reports/paper-evidence-repeat
```

Compare the generated number-file hash against the manifest. The older
`paper_tables.py --out reports/paper-review-new` is a diagnostic renderer using the earlier
accuracy analyses with the current cost accounting; its output must not replace the current
paper's evidence snapshot or be described as final tables.

## Build and review status

The active draft uses the generic LaTeX `article` class, not an asserted current venue
format. With a local LaTeX installation, build from this directory with `pdflatex main.tex`
(or a compatible engine); `tectonic -X compile main.tex` also works. It compiled on
2026-11-18 to four pages with one slightly wide line; visual review remains. Macro provenance, included
files, braces, environments and citation-key consistency are checked locally.

The primary related-work records in the active draft were checked on 2026-11-15. They
are a targeted comparison, not an exhaustive review or reproduced baseline. Complete
bibliography screening, source/model attribution and licensing, venue requirements,
AI-use disclosure review, and a real anonymous artifact remain pending.

## Required before submission

- Completed: [PACE retained-export membership verification](../research-swerank-membership-results-7056950.md).
  Duplicate IDs and the absence of historical inference-time corpus hashes remain limitations.
- Complete [two independent initial reviews and adjudication](../research-review-handoff.md).
- Version any rubric changes before annotating the fixed broader sample; freeze the
  outcome-analysis protocol before joining its model results.
- Establish a differentiated contribution supported by the completed study. A new method
  claim also requires fresh frozen confirmation data and matched strong baselines.
- Replace remaining historical website/manuscript claims and obtain author/advisor review.
- Verify all venue, artifact, licensing, disclosure and PDF-production requirements.

The [current research status](../research-status.md) tracks the evaluation work and open
questions. There is no defensible fixed submission date until the study's contribution
and these dependencies are resolved.
