"""Seeded project-grouped exploratory pilot, using metadata rather than saved outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def plan(rows: list[dict], seed: int = 37) -> dict:
    groups, languages = defaultdict(lambda: defaultdict(list)), defaultdict(set)
    for row in rows:
        if row["full_text_status"] != "unchanged":
            continue
        repo = row["repo"].casefold()
        groups[repo][str(row["issue"])].append(row)
        languages[row["project_language"]].add(repo)
    if sum(map(len, languages.values())) != len(groups):
        raise ValueError("a project appears in multiple language groups")
    rng, selected, projects = random.Random(seed), {}, {}
    for language, repos in sorted(languages.items()):
        if len(repos) < 4:
            raise ValueError(f"need four projects for {language}")
        chosen = rng.sample(sorted(repos), 4)
        selected[language] = []
        for i, repo in enumerate(chosen):
            split = "fit" if i < 2 else "validation"
            projects[repo] = {"language": language, "split": split}
            issues = sorted(groups[repo])
            for issue in rng.sample(issues, min(2, len(issues))):
                # Related PRs stay together; do not silently discard extra rows.
                for row in sorted(groups[repo][issue], key=lambda r: r["id"]):
                    selected[language].append(
                        {
                            "id": row["id"],
                            "repo": row["repo"],
                            "base_commit": row["base_commit"],
                            "issue": row["issue"],
                            "language": language,
                            "split": split,
                            "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                        }
                    )
    order = [
        selected[lang][i]
        for i in range(max(map(len, selected.values())))
        for lang in sorted(selected)
        if i < len(selected[lang])
    ]
    return {
        "schema": "development-pilot-v1",
        "seed": seed,
        "status": "Exploratory exposed fresh data; not a new confirmation set.",
        "selection": "Four seeded projects per language, two underlying issues per project where available; include all PR rows for each selected issue; round-robin execution by language.",
        "projects": projects,
        "instances": order,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / "data/fresh-full/gold.jsonl"
    report = plan([json.loads(line) for line in source.read_bytes().splitlines()])
    report["dataset_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    report["planner_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    print(f"{len(report['instances'])} rows, {len(report['projects'])} projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
