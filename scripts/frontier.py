"""Run frontier coding agents and models as bug localizers (ADR 0033, tiers T3 and T4).

    uv run python scripts/frontier.py pick --set pilot --n 10
    uv run python scripts/frontier.py run --set pilot --system claude-agent
    uv run python scripts/frontier.py score --set pilot

pick: a seeded sample of development issues (SWE-bench Verified minus Lite), never a test set.
run: for each issue, export the repository at its base commit with no git history, then ask the
system for the ten functions most likely to need the fix. Agents get read-only file tools and no
web access; single-call systems get no tools. Every run records the model, tokens, the
list-price cost the tool reports, wall time and the tools it used. Resumable.
score: hit@k, all@10 and MRR against the answer key, the unmapped-answer rate, and cost.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from allfather.eval.dataset import load_instances  # noqa: E402
from allfather.eval.metrics import aggregate, score  # noqa: E402
from allfather.parsing.symbols import is_test_path  # noqa: E402
from allfather.repos import RepoCache  # noqa: E402

OUT = ROOT / "results" / "research" / "frontier"
WORK = ROOT / ".cache" / "frontier"
GOLD = ROOT / "data" / "gold" / "swebench_verified_test.jsonl"
FRESH = ROOT / "data" / "fresh"
LITE = ROOT / "data" / "gold" / "swebench_lite_test.jsonl"
TIMEOUT_S = 1200
ANSWER = {
    "type": "object",
    "properties": {
        "functions": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {"file": {"type": "string"}, "name": {"type": "string"}},
                "required": ["file", "name"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["functions"],
    "additionalProperties": False,
}
PROMPT = """You are localizing a bug. The repository is in the current directory, checked out at the commit where the bug was reported.

Read the bug report, explore the code with the read-only tools you have, and decide which functions or methods must change to fix it. Do not edit anything and do not try to run code.

Answer with JSON only, in this shape, at most 10 entries, the most likely first:
{{"functions": [{{"file": "path/relative/to/repo.py", "name": "ClassName.method_name or function_name"}}]}}

Bug report:
{report}
"""
SINGLE = """You are localizing a bug in {repo}. You cannot open files; below are the bug report and the list of the repository's source files at the commit where the bug was reported.

Decide which functions or methods must change to fix it. Answer with JSON only, in this shape, at most 10 entries, the most likely first:
{{"functions": [{{"file": "path/relative/to/repo.py", "name": "ClassName.method_name or function_name"}}]}}

Bug report:
{report}

