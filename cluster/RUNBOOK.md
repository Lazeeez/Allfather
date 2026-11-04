# Running Allfather jobs on PACE

Every heavy experiment is a **manifest** in `cluster/manifests/`. A job ranks the issues a manifest names into a run directory. It never sees ground truth: scoring happens when the run is imported back into the repository.

**Working on PACE (ICE) since 2026-10-14.** The first job, `swerank-embed-small-lite` on one L40S, reproduced the laptop's run of the same manifest: identical recall, hit, all@k and MRR on all 291 issues, the same top 10 for 290 of them, and 99.65% of top-100 items in common (`results/runs/swerank-embed-small-lite-pace/`).

What it took to get there, each fixed in the scripts:

- jobs resolved Python packages offline and failed; `fetch.sh` now builds each job's environment in advance;
- a model's older `transformers` conflicted with the project's pins; a manifest can now replace and drop packages;
- the login node killed a fetch that downloaded too much at once; it now downloads less and one project at a time;
- forced offline mode broke one model's own loading code; offline mode is now a site setting, off on ICE, whose compute nodes reach the internet;
- the shared scratch filesystem made jobs crawl; jobs now work from the node's local disk;
- parsing workers forked after PyTorch started deadlocked on Linux; they are now started with spawn.

Two submissions were killed before the third finished. Their 143 rankings carry no invocation record, because records were written only at the end; a run now records each invocation when it starts and stamps every ranking with the commit and Slurm job that produced it.

## Once per cluster account

```sh
git clone <repository> ~/allfather && cd ~/allfather
cp cluster/site.env.example cluster/site.env     # then fill in the values
bash cluster/preflight.sh                        # checks the account, partition and paths
bash cluster/setup.sh                            # uv and the locked environment, on the login node
```

`site.env` holds the Slurm account, partition and (where the cluster requires one) QOS, the GPU type, and two directories: one on project storage for results, one on scratch for caches. It is git-ignored.

## For each experiment

```sh
git pull                                         # the commit you run is recorded in the run
bash cluster/fetch.sh  cluster/manifests/NAME.json     # login node: models, dataset, git mirrors
bash cluster/submit.sh cluster/manifests/NAME.json     # prints the job id and the run directory
```

- `fetch.sh` must finish before `submit.sh`. Whether compute nodes can reach the internet differs by cluster; set `ALLFATHER_OFFLINE=1` in `site.env` to force Hugging Face's offline mode in jobs. Some models' own loading code does not work in offline mode (SweRankEmbed-Small is one), so leave it at 0 where nodes have internet.
- The working tree must be clean. A run from uncommitted code is refused at import.
- A job that is killed or times out is resubmitted with the same command. Finished issues are skipped; at most the issue in progress is lost.
- A job copies the repository and the shared cache (git mirrors, embeddings, analysis cache) to the node's local disk before it starts, works there, and copies the cache back when it ends. On ICE the shared scratch is a network filesystem and the nodes have an 11 TB local disk at `/tmp`; set `ALLFATHER_LOCAL_DISK=0` to work on scratch directly.
- The analysis cache (a SQLite database) is not copied either way: each job builds its own on the node. A copy taken while a killed job was still writing it corrupted the shared one once, and rebuilding it costs a few minutes of parsing.
- Raise a job's time limit with `WALL_HOURS=6 bash cluster/submit.sh ...`.
- When the job ends, the run directory is copied from scratch to `$ALLFATHER_RESULTS/NAME/`.

## Running a script instead of a manifest

Benchmarks and other scripts that are not manifest runs go through `submit_script.sh`, which uses the same local-disk staging:

```sh
WALL_HOURS=4 bash cluster/submit_script.sh "python benchmarks/bench_cascade.py --label pace-l40s"
```

The command runs from a copy of the repository on the node's local disk, with the repository's `.venv` on the path. Whatever it writes under `results/` or `models/` is copied to `$ALLFATHER_RESULTS/script-<jobid>/` when it ends; the log is `$ALLFATHER_SCRATCH/logs/script-<jobid>.log`.

