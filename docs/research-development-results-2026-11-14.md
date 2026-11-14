# Development pilot: verified results and decision

The 47-row pilot provides no hit@10 advantage for choosing among the six actions
over always using the base pool with top-50 cross-encoder rereading. This is an
exploratory result on 24 projects, not proof that adaptive localization cannot
work. It fails the current action-diversity prerequisite for a complex router.
No controller has been trained and no new method claim is established.

## Evidence verified

The transferred `reports/development-replay-7019874.tar.gz` is 48,651,305 bytes,
SHA256 `1f978db6bd3e576eaecc49e0f39a06459e40becba170b03c5318fc6fd9e8822f`.
The original archive remains in ignored local `reports/` and on PACE; it is not
added to Git. The committed [analysis](../results/research/corrections/development-analysis-v1/analysis.json)
records its hash and every archived file hash. Preserve the original archive.

- Local validation passed all 6 smoke traces and all 47 pilot traces. The PACE and
  local full-pilot validation reports agree exactly. Printed trace hashes match.
- Each run's 46 recorded Python source hashes match its recorded Git commit.
  Model revisions/file hashes, adapter weight hash and exported ranker hash match
  the pinned assets. This is provenance validation, not model recomputation.
- All six repeated smoke issues have identical indexed universes, source-file
  lists, candidate features, local scores, CE scores and final action rankings in
  the full pilot. The maximum CE score difference is zero on these repeats.
- The gold join uses the previously verified complete-symbol audit, not the
  filtered retrieval universe as a substitute declaration inventory. All 118 gold
  IDs in this pilot are audited unique, present in the retrieval universe, and
  outside flagged parser-error files. Strict-symbol and name-group results agree.
  This does not certify parser completeness or causal labels.
- Twenty-seven targeted tests passed across the analysis, rank-slot handling,
  archive verification, stage validation, capture and inventory scoring/statistics.

## Fixed action results

Hit@10 means at least one labeled target in the first ten output slots. Duplicate
rows keep their slots. Recall/all-target success retain every target in the
denominator; MRR is truncated at ten. The original labels are unchanged.

| Action | All rows | Fit projects | Validation projects | Rescues / harms vs base |
|---|---:|---:|---:|---:|
| Base local | 37/47 | 18/23 | 19/24 | — |
| Wide local | 36/47 | 17/23 | 19/24 | 0 / 1 |
| Base + CE50 | 39/47 | 18/23 | 21/24 | 2 / 0 |
| Base + CE200 | 38/47 | 17/23 | 21/24 | 2 / 1 |
| Wide + CE50 | 39/47 | 18/23 | 21/24 | 2 / 0 |
| Wide + CE200 | 39/47 | 18/23 | 21/24 | 2 / 0 |

There are 12 fit projects and 12 validation projects. Both new hits occur in
validation: `anomalyco/opencode#41793` and `skylot/jadx#2995`. The fit split has
zero positive hit@10 rescue examples for all five additional actions. Do not fit
a rescue classifier on this split or move these validation rows into fit and
continue calling the same validation results held out.

The oracle union is **39/47**, exactly the successes reached by base CE50. A router
could potentially save computation at that quality, but the pilot establishes
neither learnability nor cost superiority. Base CE50 improves observed hit@10 by
4.26 percentage points; its descriptive pointwise project-bootstrap interval is
0 to 10.64 points. These small exposed-data estimates are not confirmation or a
formal superiority test. Outcome-independent issue deduplication gives 46 rows;
hit counts and the two rescues remain unchanged.

The secondary metrics also do not justify the heavier action as the default:
base CE50 has macro-issue recall@10 0.6839 and all@10 28/47; wide CE200 has the same
aggregate values. MRR@10 is 0.5676 versus 0.5396, respectively. These descriptive
comparisons do not establish equivalence or authorize changing the primary target
after observing results.

## Where useful targets are lost

