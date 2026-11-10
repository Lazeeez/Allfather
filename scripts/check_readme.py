import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from allfather.eval.metrics import metric_values, paired_bootstrap, score  # noqa: E402

RESULTS = ROOT / "results"
README = ROOT / "README.md"
LITE = ROOT / "web" / "public" / "data" / "lite.json"
GOLD_LITE = ROOT / "data" / "gold" / "swebench_lite_test.jsonl"

STEPS = {
    "naive → code-aware tokenizer": ("bm25-naive", "bm25-code"),
    "+ exclude test files": ("bm25-code", "bm25-code-notests"),
    "+ call-graph expansion (dev-tuned)": ("bm25-code-notests", "bm25-code-notests-graph"),
    "BM25 → dense embeddings alone": ("bm25-code-notests", "dense-notests"),
    "dense → hybrid (dev-tuned fusion)": ("dense-notests", "hybrid-notests"),
    "BM25 → hybrid, overall": ("bm25-code-notests", "hybrid-notests"),
    "hybrid → learning to rank (LambdaMART)": ("hybrid-notests", "ltr-notests"),
    "LTR → + fine-tuned cross-encoder (ensemble of 2)": ("ltr-notests", "ltr-ce-notests"),
}
BROWSER_STAGES = {
    "keyword search only": "keyword",
    "instant learned ranking": "instant",
    "+ static-embedding semantic index": "semantic",
    "+ MiniLM rerank of the top 20": "rerank",
    "file ranker (the file that must change)": "files",
}


def result_file(retriever: str, level: str) -> Path:
    name = f"{retriever}_{level}_lite_test.json"
    for folder in ("ties", "provenance"):
        if (RESULTS / folder / name).exists():
            return RESULTS / folder / name
    return RESULTS / name


def load(retriever: str, level: str) -> dict:
    return json.loads(result_file(retriever, level).read_text(encoding="utf-8"))


def plain(cell: str) -> str:
    return re.sub(r"[*`]", "", cell).strip()


def tables(text: str) -> dict[str, list[list[str]]]:
    found: dict[str, list[list[str]]] = {}
    heading = ""
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        elif line.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", line):
            found.setdefault(heading, []).append([plain(c) for c in line.strip("|").split("|")])
    return found


