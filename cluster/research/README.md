# PACE research jobs

## Confirmed hardware and account (2026-11-13)

The author's job 7009034 successfully allocated one `gpu:l40s:1` on `coc-gpu`
with account `coc` and QoS `coc-ice`. It reported NVIDIA L40S, 46,068 MiB VRAM
and driver 615.71.09. Follow-up preflight job 7009198 at commit `4731578` also
passed model-library imports and CUDA float32/float16/bfloat16 matrix operations.
It used PyTorch 2.14.0+cu130, Transformers 5.17.0, Sentence Transformers 6.1.0,
PEFT 0.21.0 and safetensors 0.8.0. The author's supplied result is recorded in
[pace-preflight-7009198.json](../../results/research/corrections/pace-preflight-7009198.json).
Model loading, inference throughput and research outcomes are not yet validated.

The supplied QoS query reports `MaxSubmitJobsPU=50` for `coc-ice`; use this as
the pending/running job ceiling, rather than the association's larger limit of
500. The displayed running-job/resource/walltime QoS fields were blank; inherited,
group and partition limits can still apply. `coc-gpu` has a 16-hour walltime limit;
`coc-cpu` has an 18-hour limit. These limits are not runtime estimates.

The supplied partition inventory lists 32 L40S and 8 A100 GPUs on `coc-gpu`.
`ice-gpu` also exposes H100/H200 nodes with `AllowQos=ALL`, at lower partition
priority; access and model compatibility have not been tested there. Partitions
overlap, so do not sum their hardware counts. Counts describe configured capacity,
not currently available resources. Start model work on the confirmed L40S.

## Inventory purpose

Collection job 7008760 completed 580/580 snapshots with no recorded failures in
1:59:59. Its user-supplied [summary](../../results/research/corrections/pace-inventories-7008760.json)
flags parser-error files in 400 snapshots and colliding IDs in 512; 372 have both,
and 40 have neither. These are repository-wide flags, not counts of invalid gold
targets. The full inventory artifacts still need integrity and gold-coverage checks.
Do not repeat the collection solely because these flags are present.

The first job is **CPU-only inventory extraction**, not training or agent inference.
It builds complete candidate inventories at the 580 fresh base snapshots, using the
same supported languages/test exclusions as the shared chunker. This enables a scorer
that resolves predictions without consulting gold labels and exposes parser/ID collisions.
It does not assess whether the benchmark labels are causally correct.

## Update the PACE checkout

Pull the research-correction commit into your existing PACE checkout. The repository
contains the Python source, tests and job; the existing checkout supplies its environment
and caches. Use a clean checkout so the tested source can be identified unambiguously.

The previously documented PACE path is `~/scratch/Odin`; adjust it if yours differs:

```bash
cd ~/scratch/Odin
git pull --ff-only origin main
.venv/bin/python -m pytest tests/test_resolution.py tests/test_symbol_inventories.py tests/test_research_corrections.py -q
mkdir -p results/research/corrections/pace-logs
```

The job records the Git commit, hashes of the actual source files and parser package
versions. Source hashes also identify any local changes made after pulling.

## Smoke job: three snapshots

```bash
sbatch --account=coc --qos=coc-ice --partition=coc-cpu --cpus-per-task=2 --mem=16G --time=00:30:00 \
  --job-name=allfather-inventory-smoke \
  --output=results/research/corrections/pace-logs/inventory-smoke-%j.log \
  --export=ALL,INVENTORY_LIMIT=3,INVENTORY_OUT=results/research/corrections/inventories-smoke-v1 \
  cluster/research/inventories.sbatch
```

The account and QoS match the author's successful allocation. The script uses `.venv/bin/python`; set
`ALLFATHER_PYTHON` if the existing environment is elsewhere. No package installation is
performed. The existing `.cache/repos` is reused; missing public Git objects may be fetched.

After Slurm completes, inspect:

```bash
cat results/research/corrections/inventories-smoke-v1/summary.json
```

Expected: `expected: 3`, `completed: 3`, `failures: []`. Parser-error or collision lists
can be nonempty; they are scientific findings to inspect, not silently discarded rows.
This script is sequential; two CPUs are sufficient for the first pass. Requested walltime
is a scheduling allowance, not a measured runtime estimate.

## Full job after a successful smoke run

