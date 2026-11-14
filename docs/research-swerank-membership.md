# Saved-export membership audit

Completed: [PACE job 7056950 and local verification](research-swerank-membership-results-7056950.md).
Every saved prediction ID is present, including every recovered ID. Ambiguous IDs remain
explicit. No repeat run is needed; commands below document the completed procedure.

The corrected SweRank imports have been rescored against complete symbol inventories,
and recovered IDs have now been checked against retained BEIR exports on PACE.
The fresh corpus bytes are not present locally. The historical runbook locates them on PACE
at `~/scratch/swerank/fresh` and `~/scratch/swerank/fresh-full`.

`scripts/audit_swerank_membership.py` verifies original prediction hashes against the
frozen import audit, reproduces every correction, and checks every saved slot against
the supplied export. It streams corpus files, hashes their bytes, counts duplicated
document IDs and reports `unique`, `ambiguous`, `missing`, or `unavailable` membership.
Recovered slots receive separate counts. All eight runs and all slots remain visible;
unavailable corpora do not become empty successful audits. The full-report export's
symlinks can reuse a scan of the identical underlying file.

No score, gold label or prediction is modified. There is no model inference, model
download or repository fetch. This is a CPU/I/O audit of saved files. Do not rebuild
missing exports and call the replacements original evidence.

## Run on PACE

From the existing checkout, after pulling the correction commit:

```bash
cd ~/scratch/Odin
git pull --ff-only origin main
mkdir -p results/research/corrections/pace-logs
ls -l ~/scratch/swerank/fresh/index.json ~/scratch/swerank/fresh-full/index.json
sbatch --account=coc --qos=coc-ice --partition=coc-cpu \
  --nodes=1 --ntasks=1 --cpus-per-task=2 --mem=8G --time=01:00:00 \
  --job-name=allfather-swerank-membership \
  --output=results/research/corrections/pace-logs/swerank-membership-%j.log \
  cluster/research/swerank-membership.sbatch
```

If the original exports are elsewhere, set `SHORT_EXPORT` and `FULL_EXPORT` to their
existing locations via `sbatch --export=ALL,SHORT_EXPORT=...,FULL_EXPORT=...`. The job
checks both indices before starting. It writes a new job-specific directory and refuses
to overwrite an existing audit. Paths with commas require an alternative Slurm export
mechanism; the defaults above need no override.

After completion, replace `JOBID` below with the submitted job number:

```bash
cat results/research/corrections/swerank-membership-JOBID/summary.json
tar -czf results/research/corrections/swerank-membership-JOBID.tar.gz \
  -C results/research/corrections swerank-membership-JOBID
```

Transfer that archive back to the current project as with earlier PACE results. It
contains corpus hashes and membership evidence, not the corpus source text. If the
saved exports are absent, return the missing-path output instead of rerunning export.

## Interpretation

`integrity_ok` describes completion and input consistency, not uniqueness or historical
provenance. `all_recovered_present` permits ambiguous membership and is not a strict-symbol
correctness result. The per-run counts distinguish both. Historical retrieval did not pin
corpus hashes, so even a successful audit cannot prove that these are the exact bytes used
at inference time. It does establish membership in the supplied retained exports and
records their identities for future checks.

The local tests cover duplicate IDs, absent IDs, unavailable corpora, unsafe index paths,
and refusal of a correction that differs from the saved import procedure. The completed
PACE result and subsequent local verification are linked above. The suite passed 331
tests when the collection auditor was added; the verifier adds further integrity checks.