def numbers(cell: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d+\.\d+|[-+]?\d+", cell.replace("%", ""))]


class Report:
    def __init__(self) -> None:
        self.checked = 0
        self.mismatches: list[str] = []

    def expect(self, where: str, shown: float, actual: float, places: int) -> None:
        self.checked += 1
        if round(actual, places) != round(shown, places):
            self.mismatches.append(f"{where}: README {shown} vs result {actual:.{places + 2}f}")


def check_headline(rows: list[list[str]], report: Report) -> None:
    for row in rows[1:]:
        level = "file" if row[0].startswith("File") else "function"
        summary = load("ltr-ce-notests", level)["summary"]
        report.expect(f"headline {level} issues", numbers(row[0])[0], summary["n"], 0)
        for cell, key in zip(row[1:4], ("hit@1", "hit@5", "hit@10"), strict=True):
            report.expect(f"headline {level} {key}", numbers(cell)[0], 100 * summary[key], 1)
        recall, low, high = numbers(row[4])
        report.expect(f"headline {level} recall@10", recall, summary["recall@10"], 3)
        report.expect(f"headline {level} ci low", low, summary["ci95"]["recall@10"][0], 2)
        report.expect(f"headline {level} ci high", high, summary["ci95"]["recall@10"][1], 2)
        report.expect(f"headline {level} mrr", numbers(row[5])[0], summary["mrr"], 3)


FROZEN_ROWS = {
    "Holdout, function": "holdout_function",
    "Holdout, file": "holdout_file",
    "Lite, function": "lite_function",
    "Lite, file": "lite_file",
}


def check_frozen(rows: list[list[str]], report: Report) -> None:
    runs = json.loads((RESULTS / "frozen" / "report.json").read_text(encoding="utf-8"))["runs"]
    for row in rows[1:]:
        run = runs[FROZEN_ROWS[row[0]]]
        metrics = run["metrics"]
        report.expect(f"frozen {row[0]} bugs", numbers(row[1])[0], run["issues"], 0)
        for cell, key in zip(row[2:5], ("hit@1", "hit@5", "hit@10"), strict=True):
            report.expect(
                f"frozen {row[0]} {key}", numbers(cell)[0], 100 * metrics[key]["value"], 1
            )
        _, low, high = numbers(row[4])
        report.expect(f"frozen {row[0]} hit@10 ci low", low, 100 * metrics["hit@10"]["ci95"][0], 1)
        report.expect(
            f"frozen {row[0]} hit@10 ci high", high, 100 * metrics["hit@10"]["ci95"][1], 1
        )
        report.expect(
            f"frozen {row[0]} all@10", numbers(row[5])[0], 100 * metrics["all@10"]["value"], 1
        )
        report.expect(f"frozen {row[0]} mrr", numbers(row[6])[0], metrics["mrr"]["value"], 3)


def check_retrievers(rows: list[list[str]], report: Report) -> None:
    for row in rows[1:]:
        retriever, level = row[0], row[1]
        summary = load(retriever, level)["summary"]
        where = f"retrievers {retriever} {level}"
        report.expect(f"{where} recall@1", numbers(row[2])[0], summary["recall@1"], 3)
        report.expect(f"{where} recall@5", numbers(row[3])[0], summary["recall@5"], 3)
        recall, low, high = numbers(row[4])
        report.expect(f"{where} recall@10", recall, summary["recall@10"], 3)
        report.expect(f"{where} ci low", low, summary["ci95"]["recall@10"][0], 2)
        report.expect(f"{where} ci high", high, summary["ci95"]["recall@10"][1], 2)
        report.expect(f"{where} all@10", numbers(row[5])[0], summary["all@10"], 3)
        report.expect(f"{where} mrr", numbers(row[6])[0], summary["mrr"], 3)


def paired(a: str, b: str, level: str, metric: str):
    runs = [load(name, level) for name in (a, b)]
    by_id = [{r["instance_id"]: r for r in run["per_instance"]} for run in runs]
    common = sorted(by_id[0].keys() & by_id[1].keys())
    values = [
        metric_values(
            [score(rows[q]["ranked"], rows[q]["gold"], [1, 5, 10]) for q in common], metric
        )
        for rows in by_id
    ]
    return paired_bootstrap(values[0], values[1]), len(common)


def check_steps(rows: list[list[str]], report: Report) -> None:
    for row in rows[1:]:
        a, b = STEPS[row[0]]
        diff, _ = paired(a, b, "function", "recall@10")
        where = f"steps {row[0]}"
        report.expect(f"{where} delta", numbers(row[1])[0], diff.delta, 3)
        low, high = numbers(row[2])
        report.expect(f"{where} ci low", low, diff.ci95[0], 3)
        report.expect(f"{where} ci high", high, diff.ci95[1], 3)
        shown_p = row[3]
        if shown_p.startswith("<"):
            report.checked += 1
            if not diff.p_value < numbers(shown_p)[0]:
                report.mismatches.append(f"{where} p: README {shown_p} vs result {diff.p_value}")
        else:
            places = len(shown_p.split(".")[1])
            report.expect(f"{where} p", numbers(shown_p)[0], diff.p_value, places)
        wins, losses = numbers(row[4])
        report.expect(f"{where} wins", wins, diff.wins, 0)
        report.expect(f"{where} losses", losses, diff.losses, 0)


def check_browser(rows: list[list[str]], report: Report) -> None:
    unseen = json.loads(LITE.read_text(encoding="utf-8"))["held_out"]["unseen"]
    for row in rows[1:]:
        metrics = unseen[BROWSER_STAGES[row[0]]]
        where = f"browser {row[0]}"
        report.expect(f"{where} hit@1", numbers(row[1])[0], 100 * metrics["hit@1"], 1)
        report.expect(f"{where} hit@10", numbers(row[2])[0], 100 * metrics["hit@10"], 1)
        report.expect(f"{where} mrr", numbers(row[3])[0], metrics["mrr"], 3)


LANGUAGE_NAMES = {
    "Go": "go",
    "Java": "java",
    "JavaScript": "javascript",
    "Rust": "rust",
    "TypeScript": "typescript",
}
TEST_SETS = {"SWE-bench Multilingual": "multilingual", "SWE-PolyBench": "polybench"}


def check_languages(rows: list[list[str]], report: Report) -> None:
    sets = json.loads(LITE.read_text(encoding="utf-8"))["held_out_per_language"]
    for row in rows[1:]:
        e = sets[TEST_SETS[row[1]]][LANGUAGE_NAMES[row[0]]]
        where = f"language {row[0]} {row[1]}"
        report.expect(f"{where} bugs", numbers(row[2])[0], e["issues"], 0)
        report.expect(f"{where} allfather", numbers(row[3])[0], 100 * e["learned"]["hit@10"], 1)
        report.expect(
            f"{where} baseline", numbers(row[4])[0], 100 * e["keyword_and_meaning"]["hit@10"], 1
        )
        report.expect(f"{where} change", numbers(row[5])[0], 100 * e["hit@10_gain"]["delta"], 1)
        check_p(f"{where} p", row[5].split("(p")[1], e["hit@10_gain"]["p"], report)
        check_p(f"{where} Holm p", row[6], e["hit@10_gain"]["p_holm"], report)


def check_p(where: str, shown: str, actual: float, report: Report) -> None:
    if "<" in shown:
        if not actual < numbers(shown)[0]:
            report.mismatches.append(f"{where}: README {shown.strip()} vs result {actual}")
    else:
        report.expect(where, numbers(shown)[0], actual, 3)


def check_per_repo(rows: list[list[str]], report: Report) -> None:
    bm25 = load("bm25-code-notests", "function")["summary"]["by_repo"]
    hybrid = load("hybrid-notests", "function")["summary"]["by_repo"]
    for row in rows[1:]:
        repo = row[0]
        where = f"per-repo {repo}"
        report.expect(f"{where} issues", numbers(row[1])[0], bm25[repo]["n"], 0)
        report.expect(f"{where} bm25 recall@10", numbers(row[2])[0], bm25[repo]["recall@10"], 2)
        report.expect(f"{where} hybrid recall@10", numbers(row[3])[0], hybrid[repo]["recall@10"], 2)
        report.expect(f"{where} bm25 mrr", numbers(row[4])[0], bm25[repo]["mrr"], 2)
        report.expect(f"{where} hybrid mrr", numbers(row[5])[0], hybrid[repo]["mrr"], 2)


PERF = RESULTS / "perf" / "lite_index_2026-10-13.json"
PERF_ROWS = {
    "End-to-end wall time": (("wall_s",), 0),
    "Index build p50 / p95": (("index_ms_p50", "index_ms_p95"), 0),
    "Query latency p50 / p99": (("query_ms_p50", "query_ms_p99"), 2),
    "Blobs parsed": (("blobs_parsed",), 0),
}


def check_performance(rows: list[list[str]], text: str, report: Report) -> None:
    measured = json.loads(PERF.read_text(encoding="utf-8"))
    runs = [measured["runs"][mode] for mode in ("no-cache", "cold-cache", "warm-cache")]
    for row in rows:
        if row[0] not in PERF_ROWS:
            continue
        keys, places = PERF_ROWS[row[0]]
        for cell, run in zip(row[1:], runs, strict=True):
            for shown, key in zip(numbers(cell.replace(",", "")), keys, strict=True):
                report.expect(f"performance {row[0]} {key}", shown, run[key], places)
    first = runs[0]
    stated = re.search(r"so ([\d,]+) files cost ([\d,]+) parses", text)
    files, parses = (float(g.replace(",", "")) for g in stated.groups())
    report.expect("performance files", files, first["files_indexed"], 0)
    report.expect("performance parses", parses, first["blobs_parsed"], 0)
    reuse = float(re.search(r"Within one run, (\d+)% of files are never parsed", text).group(1))
    report.expect("performance reuse", reuse, 100 * first["blob_reuse"], 0)
    report.checked += 1
    if not measured["identical_rankings"]:
        report.mismatches.append("performance: rankings differ between cache modes")


def check_dense_costs(text: str, report: Report) -> None:
    perf = RESULTS / "perf"
    slots = json.loads((perf / "unit_slots_2026-10-13.json").read_text(encoding="utf-8"))
    row = re.search(
        r"Unit slots across the (\d+) snapshots .*?\((\d+) Lite, (\d+) dev\) \| ([\d.]+)M", text
    )
    lite, dev = slots["sets"]["lite test"], slots["sets"]["dev (verified minus lite)"]
    for shown, actual, places in zip(
        row.groups(),
        (slots["snapshots"], lite["snapshots"], dev["snapshots"], slots["unit_slots"] / 1e6),
        (0, 0, 0, 2),
        strict=True,
    ):
        report.expect("unit slots", float(shown), actual, places)
    distinct = re.search(r"\*\*(\d+)k \(([\d.]+)× fewer\)\*\*", text)
    report.expect("distinct units", float(distinct.group(1)), slots["distinct_unit_texts"] / 1e3, 0)
    report.expect(
        "embedding reuse",
        float(distinct.group(2)),
        slots["unit_slots"] / slots["distinct_unit_texts"],
        1,
    )
    batching = json.loads((perf / "bench_batching_2026-10-13.json").read_text(encoding="utf-8"))
    measured = {}
    for line in batching["output"]:
        cells = line.split()
        if line.endswith("%") and len(cells) >= 3:
            measured[" ".join(cells[:-2])] = float(cells[-2])
    for label, key in (
        ("Fixed batches of 32 in file order", "arrival order, batch 32"),
        ("Length-sorted, batches of 32", "length-sorted, batch 32"),
        ("Length-sorted, 4096-token budget", "token budget 4096"),
    ):
        shown = re.search(re.escape(label) + r"\W* \| \W*(\d+)", text)
        report.expect(f"batching {key}", float(shown.group(1)), measured[key], 0)
    gain = float(re.search(r"nearly all of the ([\d.]+)× gain", text).group(1))
    report.expect(
        "batching gain",
        gain,
        measured["token budget 4096"] / measured["arrival order, batch 32"],
        1,
    )


def check_comparison(rows: list[list[str]], report: Report) -> None:
    path = RESULTS / "comparison" / "locagent-lite_2026-10-13.json"
    acc = json.loads(path.read_text(encoding="utf-8"))["stages"]["ltr-ce-notests"]["acc"]
    row = next(r for r in rows if r[0].startswith("Allfather"))
    actual = (
        acc["file"]["acc@1"],
        acc["file"]["acc@5"],
        acc["function"]["acc@5"],
        acc["function"]["acc@10"],
    )
    for shown, value in zip(row[3:], actual, strict=True):
        report.expect("comparison allfather", float(shown), 100 * value, 2)


def check_cost(text: str, report: Report) -> None:
    perf = RESULTS / "perf"
    prices = json.loads(
        (ROOT / "docs" / "data" / "published_cost_accuracy.json").read_text(encoding="utf-8")
    )
    laptop = json.loads((perf / "cascade_2026-10-13.json").read_text(encoding="utf-8"))["summary"]
    l40s = json.loads((perf / "cascade_pace-l40s-warm.json").read_text(encoding="utf-8"))["summary"]
    stated = re.search(
        r"takes ([\d.]+) seconds per issue on an NVIDIA L40S \(median ([\d.]+)\).*?"
        r"about \$([\d.]+) per issue",
        text,
    )
    seconds = l40s["total"]["mean_ms"] / 1000
    actual = (
        seconds,
        l40s["total"]["p50_ms"] / 1000,
        seconds * prices["gpu_price_l40s"]["dollars_per_hour"] / 3600,
    )
    for shown, value, places in zip(stated.groups(), actual, (2, 2, 4), strict=True):
        report.expect("cost l40s", float(shown), value, places)
    stated = re.search(
        r"\(RTX 4050\) the same cascade takes ([\d.]+) seconds per issue, median ([\d.]+) "
        r"seconds, and the reranker is (\d+)% of that; priced the same way, that is about "
        r"\$([\d.]+) per issue",
        text,
    )
    seconds = laptop["total"]["mean_ms"] / 1000
    actual = (
        seconds,
        laptop["total"]["p50_ms"] / 1000,
        100 * laptop["reranker"]["mean_ms"] / laptop["total"]["mean_ms"],
        seconds * prices["gpu_price"]["dollars_per_hour"] / 3600,
    )
    for shown, value, places in zip(stated.groups(), actual, (1, 1, 0, 4), strict=True):
        report.expect("cost laptop", float(shown), value, places)


def check_prose(text: str, report: Report) -> None:
    ce_fn_mrr, _ = paired("ltr-notests", "ltr-ce-notests", "function", "mrr")
    ce_fn_r1, _ = paired("ltr-notests", "ltr-ce-notests", "function", "recall@1")
    ce_file_mrr, _ = paired("ltr-notests", "ltr-ce-notests", "file", "mrr")
    ce_file_r1, _ = paired("ltr-notests", "ltr-ce-notests", "file", "recall@1")
    match = re.search(
        r"function MRR \+([\d.]+) and recall@1 \+([\d.]+) \(both p < 0\.01\), "
        r"file MRR \+([\d.]+) and recall@1 \+([\d.]+)",
        text,
    )
    for label, shown, diff in zip(
        ("ce function mrr", "ce function recall@1", "ce file mrr", "ce file recall@1"),
        match.groups(),
        (ce_fn_mrr, ce_fn_r1, ce_file_mrr, ce_file_r1),
        strict=True,
    ):
        report.expect(f"prose {label}", float(shown), diff.delta, 3)
        report.checked += 1
        if not diff.p_value < 0.01:
            report.mismatches.append(
                f"prose {label}: README says p < 0.01, result p = {diff.p_value}"
            )

    naive = load("bm25-naive", "function")["summary"]
    final = load("ltr-ce-notests", "function")["summary"]
    match = re.search(
        r"plain BM25 started this project at ([\d.]+)% function hit@10 "
        r"\(recall@10 ([\d.]+), against ([\d.]+) now\)",
        text,
    )
    report.expect("prose plain BM25 hit@10", float(match.group(1)), 100 * naive["hit@10"], 1)
    report.expect("prose plain BM25 recall@10", float(match.group(2)), naive["recall@10"], 3)
    report.expect("prose final recall@10", float(match.group(3)), final["recall@10"], 3)

    tests, _ = paired("bm25-code", "bm25-code-notests", "function", "recall@1")
    match = re.search(r"largest lexical win at recall@1 \(\+([\d.]+), p = ([\d.]+)\)", text)
    report.expect("prose test exclusion recall@1", float(match.group(1)), tests.delta, 3)
    report.expect("prose test exclusion p", float(match.group(2)), tests.p_value, 3)
    other_lexical = [
        paired(a, b, "function", "recall@1")[0].delta
        for a, b in (("bm25-naive", "bm25-code"), ("bm25-code-notests", "bm25-code-notests-graph"))
    ]
    report.checked += 1
    if tests.delta <= max(other_lexical):
        report.mismatches.append("prose test exclusion: README calls it the largest lexical win")

    pool = re.search(r"held a gold unit for ([\d.]+)% of issues, measured on the dev set", text)
    adr = (ROOT / "docs" / "decisions" / "0006-learning-to-rank.md").read_text(encoding="utf-8")
    report.checked += 1
    if f"contained a gold unit {pool.group(1)}% of the time" not in adr:
        report.mismatches.append("prose pool recall: README and ADR 0006 disagree")

    r1, _ = paired("bm25-naive", "bm25-code", "function", "recall@1")
    shown = float(
        re.search(r"At recall@1 the gain \(\+([\d.]+)\) is not significant", text).group(1)
    )
    report.expect("prose tokenizer recall@1 gain", shown, r1.delta, 3)
    report.checked += 1
    if r1.p_value < 0.05:
        report.mismatches.append(
            f"prose tokenizer recall@1: README says not significant, p = {r1.p_value}"
        )

    file_hybrid, _ = paired("bm25-code-notests", "hybrid-notests", "file", "recall@10")
    match = re.search(
        r"Recall@10 is \+([\d.]+) points at file level too, with (\d+) wins to (\d+) losses", text
    )
    report.expect("prose hybrid file delta", float(match.group(1)), 100 * file_hybrid.delta, 1)
    report.expect("prose hybrid file wins", float(match.group(2)), file_hybrid.wins, 0)
    report.expect("prose hybrid file losses", float(match.group(3)), file_hybrid.losses, 0)

    gold = [json.loads(line) for line in GOLD_LITE.read_text(encoding="utf-8").splitlines() if line]
    with_function = sum(1 for g in gold if g["functions"])
    class_only = sum(1 for g in gold if not g["functions"] and g["classes"])
    module_only = sum(1 for g in gold if not g["functions"] and not g["classes"])
    match = re.search(
        r"Of the 300 Lite issues, (\d+) have a function or method target, (\d+) more are class-level only"
        r".*?and (\d+) are module-level only",
        text,
    )
    report.expect("prose gold function targets", float(match.group(1)), with_function, 0)
    report.expect("prose gold class-only", float(match.group(2)), class_only, 0)
    report.expect("prose gold module-only", float(match.group(3)), module_only, 0)
    report.expect("prose one file per patch", 1, max(len(g["files"]) for g in gold), 0)

    parity = json.loads((RESULTS / "parity_pinned_2026-10-13b.json").read_text(encoding="utf-8"))[
        "totals"
    ]
    match = re.search(
        r"([\d,]+) files and ([\d,]+) units chunk identically, scores agree to within 1e-5, "
        r"and (\d+) of (\d+) queries return the same top 10",
        text,
    )
    shown = [float(group.replace(",", "")) for group in match.groups()]
    same = parity["queries"] - parity["queries_with_different_top10"]
    report.expect("prose parity files", shown[0], parity["files"], 0)
    report.expect("prose parity units", shown[1], parity["units"], 0)
    report.expect("prose parity same top 10", shown[2], same, 0)
    report.expect("prose parity queries", shown[3], parity["queries"], 0)
    report.checked += 2
    if parity["files_with_different_units"]:
        report.mismatches.append("prose parity: README says every file chunks identically")
    if parity["largest_relative_score_difference"] > 1e-5:
        report.mismatches.append("prose parity: README says scores agree to within 1e-5")

    log = (RESULTS / "test-evals.log").read_text(encoding="utf-8").splitlines()
    entries = [line.split(" | ") for line in log if line and not line.startswith("#")]
    on_lite = sum(1 for entry in entries if entry[1] == "lite")
    shown = float(re.search(r"I have scored it (\d+) times", text).group(1))
    report.expect("prose Lite evaluations", shown, on_lite, 0)


FRESH_SYSTEMS = {
    "gpt-6-astra agent (Codex)": "codex-agent-astra",
    "gpt-6-luna agent (Codex)": "codex-agent",
    "Allfather, browser only": "website",
    "Allfather + GPU reranker": "website-gpu",
    "SweRankEmbed-Large": "swerank-embed-large",
    "SweRankEmbed-Small": "swerank-embed-small",
    "Qwen3-Coder-Next agent": "open-agent-qwen3-coder-next-fp8",
    "gpt-6-astra, one call": "codex-single-astra",
    "Gemini 3.8 Flash, one call": "gemini-single",
    "gpt-oss-120b agent": "open-agent-gpt-oss-120b",
    "gpt-6-luna, one call": "codex-single",
    "Qwen3-Coder-Next, one call": "open-single-qwen3-coder-next-fp8",
    "gpt-oss-120b, one call": "open-single-gpt-oss-120b",
}


def check_fresh(rows: list[list[str]], report: Report) -> None:
    analysis = None
    for row in rows:
        if row[0] == "System":
            name = "fresh-full-agents" if "Free" in row else "fresh-full"
            analysis = json.loads(
                (RESULTS / "research" / f"analysis_{name}.json").read_text(encoding="utf-8")
            )
            first = 2 if "Free" in row else 1
            continue
        system = FRESH_SYSTEMS[row[0]]
        entry = analysis["systems"][system]
        where = f"fresh {analysis['set']} {system}"
        report.expect(f"{where} hit@1", numbers(row[first])[0], 100 * entry["hit@1"], 1)
        hit, low, high = numbers(row[first + 1])
        report.expect(f"{where} hit@10", hit, 100 * entry["hit@10"], 1)
        report.expect(f"{where} ci low", low, 100 * entry["hit@10_ci95"][0], 1)
        report.expect(f"{where} ci high", high, 100 * entry["hit@10_ci95"][1], 1)
        paired = analysis["paired"].get(f"{system}:hit@10")
        if paired is None:
            continue
        delta, wins, losses, *rest = numbers(row[-1].replace("−", "-"))
        report.expect(f"{where} delta", delta, 100 * paired["delta"], 1)
        report.expect(f"{where} wins", wins, paired["wins"], 0)
        report.expect(f"{where} losses", losses, paired["losses"], 0)
        if "<0.001" in row[-1]:
            report.checked += 1
            if paired["p_holm"] >= 0.001:
                report.mismatches.append(
                    f"{where} holm: README <0.001 vs result {paired['p_holm']}"
                )
        elif rest:
            report.expect(f"{where} holm", rest[0], paired["p_holm"], 3)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    text = README.read_text(encoding="utf-8")
    found = tables(text)
    report = Report()
    check_headline(found["On SWE-bench Lite"], report)
    check_fresh(found["Against frontier AI, on bugs they cannot have seen"], report)
    check_frozen(found["On bugs filed after its models, in projects it never saw"], report)
    check_browser(found["In the browser, on projects it never saw"], report)
    check_languages(found["In the browser, in other languages"], report)
    check_retrievers(found["Every retriever"], report)
    steps_heading = next(
        (heading for heading in found if heading.startswith("What each step bought (")),
        None,
    )
    if steps_heading is None:
        raise KeyError("What each step bought (...)")
    check_steps(found[steps_heading], report)
    check_per_repo(found["Evaluation methodology"], report)
    check_performance(found["Performance"], text, report)
    check_dense_costs(text, report)
    check_comparison(found["Next to published systems"], report)
    check_cost(text, report)
    check_prose(text, report)
    for line in report.mismatches:
        print("MISMATCH", line)
    print(f"{report.checked} README numbers checked, {len(report.mismatches)} mismatches")
    return 1 if report.mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
