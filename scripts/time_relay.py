"""Time whole-repository downloads through the site's relay.

    uv run python scripts/time_relay.py

Downloads each repository's .tar.gz at its current default-branch commit through
https://allfather.dev/relay three times and records the wall time and size of each. The first
download may miss Cloudflare's cache; later ones show the cached path. Network speed is the
laptop's own, so the file records it as measured, not as a property of the relay alone.
"""

from __future__ import annotations

import json
import platform
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SITE = "https://allfather.dev"
REPOS = ["huggingface/transformers", "home-assistant/core", "python/cpython", "django/django"]
RUNS = 3
OUT = Path("results/perf") / f"relay_{datetime.now(UTC):%Y-%m-%d}.json"


def head_commit(repo: str) -> str:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/commits/HEAD",
        headers={"Accept": "application/vnd.github.sha", "User-Agent": "allfather-time-relay"},
    )
    with urllib.request.urlopen(request, timeout=60) as r:
        return r.read().decode().strip()


def download(repo: str, sha: str) -> tuple[float, int]:
    request = urllib.request.Request(
        f"{SITE}/relay/{repo}/{sha}",
        headers={"Origin": SITE, "User-Agent": "allfather-time-relay"},
    )
    start = time.perf_counter()
    size = 0
    with urllib.request.urlopen(request, timeout=600) as r:
        while chunk := r.read(1 << 20):
            size += len(chunk)
    return time.perf_counter() - start, size


def main() -> int:
    rows = []
    for repo in REPOS:
        sha = head_commit(repo)
        runs = [download(repo, sha) for _ in range(RUNS)]
        rows.append(
            {
                "repo": repo,
                "commit": sha,
                "seconds": [round(s, 2) for s, _ in runs],
                "megabytes": round(runs[0][1] / 1e6, 1),
            }
        )
        print(rows[-1], flush=True)
    OUT.write_text(
        json.dumps(
            {
                "measured": datetime.now(UTC).isoformat(timespec="seconds"),
                "relay": f"{SITE}/relay",
                "client": platform.platform(),
                "note": "wall time of the whole download from this laptop's connection; the first run may miss Cloudflare's cache",
                "repos": rows,
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