| Stage | Issues with any target | Issues with all targets | Targets present |
|---|---:|---:|---:|
| Indexed universe | 47/47 | 47/47 | 118/118 |
| Base candidate pool | 43/47 | 38/47 | 92/118 |
| Wide candidate pool | 44/47 | 41/47 | 103/118 |
| Base MiniLM prefix | 40/47 | 29/47 | 69/118 |
| Wide MiniLM prefix | 40/47 | 29/47 | 69/118 |

Widening retrieves 11 additional labeled targets, but none yields an additional
hit@10 success. This is a measured gap between candidate coverage and useful
ranking; it is not yet a novel or predictively useful diagnosis method.

Eight rows (seven underlying issues) fail under every action:

| Row | Observed bottleneck |
|---|---|
| QuantumNous/new-api#7761 | Target absent from both candidate pools |
| Comfy-Org/ComfyUI#15922 | All six targets absent from both candidate pools |
| skylot/jadx#3044 | All three targets absent from both candidate pools |
| supabase/supabase#49940 | Widening recovers the target at local rank 177; CE200 moves it to 66 |
| ultraworkers/claw-code#3332 | Best target rank 264 in base, 427 in wide; neither CE depth reads it |
| microsoft/markitdown#2342 | Target rank 56 misses CE50; CE200 pushes it to 88 (111 with wide) |
| immich-app/immich#31079 | Target moves from rank 18 to 13 with base CE50; still below the cutoff |
| microsoft/markitdown#2356 | Target moves from rank 24 to 32 with base CE50 |

The two MarkItDown rows belong to the same underlying issue and stay grouped.
The [per-row artifact](../results/research/corrections/development-analysis-v1/rows.jsonl)
retains every target ID, identity status, retrieval row and action rank.

Observed harms also matter: wide local ranking moves an Archify #515 target from
rank 10 to 13, and base CE200 moves Immich #31348's target from rank 5 to 11.
Neither should be dropped from reporting because another action reverses the harm.

## Resource interpretation

Supabase #49940 expands from 165 to 14,359 candidates because selecting additional
files includes all their units. Fourfold channel budgets are not a fourfold pool
size limit. The pilot preserves this behavior; it was not capped after inspection.

Across the 47 rows, the CE token counter records 519,410 for base CE50 and 1,870,198
for wide CE200 (about 3.60 times as many). These are counter-defined unpadded token
positions including the cached query prefix per action, not billable API tokens
or a complete accounting of GPU work. Feature collection, padding, cache copies,
preparation and model loading need separate resource accounting.

The run takes 797.93 script seconds and 856 Slurm seconds. Trace timers total
635.13 seconds; about 157.06 seconds lie outside traces and the 5.74-second
model-startup timer. First-use costs and sequential cache reuse affect individual
actions. Do not treat observed later-stage speed as controlled standalone latency
or discard overhead when estimating a deployed policy's cost.

## Decision and next work

1. Keep base CE50 as the simple development reference. Do not train or claim a
   six-action benefit router from this pilot, and do not launch another uniform
   budget sweep in search of a favorable result.
2. Audit the fit-project failures and the label/source granularity. In particular,
   distinguish retrieval omission, inaccessible read prefixes and poor ordering
   of already-read targets before designing another corrective action.
3. If that audit motivates a materially different action, specify its mechanism,
   limits, closest-work comparison and acceptance rule before collecting a broader
   metadata-selected development cohort. Preserve project grouping and explicitly
   account for this pilot's exposure. Current results do not establish that such an
   action is novel, effective or predictable.
4. If no useful complementary action emerges, follow the stated stop rule and
   narrow toward a rigorously generalized failure/evaluation study rather than
   claiming a new routing method. New confirmation data remains necessary for any
   method selected through this exploratory work.

## Reproduction

After safely extracting the original transfer and the historical inventory-rescore
archive into separate directories, run (the output directory must not exist):

```bash
.venv/bin/python scripts/analyze_development_replay.py \
  --bundle reports/pace-development-7019874 \
  --historical-bundle reports/pace-7012506 \
  --archive reports/development-replay-7019874.tar.gz \
  --out reports/development-analysis-reproduction
```

The script verifies archive members against extracted files, run provenance,
trace integrity, historical audit hashes and the frozen selection before scoring.
No model downloads, model inference, training or network calls are required.
