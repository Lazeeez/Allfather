"""Open-weight models as bug localizers through a vLLM server (ADR 0033, open-model tier).

The agent gets the same three read-only abilities Claude Code gets in scripts/frontier.py: list
files by glob, search file contents, and read a range of lines. Every path is confined to the
bug's checkout. The single-call variant gets no tools. The server is any OpenAI-compatible
endpoint, normally `vllm serve` on the PACE node the job runs on, named by OPEN_MODEL_URL.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_TURNS = 40
MAX_RESULTS = 200
MAX_LINES = 400
SOURCE = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".rs",
    ".md",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".cfg",
}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in the repository matching a glob pattern, such as src/**/*.py.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents with a regular expression; optionally only files matching a glob.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}, "glob": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read lines start_line to end_line (1-based, inclusive) of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
]


def inside(root: Path, rel: str) -> Path | None:
    path = (root / rel.lstrip("/")).resolve()
    return path if path.is_relative_to(root.resolve()) and path.is_file() else None


def matches(root: Path, pattern: str | None) -> list[Path]:
    pattern = pattern or "**/*"
    if (
        ".." in Path(pattern).parts
        or Path(pattern).is_absolute()
        or pattern.startswith(("/", "\\"))
    ):
        return []
    base = root.resolve()
    try:
        found = list(root.glob(pattern))
    except (NotImplementedError, ValueError):
        return []
    return sorted(p for p in found if p.is_file() and p.resolve().is_relative_to(base))


def list_files(root: Path, pattern: str) -> str:
    found = [p.relative_to(root).as_posix() for p in matches(root, pattern)]
    return "\n".join(found[:MAX_RESULTS]) + (
        f"\n... {len(found) - MAX_RESULTS} more" if len(found) > MAX_RESULTS else ""
    )


def grep(root: Path, pattern: str, glob: str | None) -> str:
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return f"invalid pattern: {exc}"
    hits = []
    for p in matches(root, glob):
        if p.suffix not in SOURCE or p.stat().st_size > 1_000_000:
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p.relative_to(root).as_posix()}:{n}: {line.strip()[:200]}")
                if len(hits) >= MAX_RESULTS:
                    return "\n".join(hits) + "\n... more matches not shown"
    return "\n".join(hits) or "no matches"


def read_file(root: Path, path: str, start: int | None, end: int | None) -> str:
    target = inside(root, path)
    if target is None:
        return f"no such file: {path}"
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    first = max(1, start or 1)
    last = min(len(lines), end or first + MAX_LINES - 1, first + MAX_LINES - 1)
    return "\n".join(f"{i}: {lines[i - 1]}" for i in range(first, last + 1))


def line_number(value: object) -> int | None:
    try:
        return int(float(value)) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def call_tool(root: Path, name: str, raw: str) -> str:
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return "arguments were not valid JSON"
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    try:
        if name == "list_files":
            return list_files(root, str(args.get("pattern", "")))
        if name == "grep":
            return grep(root, str(args.get("pattern", "")), args.get("glob"))
        if name == "read_file":
            return read_file(
                root,
                str(args.get("path", "")),
                line_number(args.get("start_line")),
                line_number(args.get("end_line")),
            )
    except Exception as exc:  # noqa: BLE001
        return f"the tool failed: {type(exc).__name__}: {exc}"
    return f"unknown tool {name}"


def chat(model: str, messages: list[dict], tools: list[dict] | None) -> dict:
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": 4096}
    if tools:
        body["tools"] = tools
    request = urllib.request.Request(
        f"{os.environ['OPEN_MODEL_URL'].rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", "replace")
        if exc.code == 400 and re.search(
            r"context|maximum.{0,40}length|too long|max_model_len", message, re.I
        ):
            raise ContextFull(message[:300]) from exc
        raise


class ContextFull(RuntimeError):
    pass


def run(prompt: str, cwd: Path, model: str, agent: bool, parse_answer) -> dict:
    messages = [{"role": "user", "content": prompt}]
    tokens = {"prompt_tokens": 0, "completion_tokens": 0}
    tools_used: list[str] = []
    start = time.perf_counter()
    for turn in range(1, (MAX_TURNS if agent else 1) + 1):
        try:
            reply = chat(model, messages, TOOLS if agent else None)
        except ContextFull as exc:
            return {
                "answer": None,
                "model": model,
                "cost_usd": None,
                "usage": tokens | {"gpu_seconds": round(time.perf_counter() - start, 1)},
                "turns": turn,
                "tools": sorted(set(tools_used)),
                "error": None,
                "no_answer": f"context full at turn {turn}: {exc}",
            }
        for k in tokens:
            tokens[k] += (reply.get("usage") or {}).get(k, 0)
        message = reply["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            return {
                "answer": parse_answer(message.get("content") or ""),
                "model": reply.get("model", model),
                "cost_usd": None,
                "usage": tokens | {"gpu_seconds": round(time.perf_counter() - start, 1)},
                "turns": turn,
                "tools": sorted(set(tools_used)),
                "error": None,
            }
        messages.append(
            {"role": "assistant", "content": message.get("content") or "", "tool_calls": calls}
        )
        for c in calls:
            name = c["function"]["name"]
            tools_used.append(name)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": c["id"],
                    "content": call_tool(cwd, name, c["function"].get("arguments", ""))[:20000],
                }
            )
    return {
        "answer": None,
        "model": model,
        "cost_usd": None,
        "usage": tokens,
        "turns": MAX_TURNS,
        "tools": sorted(set(tools_used)),
        "error": None,
        "no_answer": f"no answer after {MAX_TURNS} turns",
    }
