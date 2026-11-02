"""Build fresh-2026, the sealed test set of ADR 0033.

    GITHUB_TOKEN=... uv run python scripts/fresh_set.py exclusions
    GITHUB_TOKEN=... uv run python scripts/fresh_set.py projects --per-language 17
    GITHUB_TOKEN=... uv run python scripts/fresh_set.py mine --created-after 2026-08-01 --until 2026-11-30
    uv run python scripts/fresh_set.py seal --size 600 --agents 200

exclusions: every repository in any existing set, resolved to GitHub's repository ID (and its fork
parent), so a renamed or forked project is still excluded. Reads repository names only; the sealed
holdout's are taken from its manifest, never from its answer key.
projects: popular, active repositories per language that are not excluded.
mine: for each project, merged pull requests in the window that close exactly one issue opened
before them and after the cutoff, whose text was not edited after the pull request was opened; the
answer key is the merge diff's functions and files, tests excluded (ADR 0023's rule). Resumable.
seal: a random sample stratified by language, its agent subsample, and the manifest with hashes.
Nothing here runs a localizer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from live_eval import RateLimited, closed_issues, github, language_of_fix  # noqa: E402

from allfather.eval.dataset import Instance  # noqa: E402
from allfather.eval.ground_truth import gold_for_instance  # noqa: E402
from allfather.parsing import symbols as multi  # noqa: E402
from allfather.repos import RepoCache  # noqa: E402

DATA = ROOT / "data" / "fresh"
GOLD = ROOT / "data" / "gold"
LANGUAGES = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "go": "Go",
    "java": "Java",
    "rust": "Rust",
}
ISSUE_CHARS = 1500


def existing_repos() -> set[str]:
    names = set()
    for path in GOLD.glob("*.jsonl"):
        if path.name == "odin_holdout.jsonl":
            continue
        for line in path.open(encoding="utf-8"):
            names.add(json.loads(line)["repo"])
    manifest = json.loads((ROOT / "data" / "holdout" / "manifest.json").read_text(encoding="utf-8"))
    names |= {i["repo"] for i in manifest["instances"]}
    names |= set(manifest.get("projects_excluded", []))
    names |= set(
        json.loads((ROOT / "data" / "live" / "projects.json").read_text(encoding="utf-8"))[
            "projects"
        ]
    )
    return {n for n in names if "/" in n}


def repo_ids(name: str) -> list[int]:
    try:
        r = github(f"/repos/{name}")
    except Exception as exc:  # noqa: BLE001
        print(f"  {name}: {exc}", flush=True)
        return []
    ids = [r["id"]]
    for key in ("parent", "source"):
        if r.get(key):
            ids.append(r[key]["id"])
    return ids


def cmd_exclusions(_: argparse.Namespace) -> int:
    names = sorted(existing_repos())
    target = DATA / "excluded.json"
    known = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    for name in names:
        if name not in known:
            known[name] = repo_ids(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(known, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
            )
    print(f"{len(known)} existing repositories, {sum(map(len, known.values()))} IDs")
    return 0


def cmd_projects(args: argparse.Namespace) -> int:
    known = json.loads((DATA / "excluded.json").read_text(encoding="utf-8"))
    excluded = {i for ids in known.values() for i in ids}
    excluded_names = {name.lower() for name in known}
    chosen = []
    for lang, label in LANGUAGES.items():
        q = urllib.parse.quote(
            f"language:{label} stars:>={args.min_stars} pushed:>={args.pushed_after} archived:false fork:false"
        )
        picked = 0
        for page in range(1, 6):
            items = github(
                f"/search/repositories?q={q}&sort=stars&order=desc&per_page=100&page={page}"
            ).get("items", [])
            for r in items:
                if picked >= args.per_language:
                    break
                if (
                    r["id"] in excluded
                    or r["full_name"].lower() in excluded_names
                    or not r.get("has_issues")
                ):
                    continue
                chosen.append(
                    {
                        "repo": r["full_name"],
                        "id": r["id"],
                        "language": lang,
                        "stars": r["stargazers_count"],
                    }
                )
                excluded.add(r["id"])
                picked += 1
            if picked >= args.per_language or not items:
                break
            time.sleep(3)
    target = DATA / "projects.json"
    target.write_text(
        json.dumps(
            {
                "selected": date.today().isoformat(),
                "rule": vars(args) | {"cmd": None},
                "projects": chosen,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {target}: {len(chosen)} projects")
    return 0


def last_body_edit(repo: str, issue: int) -> str | None:
    owner, name = repo.split("/")
    query = {
        "query": "query($o:String!,$n:String!,$i:Int!){repository(owner:$o,name:$n){issue(number:$i){lastEditedAt}}}",
        "variables": {"o": owner, "n": name, "i": issue},
    }
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(query).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "User-Agent": "allfather-fresh-set",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as r:
        data = json.loads(r.read())
    return ((data.get("data") or {}).get("repository") or {}).get("issue", {}).get("lastEditedAt")


def cmd_mine(args: argparse.Namespace) -> int:
    projects = json.loads((DATA / "projects.json").read_text(encoding="utf-8"))["projects"]
    target = DATA / "candidates.jsonl"
    seen = (
        {json.loads(line)["id"] for line in target.open(encoding="utf-8")}
        if target.exists()
        else set()
    )
    cache = RepoCache(ROOT / ".cache" / "repos")
    languages = frozenset({"python", "javascript", "typescript", "tsx", "go", "java", "rust"})
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        for p in projects:
            repo = p["repo"]
            q = urllib.parse.quote(
                f"repo:{repo} is:pr is:merged merged:{args.created_after}..{args.until}"
            )
            try:
                items = []
                for page in range(1, 11):
                    batch = github(
                        f"/search/issues?q={q}&per_page=100&sort=created&order=asc&page={page}"
                    ).get("items", [])
                    items += batch
                    if len(batch) < 100:
                        break
                    time.sleep(2.5)
            except RateLimited:
                print("rate limited; run again to resume", flush=True)
                return 1
            for pr in items:
                issues = closed_issues(repo, pr.get("body") or "")
                rid = f"{repo}#{pr['number']}"
                if len(issues) != 1 or rid in seen:
                    continue
                record = {
                    "id": rid,
                    "repo": repo,
                    "pr": pr["number"],
                    "issue": issues.pop(),
                    "project_language": p["language"],
                }
                try:
                    record |= mined(repo, record["issue"], pr, args.created_after, cache, languages)
                except RateLimited:
                    print("rate limited; run again to resume", flush=True)
                    return 1
                except Exception as exc:  # noqa: BLE001
                    record["skipped"] = f"error: {type(exc).__name__}: {str(exc)[:200]}"
                handle.write(json.dumps(record) + "\n")
                handle.flush()
                seen.add(rid)
                print(f"  {rid}: {record.get('skipped') or record.get('language')}", flush=True)
            time.sleep(2.5)
    return 0


def mined(
    repo: str,
    number: int,
    pr_item: dict,
    created_after: str,
    cache: RepoCache,
    languages: frozenset,
) -> dict:
    issue = github(f"/repos/{repo}/issues/{number}")
    if issue.get("pull_request"):
        return {"skipped": "the closed number is a pull request"}
    if issue["created_at"][:10] < created_after:
        return {"skipped": "issue created before the cutoff", "issue_created": issue["created_at"]}
    if issue["created_at"] > pr_item["created_at"]:
        return {"skipped": "issue opened after the pull request"}
    edited = last_body_edit(repo, number)
    if edited and edited > pr_item["created_at"]:
        return {"skipped": "issue text edited after the pull request opened", "edited": edited}
    pr = github(f"/repos/{repo}/pulls/{pr_item['number']}")
    merge = pr.get("merge_commit_sha")
    if not merge:
        return {"skipped": "no merge commit"}
    parent = github(f"/repos/{repo}/commits/{merge}")["parents"][0]["sha"]
    patch = github(
        f"/repos/{repo}/compare/{parent}...{merge}", accept="application/vnd.github.diff"
    )
    text = f"{issue['title']}\n\n{(issue.get('body') or '')[:ISSUE_CHARS]}"
    inst = Instance(f"{repo}#{pr_item['number']}", repo, parent, patch, text, issue["created_at"])
    gold = gold_for_instance(inst, cache, languages)
    targets = sorted(
        u for u in gold.functions + gold.classes if not multi.is_test_path(u.split("::")[0])
    )
    files = sorted(f for f in gold.files if not multi.is_test_path(f))
    out = {
        "issue_created": issue["created_at"], "pr_created": pr_item["created_at"], "merged": pr["merged_at"],
        "base_commit": parent, "merge_commit": merge, "text": text,
        "gold_functions": targets, "gold_files": files, "language": language_of_fix(set(targets)) if targets else None,
    }  # fmt: skip
    if not files:
        out["skipped"] = "the fix changes no file outside tests"
    return out


def cmd_seal(args: argparse.Namespace) -> int:
    rows = [json.loads(line) for line in (DATA / "candidates.jsonl").open(encoding="utf-8")]
    usable = [r for r in rows if not r.get("skipped")]
    rng = random.Random(args.seed)
    by_lang: dict[str, list[dict]] = {}
    for r in usable:
        by_lang.setdefault(r["language"] or r["project_language"], []).append(r)
    for rs in by_lang.values():
        rng.shuffle(rs)
    total = sum(len(v) for v in by_lang.values())
    take = {lang: min(len(rs), round(args.size * len(rs) / total)) for lang, rs in by_lang.items()}
    sample = [r for lang, rs in sorted(by_lang.items()) for r in rs[: take[lang]]]
    agent_rng = random.Random(args.seed + 1)
    agents = []
    for lang in sorted(by_lang):
        members = [r["id"] for r in sample if (r["language"] or r["project_language"]) == lang]
        agent_rng.shuffle(members)
        agents += members[: round(args.agents * len(members) / max(1, len(sample)))]
    gold_path = DATA / "gold.jsonl"
    with gold_path.open("w", encoding="utf-8", newline="\n") as handle:
        for r in sorted(sample, key=lambda r: r["id"]):
            handle.write(json.dumps(r) + "\n")
    with (DATA / "gold_eval_python.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for r in sorted(sample, key=lambda r: r["id"]):
            if r["language"] == "python":
                entry = {
                    "instance_id": r["id"],
                    "repo": r["repo"],
                    "base_commit": r["base_commit"],
                    "files": r["gold_files"],
                    "functions": r["gold_functions"],
                }
                handle.write(json.dumps(entry) + "\n")
    digest = hashlib.sha256(gold_path.read_bytes()).hexdigest()
    manifest = {
        "name": "fresh-2026",
        "adr": "docs/decisions/0033-frontier-comparison-protocol.md",
        "sealed": date.today().isoformat(),
        "seed": args.seed,
        "candidates": len(rows),
        "usable": len(usable),
        "by_language": {lang: take[lang] for lang in sorted(take)},
        "instances": [
            {
                "id": r["id"],
                "repo": r["repo"],
                "base_commit": r["base_commit"],
                "issue_created": r["issue_created"],
            }
            for r in sorted(sample, key=lambda r: r["id"])
        ],
        "agent_subsample": sorted(agents),
        "gold_sha256": digest,
    }
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"sealed {len(sample)} bugs ({len(agents)} for agents); gold sha256 {digest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("exclusions")
    pp = sub.add_parser("projects")
    pp.add_argument("--per-language", type=int, default=17)
    pp.add_argument("--min-stars", type=int, default=2000)
    pp.add_argument("--pushed-after", default="2026-10-01")
    mp = sub.add_parser("mine")
    mp.add_argument("--created-after", required=True)
    mp.add_argument("--until", default=date.today().isoformat())
    sp = sub.add_parser("seal")
    sp.add_argument("--size", type=int, default=600)
    sp.add_argument("--agents", type=int, default=200)
    sp.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    return {
        "exclusions": cmd_exclusions,
        "projects": cmd_projects,
        "mine": cmd_mine,
        "seal": cmd_seal,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
