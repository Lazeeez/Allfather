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
import tempfile
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
WORK = Path(
    os.environ.get("FRONTIER_WORK")
    or (
        Path(tempfile.gettempdir()) / "af"
        if sys.platform == "win32"
        else ROOT / ".cache" / "frontier"
    )
)
GOLD = ROOT / "data" / "gold" / "swebench_verified_test.jsonl"
FRESH = ROOT / "data" / "fresh"
LITE = ROOT / "data" / "gold" / "swebench_lite_test.jsonl"
TIMEOUT_S = 1200
MAX_PATH = 240 if sys.platform == "win32" else 4096
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
    log_path = ROOT / "results" / "test-evals.log"
    if not name.startswith(
        "fresh"
    ) or f"| {path.relative_to(ROOT).as_posix()} |" in log_path.read_text(encoding="utf-8"):
        return
    with log_path.open("a", encoding="utf-8", newline="\n") as log:
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
    partial = target.with_name(f"{target.name}.partial-{os.getpid()}")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    with tarfile.open(fileobj=BytesIO(tar)) as archive:
        members = [m for m in archive.getmembers() if len(str(partial / m.name)) < MAX_PATH]
        archive.extractall(partial, members=members, filter="data")
    partial.rename(target)


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
    data = last_json(done.stdout) or {}
    message = str(data.get("result") or done.stderr or "")
    if (data.get("is_error") or not data) and re.search(
        r"usage limit|rate limit|quota|limit reached|resets", message, re.I
    ):
        raise QuotaExhausted(message[:200])
    if not data:
        raise json.JSONDecodeError("no JSON from claude", done.stdout or "", 0)
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
    if not data:
        raise json.JSONDecodeError(
            f"no JSON from gemini: {done.stderr.strip()[-200:]}", done.stdout or "", 0
        )
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


def gemini_api(prompt: str, cwd: Path, model: str, agent: bool) -> dict:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": ANSWER,
        },
    }
    for attempt in range(3):
        request = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(),
            headers={
                "x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            data = json.loads(urllib.request.urlopen(request, timeout=TIMEOUT_S).read())
            break
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", "replace")
            if exc.code == 429 and re.search(r"PerDay|per day", message):
                raise QuotaExhausted(message[:300]) from exc
            if exc.code == 503:
                raise QuotaExhausted(f"Gemini overloaded, try later: {message[:200]}") from exc
            if exc.code in (429, 500) and attempt < 2:
                time.sleep(65)
                continue
            return {"answer": None, "error": f"HTTP {exc.code}: {message[:300]}"}
    candidate = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (candidate.get("content") or {}).get("parts", []))
    return {
        "answer": parse_answer(text),
        "model": data.get("modelVersion") or model,
        "cost_usd": None,
        "usage": data.get("usageMetadata"),
        "turns": 1,
        "tools": [],
        "error": None if text else f"no text, finish reason {candidate.get('finishReason')}",
    }


