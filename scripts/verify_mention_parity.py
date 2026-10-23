import dataclasses
import json
import subprocess
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

from allfather.eval.dataset import load_instances
from allfather.rank import mentions as current
from allfather.rank.ltr import feature_fingerprint

TRAINED_AT = "c3efa49"
OUT = Path("results/fingerprint/mention_parity.json")
SETS = [
    ("lite", "test"),
    ("full", "test"),
    ("verified", "test"),
    ("rebench", "train"),
    ("rebench", "test"),
]


def trained_mentions() -> types.ModuleType:
    source = subprocess.run(
        ["git", "show", f"{TRAINED_AT}:src/odin/rank/mentions.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    module = types.ModuleType("trained_mentions")
    sys.modules[module.__name__] = module
    exec(
        compile(source.replace("from odin.", "from allfather."), "trained_mentions.py", "exec"),
        module.__dict__,
    )
    return module


def ground_truth_paths() -> list[str]:
    paths: set[str] = set()
    for gold in Path("data/gold").glob("*.jsonl"):
        if "holdout" in gold.name:
            continue
        for line in gold.read_text(encoding="utf-8").splitlines():
            paths.update(json.loads(line).get("files", []))
    return sorted(paths)


def main() -> int:
    old = trained_mentions()
    fields = [f.name for f in dataclasses.fields(old.Mentions)]
    reports = {
        f"{name}/{split}": [i.problem_statement for i in load_instances(name, split)]
        for name, split in SETS
    }
    parse_differs = {
        key: sum(
            any(
                getattr(old.Mentions.parse(t), f) != getattr(current.Mentions.parse(t), f)
                for f in fields
            )
            for t in texts
        )
        for key, texts in reports.items()
    }
    paths = ground_truth_paths()
    mentioned = paths[:400] + [p.rsplit("/", 1)[-1] for p in paths[:400]]
    result = {
        "question": "do the mention features for Python issues match the code the LambdaMART rankers were trained with",
        "trained_with_commit": TRAINED_AT,
        "current_fingerprint": feature_fingerprint(),
        "reports": {key: len(texts) for key, texts in reports.items()},
        "fields": fields,
        "parse_differs": parse_differs,
        "paths": len(paths),
        "path_pairs": len(mentioned) * 600,
        "path_matches_differs": sum(
            old.path_matches(m, r) != current.path_matches(m, r)
            for m in mentioned
            for r in paths[:600]
        ),
        "module_name_differs": sum(old.module_name(r) != current.module_name(r) for r in paths),
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    identical = (
        not any(parse_differs.values())
        and not result["path_matches_differs"]
        and not result["module_name_differs"]
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("reports", "parse_differs", "path_matches_differs", "module_name_differs")
            }
        ),
        "identical:",
        identical,
    )
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