Source files:
{files}
"""
WEB_TOOLS = re.compile(r"web|search_google|google_web_search|fetch", re.I)


def gold_rows() -> dict[str, dict]:
    return {
        json.loads(line)["instance_id"]: json.loads(line) for line in GOLD.open(encoding="utf-8")
    }


def load_set(name: str) -> tuple[list[str], dict[str, dict]]:
    if name.startswith("fresh"):
        manifest = json.loads((FRESH / "manifest.json").read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in (FRESH / "gold.jsonl").open(encoding="utf-8")]
        items = {
            r["id"]: {
                "repo": r["repo"],
                "base_commit": r["base_commit"],
                "text": r["text"],
                "gold": r["gold_functions"],
            }
            for r in rows
        }
        ids = (
            manifest["agent_subsample"]
            if name == "fresh-agents"
            else [i["id"] for i in manifest["instances"]]
        )
        return ids, items
    issues = json.loads((OUT / f"{name}_issues.json").read_text(encoding="utf-8"))["issues"]
    text = {i.instance_id: i.problem_statement for i in load_instances("verified", "test")}
    gold = gold_rows()
    items = {
        q: {
            "repo": gold[q]["repo"],
            "base_commit": gold[q]["base_commit"],
            "text": text[q],
            "gold": gold[q]["functions"],
        }
        for q in issues
    }
    return issues, items


def log_test_run(name: str, system: str, model: str, path: Path) -> None:
    if not name.startswith("fresh"):
        return
    with (ROOT / "results" / "test-evals.log").open("a", encoding="utf-8", newline="\n") as log:
        log.write(
            f"{datetime.now(UTC).date().isoformat()} | {name} | {system} ({model}) | function | {path.relative_to(ROOT).as_posix()} | "
            "ADR 0033 run on the sealed fresh-2026 set; nothing decided from it\n"
        )


def cmd_pick(args: argparse.Namespace) -> int:
    lite = {json.loads(line)["instance_id"] for line in LITE.open(encoding="utf-8")}
    gold = gold_rows()
    pool = sorted(
        q for q, g in gold.items() if q not in lite and g["functions"] and not g["errors"]
    )
    chosen = sorted(random.Random(args.seed).sample(pool, args.n))
    path = OUT / f"{args.set}_issues.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "set": args.set,
                "source": "SWE-bench Verified minus Lite (development)",
                "seed": args.seed,
                "issues": chosen,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {path}: {len(chosen)} issues")
    return 0


def export(cache: RepoCache, repo: str, commit: str, target: Path) -> None:
    if target.exists():
        return
    mirror = cache.ensure_commit(repo, commit)
    tar = subprocess.run(
        ["git", "--git-dir", str(mirror), "archive", commit], capture_output=True, check=True
    ).stdout
    target.mkdir(parents=True)
    with tarfile.open(fileobj=BytesIO(tar)) as archive:
        archive.extractall(target, filter="data")


def source_files(root: Path) -> str:
    suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rs"}
    return "\n".join(
        sorted(
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.suffix in suffixes and not is_test_path(p.relative_to(root).as_posix())
        )
    )


NPM = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules"
CLAUDE = (
    str(NPM / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe")
    if sys.platform == "win32"
    else "claude"
)
GEMINI = (
    ["node", str(NPM / "@google" / "gemini-cli" / "bundle" / "gemini.js")]
    if sys.platform == "win32"
    else ["gemini"]
)


def launch(
    command: list[str], prompt: str, cwd: Path, drop: tuple[str, ...]
) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in drop}
    return subprocess.run(
        command,
        input=prompt,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        encoding="utf-8",
    )


def claude(prompt: str, cwd: Path, model: str, agent: bool) -> dict:
    command = [
        CLAUDE, "-p", "--model", model, "--output-format", "json",
        "--json-schema", json.dumps(ANSWER), "--tools", "Read,Grep,Glob" if agent else "",
        "--strict-mcp-config", "--setting-sources", "project", "--no-session-persistence",
    ]  # fmt: skip
    done = launch(command, prompt, cwd, ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"))
    data = json.loads(done.stdout)
    answer = data.get("structured_output") or parse_answer(data.get("result", ""))
    return {
        "answer": answer,
        "model": ",".join(data.get("modelUsage", {}) or [model]),
        "cost_usd": data.get("total_cost_usd"),
        "usage": data.get("usage"),
        "turns": data.get("num_turns"),
        "tools": [],
        "error": data.get("is_error") and data.get("result"),
    }


def gemini(prompt: str, cwd: Path, model: str, agent: bool) -> dict:
    settings = cwd / ".gemini" / "settings.json"
    settings.parent.mkdir(exist_ok=True)
    exclude = [
        "google_web_search",
        "web_fetch",
        "run_shell_command",
        "write_file",
        "replace",
        "save_memory",
    ]
    if not agent:
        exclude += [
            "read_file",
            "read_many_files",
            "list_directory",
            "glob",
            "search_file_content",
            "grep",
        ]
    settings.write_text(
        json.dumps(
            {
                "tools": {"exclude": exclude},
                "security": {"auth": {"selectedType": "gemini-api-key"}},
            }
        ),
        encoding="utf-8",
    )
    command = [
        *GEMINI,
        "-p",
        " ",
        "-m",
        model,
        "-o",
        "json",
        "--approval-mode",
        "plan",
        "--skip-trust",
    ]
    done = launch(
        command,
        prompt,
        cwd,
        ("GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT"),
    )
    data = last_json(done.stdout) or last_json(done.stderr) or {}
    error = data.get("error") or {}
    if "quota" in str(error.get("message", "")).lower() or "free_tier_requests" in done.stderr:
        raise QuotaExhausted(str(error.get("message") or "free-tier quota exhausted"))
    stats = data.get("stats", {})
    tools = sorted((stats.get("tools", {}) or {}).get("byName", {}) or {})
    return {
        "answer": parse_answer(data.get("response", "")),
        "model": ",".join((stats.get("models", {}) or {}).keys()) or model,
        "cost_usd": None,
        "usage": stats.get("models"),
        "turns": None,
        "tools": tools,
        "error": data.get("error"),
    }


def parse_answer(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


SYSTEMS = {
    "claude-agent": (claude, "opus", True),
    "claude-single": (claude, "opus", False),
    "gemini-agent": (gemini, "gemini-3.8-flash", True),
    "gemini-single": (gemini, "gemini-3.8-flash", False),
}


class QuotaExhausted(RuntimeError):
    pass


def last_json(text: str) -> dict | None:
    for start in [
        i for i, c in enumerate(text or "") if c == "{" and (i == 0 or text[i - 1] == "\n")
    ][::-1]:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            continue
    return None


def free_tier_only() -> bool:
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent",
        data=json.dumps(
            {"contents": [{"parts": [{"text": "ok"}]}], "generationConfig": {"maxOutputTokens": 1}}
        ).encode(),
        headers={
            "x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=60).read()
    except urllib.error.HTTPError as exc:
        return exc.code == 429 and "FreeTier" in exc.read().decode("utf-8", "replace")
    return False


def cmd_run(args: argparse.Namespace) -> int:
    if args.system.startswith("gemini") and not args.allow_billing and not free_tier_only():
        sys.exit(
            "GEMINI_API_KEY is not limited to the free tier (a paid model answered); pass --allow-billing to run anyway"
        )
    issues, items = load_set(args.set)
    runner, model, agent = SYSTEMS[args.system]
    model = args.model or model
    target = OUT / f"{args.set}_{args.system}.jsonl"
    done = (
        {json.loads(line)["id"] for line in target.open(encoding="utf-8")}
        if target.exists()
        else set()
    )
    cache = RepoCache(ROOT / ".cache" / "repos")
    if not done:
        log_test_run(args.set, args.system, model, target)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        for q in issues[: args.limit or None]:
            if q in done:
                continue
            item = items[q]
            cwd = WORK / re.sub(r"[^\w.-]", "_", q)
            export(cache, item["repo"], item["base_commit"], cwd)
            prompt = (PROMPT if agent else SINGLE).format(
                report=item["text"], repo=item["repo"], files=source_files(cwd)
            )
            start = time.perf_counter()
            try:
                record = runner(prompt, cwd, model, agent)
            except QuotaExhausted as exc:
                print(f"  stopped: {exc}", flush=True)
                break
            except subprocess.TimeoutExpired:
                record = {"answer": None, "error": f"timed out after {TIMEOUT_S} s"}
            except (json.JSONDecodeError, subprocess.CalledProcessError) as exc:
                record = {"answer": None, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            record = {
                "id": q, "system": args.system, "requested_model": model, "date": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": round(time.perf_counter() - start, 1), **record,
                "web_tool_used": any(WEB_TOOLS.search(t) for t in record.get("tools") or []),
            }  # fmt: skip
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            print(
                f"  {q}: {len(((record.get('answer') or {}).get('functions')) or [])} functions, {record['seconds']} s, {record.get('error') or 'ok'}",
                flush=True,
            )
            if not args.keep:
                shutil.rmtree(cwd, ignore_errors=True)
    return 0


def unit_ids(answer: dict | None) -> list[str]:
    out = []
    for f in (answer or {}).get("functions", [])[:10]:
        path = str(f.get("file", "")).strip().lstrip("./").replace("\\", "/")
        name = str(f.get("name", "")).strip().replace("::", ".")
        if path and name:
            out.append(f"{path}::{name}")
    return out


def matched(ranked: list[str], gold: list[str]) -> list[str]:
    out = []
    for unit in ranked:
        path, name = unit.split("::", 1)
        exact = next((g for g in gold if g == unit), None)
        tail = [
            g
            for g in gold
            if g.split("::", 1)[0] == path
            and g.split("::", 1)[1].split(".")[-1] == name.split(".")[-1]
        ]
        out.append(exact or (tail[0] if len(tail) == 1 else unit))
    return out


def cmd_score(args: argparse.Namespace) -> int:
    _, items = load_set(args.set)
    for path in sorted(OUT.glob(f"{args.set}_*.jsonl")):
        rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        rows = [r for r in rows if items[r["id"]]["gold"]]
        scores = [
            score(
                matched(unit_ids(r.get("answer")), items[r["id"]]["gold"]),
                items[r["id"]]["gold"],
                [1, 5, 10],
            )
            for r in rows
        ]
        summary = aggregate(scores, [1, 5, 10])
        costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
        print(
            f"{path.stem:28} n={summary['n']}  hit@1 {summary['hit@1']:.2f}  hit@5 {summary['hit@5']:.2f}  hit@10 {summary['hit@10']:.2f}  "
            f"all@10 {summary['all@10']:.2f}  MRR {summary['mrr']:.2f}  no answer {sum(1 for r in rows if not unit_ids(r.get('answer')))}  "
            f"web {sum(1 for r in rows if r.get('web_tool_used'))}  mean cost {sum(costs) / len(costs) if costs else float('nan'):.3f} USD  "
            f"mean time {sum(r.get('seconds') or 0 for r in rows) / len(rows):.0f} s"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pk = sub.add_parser("pick")
    pk.add_argument("--set", required=True)
    pk.add_argument("--n", type=int, default=10)
    pk.add_argument("--seed", type=int, default=0)
    rn = sub.add_parser("run")
    rn.add_argument("--set", required=True)
    rn.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    rn.add_argument("--model")
    rn.add_argument("--limit", type=int, default=0)
    rn.add_argument("--keep", action="store_true")
    rn.add_argument("--allow-billing", action="store_true")
    sc = sub.add_parser("score")
    sc.add_argument("--set", required=True)
    args = ap.parse_args()
    return {"pick": cmd_pick, "run": cmd_run, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