```bash
sbatch --account=coc --qos=coc-ice --partition=coc-cpu --cpus-per-task=2 --mem=16G --time=04:00:00 \
  --job-name=allfather-inventories \
  --output=results/research/corrections/pace-logs/inventories-%j.log \
  --export=ALL,INVENTORY_LIMIT=0,INVENTORY_OUT=results/research/corrections/inventories-fresh-v1 \
  cluster/research/inventories.sbatch
```

Resubmit the same command if interrupted: completed snapshot files are reused, while
failed snapshots are retried. A manifest mismatch refuses to resume; changed code or
parser versions require a new output directory. Original gold, rankings and model files
are not overwritten. Do not run two jobs against the same output/cache concurrently.

## GPU environment check (can run alongside inventory)

After updating the checkout and creating the log directory above, submit:

```bash
sbatch --account=coc --qos=coc-ice --partition=coc-gpu \
  --nodes=1 --ntasks=1 --gres=gpu:l40s:1 \
  --cpus-per-task=2 --mem=16G --time=00:10:00 \
  --job-name=allfather-gpu-preflight \
  --output=results/research/corrections/pace-logs/gpu-preflight-%j.log \
  cluster/research/gpu-preflight.sbatch
```

The check imports the existing model libraries and exercises CUDA matrix multiplication
in float32, float16 and bfloat16. It writes package/driver versions, device details,
the checkout commit and success or traceback to `pace-logs/gpu-preflight-JOBID.json`.
It refuses to overwrite an existing report. No packages or models are downloaded,
and no training, API calls or benchmark scoring occur. Ten minutes is an allocation
allowance, not a performance estimate. Send back the JSON and log even if it fails.

This validates environment readiness only. Existing-weight stage/action replay still
requires inventory validation and a development split audit before submission.

Preflight job 7009198 passed; do not rerun it for the unchanged environment. The
offline [split audit](../../results/research/corrections/split-audit-v1.json) finds
all 10 historical pilot issues in the browser ranker's declared training pool.
Do not use that pilot to claim unseen-issue/project performance of the full pipeline.
The 580 full-report fresh rows have no ID, snapshot or case-normalized project overlap
with either the reconstructed browser pool or available eligible CE records. They
are still exposed exploratory data, not a new confirmation set. Two PR rows for
`microsoft/markitdown` issue 2340 must remain grouped. The audit does not establish
absence of foundation-model exposure or renamed/forked-project overlap.

## Audit the completed inventories

The next CPU job reads the existing gzip files one snapshot at a time. It verifies
SHA256 hashes, snapshot identities and internal counts, then reports unique,
ambiguous and missing gold IDs and whether their files have parser errors. Labels
and predictions stay unchanged; this job does not score systems. Run after pulling
the audit commit into the checkout:

```bash
sbatch --account=coc --qos=coc-ice --partition=coc-cpu \
  --nodes=1 --ntasks=1 --cpus-per-task=1 --mem=8G --time=01:00:00 \
  --job-name=allfather-inventory-audit \
  --output=results/research/corrections/pace-logs/inventory-audit-%j.log \
  cluster/research/inventory-audit.sbatch
```

One hour is an allocation allowance, not a measured duration. No repositories are
fetched or reparsed, and no inference is run. Results go to a fresh
`results/research/corrections/inventory-audit-JOBID/` directory. Send `summary.json`
and the job log first; retain `instances.jsonl` and `provenance.json` for detailed
diagnosis. `integrity_ok: true` confirms saved-artifact consistency, not semantic
parser correctness or complete extraction against Git. File and symbol totals are
summed over instance snapshots, so repeated source blobs are counted repeatedly.

An ambiguous gold ID can reflect an overload, repeated declaration or extraction
defect. A parser error somewhere in a gold file need not affect its target symbol.
Do not drop affected issues or silently repair their names based on these flags.

## Return artifacts

Send `summary.json` and the job log first. For actual rescoring, bring back the full
`inventories-fresh-v1/` directory (`manifest.json`, `index.json`, `summary.json` and compressed
snapshot files). It contains symbol IDs, kinds, ranges and Git blob IDs, not source text.
`collection_complete` means every selected file was visited; parser-error files must
still be reviewed before treating aliases as reliably unique.

The next GPU job will replay existing weights on development projects while logging
candidate pools and stage outcomes. It will be specified after inventory validation and
the development split audit. No large training sweep or new paid model calls are needed
for this first job.
