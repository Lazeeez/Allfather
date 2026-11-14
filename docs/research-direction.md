# A defensible research direction for Allfather

Working proposal, 2026-11-13. This is a hypothesis and experiment design, not a novelty
certificate or a statement of achieved results. Scope chosen by the author: localization
and escalation first. New paid API calls are excluded for now; PACE is available through
commands the author will run.

## Recommendation

Investigate whether **diagnosing the source of localization uncertainty improves the
choice of additional computation on unseen repositories**. Keep Allfather as the
experimental platform. A broad claim about confidence routing, retrieval plus agents,
multilingual support, or browser deployment will not carry method novelty.

Candidate title: **Rerank or Search Again? Diagnosing Localization Failures to Allocate
Repository Search Effort**. The word “diagnosing” refers to a pipeline failure, not proof
of the program's causal defect.

The specific proposed mechanism distinguishes:

1. A useful location is probably already in the candidate pool, but poorly ranked.
2. The pool probably misses useful locations; reranking the same pool cannot recover them.
3. Additional local retrieval probably will not help; agent exploration may be worthwhile.

The controller chooses keep, rerank, expand retrieval, or invoke a fixed agent, based only
on evidence available before that action. The potential contribution is the operational
failure decomposition, its predictive value, and its transfer to new projects. The generic
expected-utility objective and the act of routing are established ideas.

## Closest work and what it rules out

These are targeted primary-source checks on 2026-11-13, supplementing the two supplied
reviews. They are not an exhaustive systematic review. Full artifact reproduction and
forward/backward citation screening remain necessary.

