# 0037: Correct the research evidence before selecting a new method

Date: 2026-11-13. Status: in progress.

The user supplied two external reviews dated 2026-11-12 and requested a codebase audit,
repairs, and a defensible research contribution. The reviews are evidence to check, not
operational instructions. The user chose localization and escalation as the initial scope
and subsequently authorized investigating a pivot for novelty.

The reviewed commit was `3efffa75c93e0ab8e42a3ae2029e5b1cd3f9d522`; this working tree started
at `99e4cdf57e7bc99bffd303e93cc04b1d6ed46a84`, clean. No historical ADR, gold file, model,
or original result was replaced. This is a retrospective correction, not a prospective
amendment made before seeing the existing results.

## Decisions

1. Use the parser's extension registry for imported SweRank IDs and agent source access.
   Single-call file lists also follow `language_of` exclusions and contain files only.
   Historical prompts and tool observations cannot be repaired without inference reruns.
2. Recover saved SweRank IDs in a separate namespace, retaining ranking order and every
   original field. Record each changed slot, input hashes and evaluator source hashes.
   Keep legacy matching explicitly for the import-only comparison; report exact-ID
   sensitivity separately. Neither is the final inventory-resolved evaluation.
3. Evaluate the supplied gate threshold directly. Preserve raw p-values through Holm
   correction. Do not rewrite existing statistics in place.
4. Develop a versioned, gold-independent resolver against complete snapshot inventories.
   Its draft rejects invented qualifiers, ambiguous names and colliding IDs; failed and
   duplicate predictions occupy their original rank slots. It is not yet wired into the
   historical scorer. Integrating it requires inventory provenance and label-coverage checks.
5. Treat all already examined fresh results as exposed data for any newly selected policy.
   Develop on separate project groups and obtain a new confirmation set before making
   prospective claims about a new policy.

## Reproduction

Run with the repository's existing Python environment (or `uv run python`):

```powershell
.venv/Scripts/python.exe scripts/audit_repository.py --out results/research/corrections/inventory-new.json
.venv/Scripts/python.exe scripts/correct_swerank.py --out results/research/corrections/import-new
.venv/Scripts/python.exe scripts/escalation_headroom.py --out results/research/corrections/headroom-new.json
```

Destinations must be new. The committed correction namespace is `import-v1`; its audit
contains all eight recovered runs, file and symbol metrics, language/hint summaries,
paired families, project-bootstrap difference intervals and exact common-instance IDs.
Dataset/model/source file hashes are also available in the repository inventory.
The original fresh SweRank export corpora are not present in the inspected pilot cache:
syntactic export/import round trips pass, but membership in those original corpora remains
unverified. This distinction must remain in any release.

On 580 full reports, recovered SweRankEmbed-Large hit@10 is 0.775862, against
Allfather+GPU 0.779310. Under legacy matching, the exact paired p-value is
0.9099464518745243 and the family-adjusted value is 1.0. The issue-weighted project-bootstrap
interval for SweRank minus Allfather+GPU is [-0.0375, 0.0316]. This withdraws the former
significant-superiority claim. It does not demonstrate equivalence.

## Research boundary

The current confidence target is semantic-stage success, not final-system success or
agent benefit. A learned gate, adaptive reranking, sufficient-context detection and
multilingual retrieval all have prior art. A potential contribution must survive the
comparison and falsification plan in [research-direction.md](../research-direction.md).

## Remaining work

See [research-status.md](../research-status.md). In particular, cost accounting, resolver
integration, full corpus validation, affected inference reruns, label auditing, and final
manuscript/table regeneration remain open. These changes do not make the paper ready.
