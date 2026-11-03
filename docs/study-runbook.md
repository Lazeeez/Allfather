# Running the ADR 0033 study

The order in which I run [ADR 0033](decisions/0033-frontier-comparison-protocol.md). Every run on fresh-2026 appends to `results/test-evals.log`; results land in `results/research/frontier/fresh*_<system>.jsonl`.

## 1. Build and seal fresh-2026 (with my `GITHUB_TOKEN`)

```powershell
uv run python scripts/fresh_set.py exclusions
uv run python scripts/fresh_set.py projects --per-language 17
uv run python scripts/fresh_set.py mine --created-after 2026-08-01   # resumable; rerun until it finishes
uv run python scripts/fresh_set.py seal --per-language 100 --cap 12 --agents 200   # vets each drawn bug; resumable
```

Commit `data/fresh/` (manifest, answer keys, hashes) before step 2. Nothing may be tuned after this point.

## 2. Run every system

| Tier | System | Command |
|---|---|---|
| T0 | Website pipeline, six languages | `uv run python scripts/fresh_website.py --set fresh`, and again with `--set fresh-agents` so the agent comparison has the same 200 bugs |
| T0 | allfather-fast, Python bugs | `uv run allfather eval --dataset fresh --gold data/fresh/gold_eval_python.jsonl --retriever ltr-ce-more-data-notests --level function --out results/research/frontier/fresh_eval.json`, then `uv run python scripts/eval_import.py --set fresh --system allfather-fast --results results/research/frontier/fresh_eval.json` |
| T1 | SweRank retrievers (PACE) | `cluster/RUNBOOK.md`, section "fresh-2026 with SweRank's retrievers" |
| T3 | Claude Opus 5.5, one call | `uv run python scripts/frontier.py run --set fresh --system claude-single` |
| T3 | Gemini 3.8 Flash, one call, free tier | `uv run python scripts/frontier.py run --set fresh-agents --system gemini-single` (20 a day; rerun daily) |
| T4 | Claude Opus 5.5 agent | `uv run python scripts/frontier.py run --set fresh-agents --system claude-agent` |

Runs are resumable. Claude runs use my Pro plan and stop at its usage limits; I rerun them later.

## 3. Analyse

Choose the escalation threshold on development data first (`uv run python scripts/fresh_analysis.py --set pilot`, or a larger development set), record it in ADR 0033, then:

```powershell
uv run python scripts/fresh_analysis.py --set fresh --threshold <chosen>
uv run python scripts/fresh_analysis.py --set fresh-agents --threshold <chosen>
```
