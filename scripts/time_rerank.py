"""Time the site's GPU reranker the way the browser calls it.

    uv run python scripts/time_rerank.py

Sends one request shaped like the browser's (a bug report and the text of 50 functions, here this
repository's own Python functions) to https://allfather.dev/rerank, then four more. Each request
carries a unique report, so none is answered from the one-day score cache. The first call shows
the start-up cost when no container is running; the rest are warm. Times include the network from
this laptop and the Worker hop.
"""

from __future__ import annotations

import ast
import json
import platform
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SITE = "https://allfather.dev"
OUT = Path("results/perf") / f"rerank_{datetime.now(UTC):%Y-%m-%d}.json"
CALLS = 5


def functions(limit: int = 50) -> list[str]:
    out = []
    for path in sorted(Path("src/allfather").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef):
                out.append(f"{path.as_posix()}\n{ast.get_source_segment(source, node)}")
                if len(out) == limit:
                    return out
    return out


def call(report: str, texts: list[str]) -> float:
    body = json.dumps({"query": report, "texts": texts}).encode()
    request = urllib.request.Request(
        f"{SITE}/rerank",
        data=body,
        headers={
            "Origin": SITE,
            "Content-Type": "application/json",
            "User-Agent": "allfather-time-rerank",
        },
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as r:
        scores = json.loads(r.read())["scores"]
    elapsed = time.perf_counter() - start
    if len(scores[0]) != len(texts):
        raise SystemExit(f"expected {len(texts)} scores, got {len(scores[0])}")
    return elapsed


def main() -> int:
    texts = functions()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    seconds = []
    for i in range(CALLS):
        report = f"paired_bootstrap returns the wrong p-value when every difference is zero (timing run {stamp} #{i})"
        seconds.append(round(call(report, texts), 2))
        print(f"call {i + 1}: {seconds[-1]} s", flush=True)
    OUT.write_text(
        json.dumps(
            {
                "measured": stamp,
                "endpoint": f"{SITE}/rerank",
                "client": platform.platform(),
                "functions": len(texts),
                "note": "wall time per request from this laptop; the first call follows an idle period, so it may include a container start",
                "seconds": seconds,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