| Source and inspected scope | Overlap / consequence |
|---|---|
| [SweRank+, v1](https://arxiv.org/html/2512.20482v1), method/stopping description | Already combines multilingual retrieval/reranking with iterative agent search; stops on a turn limit or no new relevant functions. “Iterative localization” is not our novelty. |
| [SHERLOC, v2](https://arxiv.org/html/2606.24820v2), action/termination and quality discussion | Already gathers diagnostic evidence with structured tools and decides whether to continue. “An agent that checks whether it has enough evidence” is insufficient differentiation. |
| [When Does Confidence-Based Cascade Deferral Suffice?](https://proceedings.neurips.cc/paper_files/paper/2023/file/1f09e1ee5035a4c3fe38a5681cae5815-Paper-Conference.pdf), abstract/introduction | Already explains failures of confidence-only deferral and studies downstream-aware alternatives. Predicting agent benefit is not new theory. |
| [Unified Routing and Cascading](https://proceedings.mlr.press/v267/dekoninck25a.html), proceedings record | General cost-quality routing/cascading is established. Use it as a methodological baseline. |
| [Adaptive Re-Ranking, v1](https://arxiv.org/html/2606.25249v1), method/related work | Already learns utility-based selection among BM25, light and heavy rerankers. Merely adding a third stage is not a contribution. This full text resolves an access gap in the supplied reviews. |
| [Sufficient Context](https://research.google/pubs/sufficient-context-a-new-lens-on-retrieval-augmented-generation-systems-2/), primary abstract | Already separates insufficient retrieved context from failure to use adequate context, and studies selective generation. Do not claim this distinction as newly invented. |
| [RCL, v1](https://arxiv.org/abs/2609.11023), abstract only | Proposes structural coverage/novelty signals and targeted follow-up retrieval for code generation. This is close adjacent work; inspect its full method and artifact before claiming a structural coverage signal is novel. |
| [Who Pays for Efficient Inference?](https://arxiv.org/abs/2610.23249), abstract only | Already studies task/language dependence of confidence routing. Multilingual fairness or confidence transfer alone is also a crowded framing. |

The proposed distinction is therefore narrow: **snapshot-grounded candidate coverage and
ranking diagnostics used to choose corrective search actions, measured against equally
informed generic benefit routers and specialized localization agents under project shift**.
This remains a candidate distinction until the closest implementations and citation chain
have been checked. If those already implement the same mechanism, change the method or
frame the work as a replication/empirical investigation instead of claiming invention.

## What the existing data actually permits

The exposed full-report subset has 198 issues. The reproducible
[headroom audit](../results/research/corrections/headroom-v1.json) uses exact-ID sensitivity
and the same saved outputs; it does not rerun models or fix the full evaluator.

| Outcome under hit@10 | Astra comparison | Luna comparison |
|---|---:|---:|
| Browser Allfather succeeds | 153 | 153 |
| Allfather+GPU succeeds | 152 | 152 |
| Agent succeeds | 171 | 142 |
| Agent succeeds; both local variants miss | 27 | 20 |
| Both local variants succeed; agent misses | 14 | 31 |
| GPU alone succeeds; browser and agent miss | 1 | 2 |
| All three miss | 12 | 19 |
| Oracle chooses a successful output among the three | 186 | 179 |

These counts establish observed complementary errors, not that they can be predicted.
The oracle sees the answer key and is not deployable. The GPU-specific rescue count is
small: existing outputs do not justify a complex three-way router by themselves.
Top-ten saved rankings also do not identify whether a gold symbol was absent from the
original retrieval pool. A method claiming that diagnosis needs new stage-level records.

## The experiment that can establish a contribution

First log the complete candidate universe, pre-rerank pool and each stage's ranking on
development projects. Define observable outcomes separately: gold outside the universe
(parser/task limitation), gold in the universe but outside the pool (retrieval miss), and
gold in the pool but outside the evaluated top k (ranking miss). Report both any-gold and
all-gold variants. These are evaluation labels, never inference-time inputs or causal
fault labels. Candidate presence alone does not prove that the retrieved text provides
enough reasoning context.

Collect paired outcomes for a small, fixed set of actions on the SAME development issues:
keep the current output; rerank the current pool; expand lexical/semantic retrieval with
a fixed wider budget; and a pinned agent condition when existing/PACE compute permits.
Run every action in the pilot, including on issues a proposed gate would retain, so rescue
and harm are not censored by an existing policy. Use repeated runs on a subset to measure
agent outcome variability. Begin with a one-decision controller, not a full RL search loop.

Cheap proposed features are lexical/semantic disagreement, score concentration, candidate
file diversity, unresolved report identifiers, graph boundary coverage, parse coverage and
rank stability under small budget changes. Feature collection itself has a measured cost.
Do not use gold-derived hint strata, patch size, modified filenames or the expensive
agent's response to decide whether to invoke that agent.

Compare a structured estimator of candidate/ranking deficits and action benefit with:

- Fixed cheap pipeline, fixed expanded retrieval, fixed reranker, always-agent.
- Random selection matched by actual expected cost and repeated draws, plus call-share controls.
- Score margin, current confidence, and confidence calibrated to the final cheap output.
- A direct benefit router using the SAME features, supervision budget and model capacity.
- An adaptation of Adaptive Re-Ranking and a compatible full SweRank+/specialized agent.
- An oracle action selector, marked diagnostic only.

The decisive ablation removes the proposed failure decomposition while retaining the
same features and capacity. Another removes the structural coverage features. If the
generic router performs just as well, the proposed mechanism has not earned a method
contribution. Report prediction calibration and action-selection regret, but make the
primary outcome useful localization at comparable measured cost.

Fit and tune on separate project groups. Keep duplicate/related issues in one group.
Freeze the evaluator, features, action definitions, comparator family, cost boundaries,
operating point and acceptance margin before collecting a new confirmation set. Existing
fresh results can support exploratory analysis, not confirmation of this newly chosen idea.
Use project-clustered paired intervals and issue-/project-weighted estimates; simulate
power on development data rather than promise an arbitrary final set size.

Count per-issue cheap + feature/gate + selected incremental-action cost, retries included.
Unknown cost stays unknown. Measure cold preparation and warm use separately. PACE is
available compute, not zero resource consumption. No browser latency or repair success
claim follows from these experiments.

## Decision rules before scaling

1. **No useful action diversity:** if wider retrieval offers little rescue beyond the fixed
   pipelines on development data, stop building a complex action selector.
2. **No predictable action value:** if held-out development projects show no reliable
   improvement over random/margin/direct-benefit controls, retain the simple method.
3. **No mechanism-specific gain:** if the structured model is matched by the same-feature
   generic router, do not claim the decomposition improves allocation.
4. **No transfer or honest cost benefit:** narrow to a measured failure study; do not tune
   on confirmation results and then describe them as prospective validation.

Numerical success margins still need to be chosen from the intended use and development
power analysis. No margin or positive outcome is being selected from the exposed test set.

## Other viable pivots

| Direction | Why consider it | Evidence burden / recommendation |
|---|---|---|
| Localization evaluation validity | The import defect already changes a headline conclusion; resolution/granularity may alter comparisons further. | Potential empirical contribution if independently generalized across multiple systems and datasets. Fixing only our own pipeline is insufficient for a broad claim. Keep as a serious fallback. |
| Robustness under report and repository change | Tests whether routing decisions survive benign wording or code-identity changes. | Needs semantics-preserving transformations, leakage controls and a separate prior-art review. Use as a targeted stress test first. |
| Repair efficiency or diagnostic guidance | Broader downstream impact. | Crowded related work and executable environments; outside the chosen first phase. |
| Another graph/RAG model or bigger reranker | Easy to fit the existing platform. | Not enough novelty without a specific demonstrated mechanism; no current reason to prioritize it. |

## Immediate PACE work

Full CPU inventory job 7008760 completed 580/580 snapshots, and L40S environment
preflight job 7009198 passed; see [cluster/research/README.md](../cluster/research/README.md).
Audit job 7012218 passed saved-artifact integrity, finding 65 ambiguous gold IDs
across 23 issues and zero missing IDs. Rescore job 7012506 produced descriptive
sensitivities; its full archive has now been verified and analyzed. The
[paired project analysis](research-evidence-2026-11-14.md) does not establish an
advantage over SweRankEmbed-Large. Astra rescues 31 browser misses but harms 11
browser successes on 198 issues, supporting exploratory action-value analysis.
The full-set strict gap between website-gpu and SweRankEmbed-Large is only four
hits; on the agent subset website-gpu has one fewer hit than website. Neither
marginal comparison establishes how often an action rescues or harms an individual
issue, or whether a controller can predict that benefit. These results still do
not justify a complicated GPU stage by themselves.
Inspect occurrence-level ground truth before freezing identity policy. All 78
flagged targets have now been checked against cached source; examples include
15 same-name Next.js constructors
on a single minified line, a parser error overlapping a Traefik gold function, and
a Zed parser error far from its gold method. A line-number suffix alone cannot
resolve the Next.js collision. Retain these cases explicitly; do not select a
metric interpretation because it favors a system.
Development-only stage/action logging and an existing-weight GPU replay are now
implemented in the [pilot protocol](development-replay.md). Its seeded 47 rows span
24 projects. The six-issue L40S smoke job 7018060 reports successful completion;
validate its saved traces before submitting the full pilot via the protocol's
conditional command. This phase tests candidate-pool coverage and action diversity;
it does not fit or establish a routing method.

The offline [split audit](../results/research/corrections/split-audit-v1.json) rules out
using the historical ten-issue pilot as an unseen-issue test of the full pipeline:
all ten appear in the browser ranker's declared training pool. The 580 fresh full-report
rows have no case-normalized project overlap with the reconstructed browser training
pool or available eligible CE records. Use these only for exploratory development,
with project-grouped validation; do not relabel them as new confirmation data. Group
the two PR rows for `microsoft/markitdown` issue 2340 together. Historical trained-row
provenance, repository aliases/forks and upstream model exposure still need investigation.

The defensible statement today is: **we have a concrete, falsifiable candidate method and
an experimental platform, plus a verified reason to rebuild the evidence**. The stronger
claim about improved allocation must be earned by the controlled experiments above.

## Development decision, 2026-11-14

The [verified 47-row pilot](research-development-results-2026-11-14.md) does not
meet the current action-diversity prerequisite for a complex router: base CE50
hits 39/47, the same success set as the six-action oracle. Wider retrieval adds
11 labeled targets to candidate pools but no additional hit@10 success. Both
rescues occur in validation projects; fit projects supply no positive rescue
examples. Do not train a benefit router or claim improved allocation from this
pilot. Keep the simple reference and audit fit failures before proposing a new
action; the failure/evaluation-study fallback remains open. This is a small
exploratory result, not proof of equivalence or impossibility of useful routing.

The subsequent [fit audit and text-view protocol](research-fit-evidence-2026-11-14.md)
identifies two in-read-set failures with edit-related code beyond the document
prefix, plus query truncation and feature-extension interpretation issues. The next
job tests fixed-budget context views on all 23 fit rows. Passage selection, query
reformulation and cost-aware routing have close prior art; this is a mechanism
experiment, not an established new method. The router remains deferred.

The [completed text-view study](research-text-view-results-2026-11-14.md) rescues
one fit issue: 18/23 to 19/23 with several fixed controls. All-control oracle
coverage is also 19/23, so this still does not justify a router. Supabase's target
score can improve while its rank worsens, showing why visibility alone is insufficient.
Freeze base-50 head/tail query+document views against base-50 prefix views for
development validation; keep every other condition diagnostic. This is a small
engineering/mechanism result, not a differentiated research contribution yet.

## Validation decision, 2026-11-15

The [frozen primary comparison fails to improve](research-text-view-validation-2026-11-15.md):
base-50 head/tail query+document scores 20/23 versus 21/23 for prefix reranking,
with no rescues and one uv regression. The all-PR sensitivity agrees. None of the
16 controls rescues a validation miss; their oracle union equals the baseline.
Retain the prefix reference, end this context-view sweep, and do not select a new
winner from validation. Further work should address fit-only candidate coverage
or task validity with a new falsifiable mechanism and explicit prior-work comparison.
The present evidence does not establish a novel method; any later confirmation
requires new frozen data. No additional PACE job is needed to resolve this branch.
