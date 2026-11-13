# PACE research jobs

## Confirmed hardware and account (2026-11-13)

The author's job 7009034 successfully allocated one `gpu:l40s:1` on `coc-gpu`
with account `coc` and QoS `coc-ice`. It reported NVIDIA L40S, 46,068 MiB VRAM
and driver 615.71.09. This confirms allocation and driver visibility; it does not
yet verify the project's PyTorch environment or model throughput.

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
