"""Run the website's own pipeline (ADR 0033, tier T0) on a set from scripts/frontier.py.

    uv run python scripts/fresh_website.py --set pilot
    uv run python scripts/fresh_website.py --set fresh

The same ranking the live-accuracy monitor runs (browser rankers, semantic and language-model
stages, no GPU reranker), in all six languages. Writes results/research/frontier/<set>_website.jsonl
in the shape scripts/frontier.py scores. Resumable.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from frontier import OUT, load_set, log_test_run  # noqa: E402
from live_eval import Site  # noqa: E402

from allfather.eval.dataset import Instance  # noqa: E402
from allfather.rank.confidence import confidence_features, predict_confidence  # noqa: E402

CONFIDENCE = ROOT / "web" / "src" / "assets" / "confidence.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    args = ap.parse_args()
    ids, items = load_set(args.set)
    target = OUT / f"{args.set}_website.jsonl"
    done = (
        {json.loads(line)["id"] for line in target.open(encoding="utf-8")}
        if target.exists()
        else set()
    )
    site = Site()
    model = json.loads(CONFIDENCE.read_text(encoding="utf-8"))
    if not done:
        log_test_run(args.set, "website", f"ranker {site.sha[:12]}", target)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        for q in ids:
            if q in done or not items[q]["gold"]:
                continue
            item = items[q]
            inst = Instance(q, item["repo"], item["base_commit"], "", item["text"])
            start = time.perf_counter()
            site.last_semantic = None
            ranked, _, units = site.rank(inst, set(item["gold"]), set())
            sure = None
            if site.last_semantic is not None:
                s_b, X, chars = site.last_semantic
                sure = round(
                    float(predict_confidence(model, confidence_features(s_b, X, chars))[0]), 4
                )
            top = [{"file": u.split("::", 1)[0], "name": u.split("::", 1)[1]} for u in ranked[:10]]
            record = {
                "id": q,
                "system": "website",
                "requested_model": f"ranker {site.sha[:12]}",
                "date": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": round(time.perf_counter() - start, 1),
                "answer": {"functions": top},
                "units": units,
                "confidence": sure,
                "cost_usd": 0.0,
                "tools": [],
                "web_tool_used": False,
            }
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            print(f"  {q}: {units} units, {record['seconds']} s", flush=True)
    site.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
