# 0035: Allfather on the Long Code Arena bug-localization leaderboard

## Status

Accepted, 2026-11-06. Written before Allfather has run on any Long Code Arena bug. The test split is scored once, after the rule below has been applied to the training split.

## Context

Long Code Arena (JetBrains) keeps a public leaderboard for bug localization: given an issue and the repository at the commit where the bug is reproducible, name the files the fix changes. The data is on Hugging Face (`JetBrains-Research/lca-bug-localization`), with `py`, `java` and `kt` configurations and a hand-checked `test` split of 50 bugs each. Submissions are sent by email with a reproduction package. Entries are scored on the set of files a system names, not on a ranking: precision, recall, F1, false-positive rate, the share of bugs answered exactly (`All_correct`) and the share answered with no correct file (`All_incorrect`), averaged over bugs. The best entries today have F1 about 0.58 (Claude 3.5 Haiku 0.583, o1 0.576), naming 2 to 4 files per bug.

What I checked before deciding to enter, without running anything:

- **No test bug is in Allfather's data.** None of the 100 Python and Java test bugs is in any of Allfather's ground-truth files. One Java bug (`google/gson` #2364) is in one of my held-out test sets, which no model trained on.
- **Some projects are familiar.** 13 of the 50 Python test bugs and 2 of the 50 Java ones come from projects I have trained, tuned or tested on (`data/fresh/excluded.json`). I report the result without them as well.
- **Kotlin is out of reach.** Allfather does not parse Kotlin, so the entry covers the Python and Java configurations, 100 of the 150 test bugs, and says so.
- **The answer keys include tests.** 19 of the 50 Python and 27 of the 50 Java test bugs change a test file. Allfather never ranks test files, so without a rule for tests it cannot name them.

## Decision

The system is the website's pipeline in the browser configuration (the `website` system of ADR 0033: browser rankers, static embeddings and the language-model stage, run by `scripts/live_eval.py`'s `Site`), unchanged. Its file ranker orders the repository's files. The answer is the top `k` files, optionally with their tests:

- **k** is one of 1, 2, 3, 4 or 5.
- **Tests** is either *off* or *paired*. Paired adds, for each named file, one test file from the repository at the base commit whose name follows the language's convention for that file: `test_<name>.py` or `<name>_test.py` for Python, `<Name>Test.java`, `<Name>Tests.java` or `Test<Name>.java` for Java. If several match, the one whose directory shares the longest prefix with the named file's directory is taken, then the alphabetically first.

**Choosing the setting.** For each language, I draw 150 bugs from the `train` split at random (seed 0) and choose the setting with the highest mean F1; ties go to the smaller `k`, then to *off*. Nothing else is tuned. The test split is then run once with the chosen settings, and the run is logged in `results/test-evals.log`.

**Scoring.** The metrics are computed as the leaderboard's evaluator computes them (`lca-baselines`, `bug_localization/src/baselines/metrics/quality_metrics.py`), per bug and then averaged. The false-positive rate counts all files of the configuration's language in the repository at the base commit as the negatives. I report per language, both languages together, and both languages without the bugs from familiar projects.

**Submission.** I send the result, the reproduction package (`scripts/lca_bug_localization.py` and the answer files) and the metadata to the address the leaderboard gives, under my own name, with the coverage (Python and Java only) and the familiar-project numbers stated.

## Consequences

- The leaderboard entry is comparable with the others only on two of their three languages; the email and any table I publish say so.
- Allfather's ranking quality is not what this leaderboard measures. Its own metrics (hit@k) are reported alongside, from the same run.

## Amendment, 2026-11-06: replacing training bugs whose repository is gone

Written after the training rankings were collected and before `choose` has computed any score from them. Two of the 150 Java training bugs (`hashgraph/hedera-mirror-node` #286 and #59) cannot be run: the repository no longer exists on GitHub. Counting them as misses would score every setting on 148 real bugs and two blanks. Instead, a training bug whose repository cannot be cloned is replaced by the next bug in a shuffle of the remaining training bugs (seed 1), skipping any whose repository cannot be cloned either, until the language has 150 bugs with a ranking; `choose` uses exactly those 150. The replacements are drawn by this rule, not chosen. The test split is not changed: a test bug that cannot be run counts as a miss, as the leaderboard defines its set.