def parse_answer(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def codex(prompt: str, cwd: Path, model: str, agent: bool) -> dict:
    if agent and sys.platform == "win32":
        sys.exit("codex-agent needs a real read-only sandbox; run it under WSL or Linux")
    WORK.mkdir(parents=True, exist_ok=True)
    schema = WORK / "answer_schema.json"
    schema.write_text(json.dumps(ANSWER), encoding="utf-8")
    command = [
        shutil.which("codex") or "codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
        "--ignore-user-config", "--ignore-rules", "-s", "read-only", "-m", model,
        "-c", 'web_search="disabled"', "-c", 'model_reasoning_effort="medium"',
        "--output-schema", str(schema),
        *([] if agent else ["--disable", "shell_tool"]), "-",
    ]  # fmt: skip
    done = launch(command, prompt, cwd, ("OPENAI_API_KEY",))
    events = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    failures = [
        str(e.get("message") or e.get("error"))
        for e in events
        if e["type"] in ("error", "turn.failed")
    ]
    if done.returncode:
        failures.append(done.stderr.strip()[-300:])
    if any(
        re.search(
            r"usage limit|rate limit|quota|try again (at|in)|token_revoked|HTTP 401|log ?in again",
            f,
            re.I,
        )
        for f in failures
    ):
        raise QuotaExhausted(failures[-1][:300])
    if any(
        re.search(r"context.{0,20}(window|length|limit)|too.(long|large)|maximum length", f, re.I)
        for f in failures
    ):
        return {"answer": None, "model": model, "error": None, "too_long": failures[-1][:300]}
    items = [e["item"] for e in events if e["type"] == "item.completed"]
    messages = [i["text"] for i in items if i.get("type") == "agent_message"]
    if not events:
        raise json.JSONDecodeError(f"no JSON from codex: {done.stderr.strip()[-200:]}", "", 0)
    return {
        "answer": parse_answer(messages[-1]) if messages else None,
        "model": model,
        "cost_usd": None,
        "usage": next((e["usage"] for e in events if e["type"] == "turn.completed"), None),
        "turns": None,
        "tools": sorted({i["type"] for i in items if i.get("type") != "agent_message"}),
        "error": failures[-1][:300] if failures and not messages else None,
    }


def open_model(prompt: str, cwd: Path, model: str, agent: bool) -> dict:
    import open_agent

    return open_agent.run(prompt, cwd, model, agent, parse_answer)


SYSTEMS = {
    "claude-agent": (claude, "opus", True),
    "claude-single": (claude, "opus", False),
    "gemini-agent": (gemini, "gemini-3.8-flash", True),
    "gemini-single": (gemini_api, "gemini-3.8-flash", False),
    "open-agent": (open_model, "", True),
    "open-single": (open_model, "", False),
    "codex-agent": (codex, "gpt-6-luna", True),
    "codex-single": (codex, "gpt-6-luna", False),
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


def cmd_prepare(args: argparse.Namespace) -> int:
    ids, items = load_set(args.set)
    cache = RepoCache(ROOT / ".cache" / "repos")
    for n, q in enumerate(ids, 1):
        item = items[q]
        entries = cache.list_tree(item["repo"], item["base_commit"])
        cache.prefetch_blobs(item["repo"], [f"{item['base_commit']}:{e.path}" for e in entries])
        print(f"  {n}/{len(ids)} {q}: {len(entries)} files", flush=True)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.system.startswith("gemini") and not args.allow_billing and not free_tier_only():
        sys.exit(
            "GEMINI_API_KEY is not limited to the free tier (a paid model answered); pass --allow-billing to run anyway"
        )
    issues, items = load_set(args.set)
    runner, model, agent = SYSTEMS[args.system]
    model = args.model or model
    name = f"{args.system}-{args.tag}" if args.tag else args.system
    target = OUT / f"{args.set}_{name}.jsonl"
    done = (
        {json.loads(line)["id"] for line in target.open(encoding="utf-8")}
        if target.exists()
        else set()
    )
    cache = RepoCache(ROOT / ".cache" / "repos")
    if not done:
        log_test_run(args.set, name, model, target)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        for q in issues[: args.limit or None]:
            if q in done:
                continue
            item = items[q]
            cwd = WORK / name / re.sub(r"[^\w.-]", "_", q)
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
                "id": q, "system": name, "requested_model": model, "date": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": round(time.perf_counter() - start, 1), **record,
                "web_tool_used": any(WEB_TOOLS.search(t) for t in record.get("tools") or []),
            }  # fmt: skip
            if record.get("error") and not str(record["error"]).startswith("timed out"):
                with target.with_suffix(".errors.jsonl").open(
                    "a", encoding="utf-8", newline="\n"
                ) as errors:
                    errors.write(json.dumps(record) + "\n")
                print(f"  {q}: error, kept for a retry: {str(record['error'])[:120]}", flush=True)
                shutil.rmtree(cwd, ignore_errors=True)
                continue
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
    rn.add_argument(
        "--tag", help="added to the system name in the output file, e.g. the open model"
    )
    rn.add_argument("--limit", type=int, default=0)
    rn.add_argument("--keep", action="store_true")
    rn.add_argument("--allow-billing", action="store_true")
    pp = sub.add_parser("prepare")
    pp.add_argument("--set", required=True)
    sc = sub.add_parser("score")
    sc.add_argument("--set", required=True)
    args = ap.parse_args()
    return {"pick": cmd_pick, "prepare": cmd_prepare, "run": cmd_run, "score": cmd_score}[args.cmd](
        args
    )


if __name__ == "__main__":
    raise SystemExit(main())