## Bringing a run back

```sh
rsync -a pace:PATH_TO_ODIN_RESULTS/NAME/ runs/NAME/     # on the laptop
uv run allfather import-run runs/NAME
```

`import-run` refuses the run unless every file matches its checksum, the manifest is the committed one, the commit is in this repository, the tree was clean, and every issue of the manifest is present. It then scores the rankings, writes `results/runs/NAME/result.json`, and appends a line to `results/test-evals.log` when the manifest names a test set.

## Testing a job before handing it over

```sh
uv run --extra dense allfather run --manifest cluster/manifests/NAME.json --out /tmp/NAME --local 3
```

`--local N` runs the same code on the first N issues. A local run is marked as such and cannot be imported.

## Manifests

| Manifest | What it runs | Needs | Expected |
|---|---|---|---|
| `swerank-embed-small-lite` | SweRankEmbed-Small (137M) as the retriever over Allfather's index, on Lite | one GPU, 6 GB; the `transformers<5` overlay in the manifest | about 30 GPU-minutes; fits the laptop |

A manifest's `environment.with` lists packages that replace the locked ones for that job. `fetch.sh` builds a separate environment for such a manifest under `$ALLFATHER_SCRATCH/envs/NAME` on the login node, and the job runs from it: compute nodes have no internet, so nothing is resolved or installed at job time. A manifest without `environment.with` runs from the repository's own `.venv`.

## What is not here yet

- Apptainer definitions for the SWE-bench evaluation images (phase 7).
- vLLM serving for the larger rerankers and agents (phases 11 and 6).

## fresh-2026 with SweRank's retrievers (ADR 0033, tier T1)

On the laptop, after the set is sealed: `uv run python scripts/swerank_export.py --set fresh --out ../swerank-fresh`, then copy `../swerank-fresh` to `$HOME/scratch/swerank/fresh` on PACE. Models are downloaded onto the node at the start of the job (see below).

```bash
sbatch --gres=gpu:1 --time=4:00:00 --export=ALL,TAG=embed-large,DATA=fresh,MODEL=Salesforce/SweRankEmbed-Large,REVISION=b2cbc7dd3a2aed8c268fa65673464cd5ad96f9ff cluster/swerank/retrieve_fresh.sbatch
sbatch --gres=gpu:1 --time=2:00:00 --export=ALL,TAG=embed-small,DATA=fresh,MODEL=Salesforce/SweRankEmbed-Small,REVISION=745d2a06103a66d3cfa600aa52fc0d3523010daa cluster/swerank/retrieve_fresh.sbatch
```

Instead of copying the export (about 16 GB), PACE can build it: `sbatch --partition=coc-cpu --cpus-per-task=8 --mem=32G --time=4:00:00 cluster/swerank/export_fresh.sbatch` writes `$HOME/scratch/swerank/fresh`, fetching each bug's repository as it goes and skipping bugs a previous run already wrote, so a job that hits its time limit can simply be resubmitted; submit the retrievers with `--dependency=afterok:<that job>` so they start when it finishes.

Bring `out/fresh-<tag>/results.json` back and run `uv run python scripts/swerank_import.py --set fresh --system swerank-<tag> --model <model@revision> --results <file>`. The LLM rerankers still read SWE-bench Lite's layout through the authors' scripts and are not wired to fresh-2026 yet.

## Models on node-local disk

I tested it on 2026-11-04: compute nodes on the `coc-gpu` partition (account `coc`, QOS `coc-ice`) reach Hugging Face, PyPI and GitHub, and have about 1.7 TB free in `$TMPDIR` (`/tmp`), against a 300 GB scratch quota. So `cluster/stage_models.sh` puts each job's models in its own folder on that local disk: it copies a model from the permanent store on scratch if one is there, and otherwise downloads it on the node, at the job's `REVISION` when one is set. It then points `HF_HOME` at the folder, switches Hugging Face to offline mode, and deletes the folder when the job ends, because `/tmp` is not guaranteed to be wiped between jobs. Large models therefore never need to be on scratch. A permanent copy on scratch is still worth keeping for a small model used by many jobs, downloaded once on the login node:

```bash
export HF_HOME=$HOME/scratch/odin-cache/huggingface
huggingface-cli download Salesforce/SweRankEmbed-Large --revision b2cbc7dd3a2aed8c268fa65673464cd5ad96f9ff
huggingface-cli download Salesforce/SweRankEmbed-Small --revision 745d2a06103a66d3cfa600aa52fc0d3523010daa
```

A job script stages what it needs with `. "$HOME/scratch/Odin/cluster/stage_models.sh"` and `stage_models <repo id> [...]`. Results are written straight to scratch, so nothing is lost when local disk is wiped.

## fresh-2026 with open-weight models (ADR 0033, open-model tier)

Once, on the login node:

```bash
uv venv --python 3.12 $HOME/scratch/vllm-env && uv pip install --python $HOME/scratch/vllm-env/bin/python vllm
export HF_HOME=$HOME/scratch/odin-cache/huggingface
huggingface-cli download Qwen/Qwen3-Coder-Next       # note the commit it prints and use it as REVISION
huggingface-cli download openai/gpt-oss-120b
cd $HOME/scratch/Odin && git pull && uv run python scripts/frontier.py prepare --set fresh-agents
```

`prepare` downloads each repository and every file at each bug's base commit, so the job can check them out offline; the checkouts themselves are made on the node's local disk during the job, not on scratch. Check the model ids and the tool-call parser names against `vllm serve --help` for the installed vLLM before submitting.

```bash
sbatch --gres=gpu:A100:1 --time=24:00:00 --export=ALL,SET=fresh-agents,TAG=qwen3-coder-next,MODEL=Qwen/Qwen3-Coder-Next,REVISION=<commit>,PARSER=qwen3_coder cluster/open_models/run.sbatch
sbatch --gres=gpu:A100:1 --time=24:00:00 --export=ALL,SET=fresh-agents,TAG=gpt-oss-120b,MODEL=openai/gpt-oss-120b,REVISION=<commit>,PARSER=openai cluster/open_models/run.sbatch
```

Each job serves the model with vLLM on its own GPU, then runs the read-only agent and the one-call variant on the 198-bug agent subsample. The runs are resumable; if a job hits its time limit, submit it again. Bring `results/research/frontier/fresh-agents_open-*.jsonl` and the new lines of `results/test-evals.log` back to the laptop.

## The six-language reranker candidates (ADR 0034, step 2)

On the laptop first: `uv run python scripts/website_rerank.py tasks --multilang` and `uv run python scripts/ce_multilang.py records`, then copy `results/website-rerank/work/tasks.jsonl`, `tasks_multilang.jsonl` and `ce_records.jsonl` to the same folder on PACE by hand: `results/website-rerank/work/` is in `.gitignore`, so a pull does not bring them. On the login node, download the bases once:

```bash
export HF_HOME=$HOME/scratch/odin-cache/huggingface
huggingface-cli download Qwen/Qwen3-Reranker-0.6B
huggingface-cli download Qwen/Qwen3-Reranker-4B
```

Then one array job per candidate, five folds each (A and B fit an A100 40 GB; C wants an A100 80 GB or an H100):

```bash
sbatch --array=0-4 --gres=gpu:A100:1 --time=8:00:00 --export=ALL,CANDIDATE=A cluster/ce_multilang/fold.sbatch
sbatch --array=0-4 --gres=gpu:A100:1 --time=12:00:00 --export=ALL,CANDIDATE=B cluster/ce_multilang/fold.sbatch
sbatch --array=0-4 --gres=gpu:H100:1 --time=24:00:00 --export=ALL,CANDIDATE=C cluster/ce_multilang/fold.sbatch
```

Each fold writes its held-out scores to `results/website-rerank/work/scores_cand-<X>.fold<k>.jsonl`; when all five are in, run `scripts/ce_multilang.py merge --candidate <X>`, bring the merged file back and evaluate on the laptop. The chosen candidate is then trained on every project with `--export=ALL,CANDIDATE=<X>,FOLD=all`.
