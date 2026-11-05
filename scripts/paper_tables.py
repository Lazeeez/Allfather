"""Write every table and number the paper uses, from the committed results only.

    uv run python scripts/paper_tables.py

Reads results/research/analysis_<set>.json, the run records in results/research/frontier/ (for cost
and time), data/fresh/ (for the test set's composition) and the reranker study's choice.json, and
writes docs/paper/generated/: one .tex file per table and numbers.tex, a list of \\newcommand macros
the text uses instead of typing numbers. Prices are the per-token rates listed in PRICES, with their
sources in the paper; a run on a subscription records no price, so its cost is computed from its own
token counts at those rates.
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "research"
RUNS = RESULTS / "frontier"
OUT = ROOT / "docs" / "paper" / "generated"

NAMES = {
    "website-gpu": "Allfather + GPU reranker",
    "website": "Allfather, browser only",
    "allfather-fast": "allfather-fast (Python)",
    "swerank-embed-large": "SweRankEmbed-Large",
    "swerank-embed-small": "SweRankEmbed-Small",
    "codex-agent": "gpt-6-luna, agent",
    "codex-single": "gpt-6-luna, one call",
    "codex-agent-astra": "gpt-6-astra, agent",
    "codex-single-astra": "gpt-6-astra, one call",
    "gemini-single": "Gemini 3.8 Flash, one call",
    "claude-agent": "Claude Opus 5.5, agent",
    "claude-single": "Claude Opus 5.5, one call",
    "claude-single-sonnet": "Claude Sonnet 5.5, one call",
    "open-agent-qwen3-coder-next-fp8": "Qwen3-Coder-Next, agent",
    "open-single-qwen3-coder-next-fp8": "Qwen3-Coder-Next, one call",
    "open-agent-gpt-oss-120b": "gpt-oss-120b, agent",
    "open-single-gpt-oss-120b": "gpt-oss-120b, one call",
}
FREE = {
    "website-gpu", "website", "allfather-fast", "swerank-embed-large", "swerank-embed-small",
    "codex-agent", "codex-single", "gemini-single", "open-agent-qwen3-coder-next-fp8",
    "open-single-qwen3-coder-next-fp8", "open-agent-gpt-oss-120b", "open-single-gpt-oss-120b",
}  # fmt: skip
LANG = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "go": "Go",
    "java": "Java",
    "rust": "Rust",
}
PRICES = {
    "astra": (10.0, 1.0, 50.0, 20.0, 75.0),
    "luna": (0.10, 0.01, 0.50, 0.20, 0.75),
    "gemini": (0.75, 3.75),
    "gpu_hour": {"l40s": 1.00, "l4": 0.80},
}
MIN_ISSUES = 50
CHECK = "\\checkmark"


def analysis(name: str) -> dict:
    return json.loads((RESULTS / f"analysis_{name}.json").read_text(encoding="utf-8"))


def rows(set_name: str, system: str) -> list[dict]:
    path = RUNS / f"{set_name}_{system}.jsonl"
    return [json.loads(line) for line in path.open(encoding="utf-8")] if path.exists() else []


def codex_cost(usage: dict, model: str) -> float:
    i, c, o, il, ol = PRICES[model]
    inp, cached, out = (
        usage.get("input_tokens", 0),
        usage.get("cached_input_tokens", 0),
        usage.get("output_tokens", 0),
    )
    if inp > 272_000:
        i, o, c = il, ol, il / 10
    return ((inp - cached) * i + cached * c + out * o) / 1e6


def cost_per_bug(set_name: str, system: str) -> float | None:
    rs = rows(set_name, system)
    if not rs:
        return None
    if system.startswith("claude"):
        return st.mean(r.get("cost_usd") or 0.0 for r in rs)
    if system.startswith("codex"):
        return st.mean(
            codex_cost(r.get("usage") or {}, "astra" if "astra" in system else "luna") for r in rs
        )
    if system.startswith("gemini"):
        i, o = PRICES["gemini"]
        return st.mean(
            ((u := r.get("usage") or {}).get("promptTokenCount", 0) * i
             + (u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)) * o) / 1e6
            for r in rs
        )  # fmt: skip
    if system.startswith("open-"):
        return (
            st.mean(
                ((r.get("usage") or {}).get("gpu_seconds") or r.get("seconds") or 0) for r in rs
            )
            / 3600
            * 4
            * PRICES["gpu_hour"]["l40s"]
        )
    if system in ("website", "allfather-fast"):
        return 0.0
    if system == "website-gpu":
        gpu = median_seconds(set_name, "website-gpu") - median_seconds(set_name, "website")
        return max(gpu, 0) / 3600 * PRICES["gpu_hour"]["l4"]
    return None


def median_seconds(set_name: str, system: str) -> float:
    rs = rows(set_name, system)
    return st.median(r.get("seconds") or 0 for r in rs) if rs else 0.0


def pct(x: float) -> str:
    return f"{x * 100:.1f}"


def money(x: float | None) -> str:
    if x is None:
        return "--"
    if x == 0:
        return "\\$0"
    return f"\\${x:.3f}" if x < 0.1 else f"\\${x:.2f}"


def pvalue(p: float | None) -> str:
    if p is None:
        return "--"
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def systems_table(set_name: str, ref: str, caption: str, label: str) -> str:
    a = analysis(set_name)
    order = sorted(
        (s for s, e in a["systems"].items() if e["issues"] >= MIN_ISSUES and s in NAMES),
        key=lambda s: -a["systems"][s]["hit@10"],
    )
    lines = [
        "\\begin{table*}[t]", "\\centering", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
        "\\begin{tabular}{lcrrrrrrrr}", "\\toprule",
        "System & Free & $n$ & hit@1 & hit@10 & 95\\% CI & all@10 & MRR & Cost/bug & $\\Delta$ hit@10 (W/L, $p_{\\mathrm{Holm}}$) \\\\",
        "\\midrule",
    ]  # fmt: skip
    for s in order:
        e = a["systems"][s]
        lo, hi = e["hit@10_ci95"]
        pr = a["paired"].get(f"{s}:hit@10")
        delta = "reference" if s == ref else (
            f"{pr['delta'] * 100:+.1f} ({pr['wins']}/{pr['losses']}, {pvalue(pr['p_holm'])})" if pr else "--"
        )  # fmt: skip
        name = f"\\textbf{{{NAMES[s]}}}" if s == ref else NAMES[s]
        lines.append(
            f"{name} & {CHECK if s in FREE else ''} & {e['issues']} & {pct(e['hit@1'])} & {pct(e['hit@10'])} & "
            f"{pct(lo)}--{pct(hi)} & {pct(e['all@10'])} & {e['mrr']:.3f} & {money(cost_per_bug(set_name, s))} & {delta} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table*}", ""]
    return "\n".join(lines)


def language_table(set_name: str, caption: str, label: str) -> str:
    a = analysis(set_name)
    langs = [lang for lang in LANG if lang in next(iter(a["by_language"].values()))]
    order = sorted(
        (
            s
            for s in a["by_language"]
            if a["systems"].get(s, {}).get("issues", 0) >= MIN_ISSUES and s in NAMES
        ),
        key=lambda s: -a["systems"][s]["hit@10"],
    )
    head = " & ".join(f"{LANG[lang]}" for lang in langs)
    lines = ["\\begin{table}[t]", "\\centering", "\\small", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
             "\\begin{tabular}{l" + "r" * len(langs) + "}", "\\toprule", f"System & {head} \\\\", "\\midrule"]  # fmt: skip
    for s in order:
        cells = []
        best = {
            lang: max(
                a["by_language"][x][lang]["hit@10"] for x in order if lang in a["by_language"][x]
            )
            for lang in langs
        }
        for lang in langs:
            v = a["by_language"][s].get(lang, {}).get("hit@10")
            cells.append(
                "--" if v is None else (f"\\textbf{{{pct(v)}}}" if v == best[lang] else pct(v))
            )
        lines.append(f"{NAMES[s]} & " + " & ".join(cells) + " \\\\")
    n = {lang: a["by_language"][order[0]][lang]["issues"] for lang in langs}
    lines += ["\\midrule", "Bugs & " + " & ".join(str(n[lang]) for lang in langs) + " \\\\",
              "\\bottomrule", "\\end{tabular}", "\\end{table}", ""]  # fmt: skip
    return "\n".join(lines)


def escalation_table(set_name: str, label: str) -> str:
    a = analysis(set_name)
    lines = ["\\begin{table}[t]", "\\centering", "\\small",
             "\\caption{Confidence-gated escalation (RQ3): the bugs Allfather is least confident about, at the threshold fixed before the study (0.7899), go to an agent; the rest keep Allfather's answer. Random escalates the same share at random.}",
             f"\\label{{{label}}}", "\\begin{tabular}{lrrrrr}", "\\toprule",
             "Agent & Escalated & Cascade & Random & Agent alone & Cascade cost/bug \\\\", "\\midrule"]  # fmt: skip
    ref_cost = cost_per_bug(set_name, a["reference"]) or 0.0
    for s, e in sorted(a["escalation"].items(), key=lambda kv: -kv[1]["chosen"]["hit@10"]):
        if s not in NAMES or "agent" not in s:
            continue
        c = e["chosen"]
        agent_cost = cost_per_bug(set_name, s) or 0.0
        lines.append(
            f"{NAMES[s]} & {pct(c['escalated'])}\\% & {pct(c['hit@10'])} & {pct(c['random_hit@10'])} & "
            f"{pct(a['systems'][s]['hit@10'])} & {money(ref_cost + c['escalated'] * agent_cost)} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def condition_table(label: str) -> str:
    rows_out = []
    for short, full, n in (
        ("fresh-agents", "fresh-full-agents", 198),
        ("fresh", "fresh-full", 580),
    ):
        s, f = analysis(short), analysis(full)
        for name in sorted(
            set(s["systems"]) & set(f["systems"]), key=lambda x: -f["systems"][x]["hit@10"]
        ):
            if (
                name in NAMES
                and min(s["systems"][name]["issues"], f["systems"][name]["issues"]) >= MIN_ISSUES
            ):
                a, b = s["systems"][name]["hit@10"], f["systems"][name]["hit@10"]
                rows_out.append(
                    f"{NAMES[name]} & {n} & {pct(a)} & {pct(b)} & {(b - a) * 100:+.1f} \\\\"
                )
    return "\n".join(
        ["\\begin{table}[t]", "\\centering", "\\small",
         "\\caption{Shortened (first 1,500 characters of the body) against full bug reports, function hit@10 on the same bugs.}",
         f"\\label{{{label}}}", "\\begin{tabular}{lrrrr}", "\\toprule", "System & Bugs & Shortened & Full & Change \\\\", "\\midrule",
         *rows_out, "\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    )  # fmt: skip


def dataset_table(label: str) -> str:
    gold = [
        json.loads(line) for line in (ROOT / "data" / "fresh" / "gold.jsonl").open(encoding="utf-8")
    ]
    full = {
        r["id"]: r
        for r in map(
            json.loads, (ROOT / "data" / "fresh-full" / "gold.jsonl").open(encoding="utf-8")
        )
    }
    sub = set(
        json.loads((ROOT / "data" / "fresh" / "manifest.json").read_text(encoding="utf-8"))[
            "agent_subsample"
        ]
    )
    lines = ["\\begin{table}[t]", "\\centering", "\\small", "\\caption{fresh-2026: bugs reported from 1 August to 2 November 2026.}",
             f"\\label{{{label}}}", "\\begin{tabular}{lrrrrr}", "\\toprule",
             "Language & Bugs & Projects & Agent subset & Funcs/bug & Report chars (full) \\\\", "\\midrule"]  # fmt: skip
    for lang in LANG:
        g = [r for r in gold if r["language"] == lang]
        lines.append(
            f"{LANG[lang]} & {len(g)} & {len({r['repo'] for r in g})} & {sum(r['id'] in sub for r in g)} & "
            f"{st.median(len(r['gold_functions']) for r in g):.0f} & {st.median(len(full[r['id']]['text']) for r in g):,.0f} \\\\"
        )
    lines += ["\\midrule",
              f"All & {len(gold)} & {len({r['repo'] for r in gold})} & {len(sub)} & {st.median(len(r['gold_functions']) for r in gold):.0f} & {st.median(len(full[r['id']]['text']) for r in gold):,.0f} \\\\",
              "\\bottomrule", "\\end{tabular}", "\\end{table}", ""]  # fmt: skip
    return "\n".join(lines)


def reranker_table(label: str) -> str:
    c = json.loads(
        (ROOT / "results" / "website-rerank" / "choice.json").read_text(encoding="utf-8")
    )["languages"]
    cols = ["current pair", "A", "B", "C"]
    lines = ["\\begin{table}[t]", "\\centering", "\\small",
             "\\caption{The GPU reranker on training bugs, cross-validated with whole projects held out: function hit@10. Current pair: two adapters trained on Python only. A, B, C: one adapter trained on all six languages (A: the shipped recipe; B: larger groups, two epochs, language-balanced; C: B's recipe on a 4B model). $^*$ passes the rule (gain $\\geq$ 2 points, Holm $p<0.05$).}",
             f"\\label{{{label}}}", "\\begin{tabular}{lrrrrrr}", "\\toprule",
             "Language & Bugs & No reranker & Python pair & A & B & C \\\\", "\\midrule"]  # fmt: skip
    for lang in LANG:
        r = {x: c[x][lang] for x in cols}
        cells = [f"{pct(r[x]['with'])}{'$^*$' if r[x]['passes'] else ''}" for x in cols]
        lines.append(
            f"{LANG[lang]} & {r['A']['issues']} & {pct(r['A']['website'])} & "
            + " & ".join(cells)
            + " \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def numbers() -> str:
    full, full198, short198 = (
        analysis("fresh-full"),
        analysis("fresh-full-agents"),
        analysis("fresh-agents"),
    )
    gold = [
        json.loads(line) for line in (ROOT / "data" / "fresh" / "gold.jsonl").open(encoding="utf-8")
    ]
    m = json.loads((ROOT / "data" / "fresh" / "manifest.json").read_text(encoding="utf-8"))
    rep = short198.get("repeatability") or {}

    def h(a, s, k="hit@10"):
        return pct(a["systems"][s][k])

    esc = short198["escalation"].get("claude-agent", {}).get("chosen", {})
    out = {
        "NBugs": len(gold),
        "NProjects": len({r["repo"] for r in gold}),
        "NAgent": len(m["agent_subsample"]),
        "NCandidates": f"{m['candidates']:,}",
        "NUsable": f"{m['usable']:,}",
        "GoldHash": m["gold_sha256"][:16],
        "NLonger": sum(
            1
            for r in map(
                json.loads, (ROOT / "data" / "fresh-full" / "gold.jsonl").open(encoding="utf-8")
            )
            if len(r["text"]) > len(next(g for g in gold if g["id"] == r["id"])["text"])
        ),
        "AFgpuFullAll": h(full, "website-gpu"),
        "AFbrowserFullAll": h(full, "website"),
        "AFgpuFullAgents": h(full198, "website-gpu"),
        "LunaAgentFull": h(full198, "codex-agent"),
        "AFgpuShortAgents": h(short198, "website-gpu"),
        "ClaudeAgentShort": h(short198, "claude-agent"),
        "AstraAgentShort": h(short198, "codex-agent-astra"),
        "AstraSingleShort": h(short198, "codex-single-astra"),
        "AFgpuHitOneShort": h(short198, "website-gpu", "hit@1"),
        "AstraAgentHitOneShort": h(short198, "codex-agent-astra", "hit@1"),
        "CascadeClaude": pct(esc.get("hit@10", 0)),
        "CascadeClaudeEscalated": pct(esc.get("escalated", 0)),
        "CascadeClaudeRandom": pct(esc.get("random_hit@10", 0)),
        "RepeatSingleChanged": (rep.get("codex-single-astra") or {}).get(
            "hit@10_outcome_changed", "--"
        ),
        "RepeatSingleN": (rep.get("codex-single-astra") or {}).get("issues", "--"),
        "RepeatAgentChanged": (rep.get("codex-agent-astra") or {}).get(
            "hit@10_outcome_changed", "--"
        ),
        "RepeatAgentN": (rep.get("codex-agent-astra") or {}).get("issues", "--"),
        "CostClaudeAgent": money(cost_per_bug("fresh-agents", "claude-agent")),
        "CostAstraAgent": money(cost_per_bug("fresh-agents", "codex-agent-astra")),
        "CostAstraSingle": money(cost_per_bug("fresh-agents", "codex-single-astra")),
        "CostAFgpu": money(cost_per_bug("fresh-full-agents", "website-gpu")),
    }
    return "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in out.items()) + "\n"


def results_macros() -> str:
    out = [
        r"\newcommand{\res}[3]{\ifcsname r@#1@#2@#3\endcsname\csname r@#1@#2@#3\endcsname\else\textbf{\textcolor{red}{pending}}\fi}",
        r"\newcommand{\setres}[4]{\expandafter\def\csname r@#1@#2@#3\endcsname{#4}}",
    ]

    def put(name: str, system: str, key: str, value: str) -> None:
        out.append(rf"\setres{{{name}}}{{{system}}}{{{key}}}{{{value}}}")

    for name in ("fresh-full-agents", "fresh-full", "fresh-agents", "fresh"):
        a = analysis(name)
        for system, e in a["systems"].items():
            for m in ("hit@1", "hit@5", "hit@10", "all@10"):
                lo, hi = e[f"{m}_ci95"]
                put(name, system, m, pct(e[m]))
                put(name, system, f"{m}-ci", f"{pct(lo)}--{pct(hi)}")
            put(name, system, "mrr", f"{e['mrr']:.3f}")
            put(name, system, "n", str(e["issues"]))
            put(name, system, "cost", money(cost_per_bug(name, system)))
        families = [("", a["paired"])]
        if "also_reference" in a:
            families.append(("browser-", a["also_reference"]["paired"]))
        for prefix, paired in families:
            for key, v in paired.items():
                system, m = key.split(":", 1)
                if m not in ("hit@1", "hit@10"):
                    continue
                put(name, system, f"{prefix}d{m}", f"{v['delta'] * 100:+.1f}")
                put(name, system, f"{prefix}wl{m}", f"{v['wins']}/{v['losses']}")
                put(name, system, f"{prefix}p{m}", pvalue(v.get("p_holm")))
        for system, strata in a["strata"].items():
            for stratum, v in strata.items():
                put(name, system, f"s-{stratum}", pct(v["hit@10"]))
                put(name, system, f"sn-{stratum}", str(v["issues"]))
        for system, e in a["escalation"].items():
            if c := e.get("chosen"):
                for k in ("escalated", "hit@10", "random_hit@10"):
                    put(name, system, f"esc-{k}", pct(c[k]))
    return "\n".join(out) + "\n"


def fit(text: str) -> str:
    if not text.startswith("\\begin{table}"):
        return text
    text = text.replace("\\begin{tabular}", "\\resizebox{\\columnwidth}{!}{\\begin{tabular}", 1)
    return text.replace("\\end{tabular}", "\\end{tabular}}", 1)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "dataset.tex": dataset_table("tab:dataset"),
        "main_full_agents.tex": systems_table(
            "fresh-full-agents",
            "website-gpu",
            "Full bug reports, the 198-bug agent subset: every free system and Allfather. hit@k: a function the fix changed is in the top $k$; all@10: every changed function is in the top 10. 95\\% intervals from a bootstrap over projects. $\\Delta$: against Allfather + GPU reranker, with wins/losses and the exact paired test, Holm-adjusted across the table.",
            "tab:full198",
        ),  # fmt: skip
        "main_full_all.tex": systems_table(
            "fresh-full",
            "website-gpu",
            "Full bug reports, all 580 bugs: the systems that ran on the whole set. Columns as in Table~\\ref{tab:full198}.",
            "tab:full580",
        ),  # fmt: skip
        "main_short_agents.tex": systems_table(
            "fresh-agents",
            "website-gpu",
            "Shortened bug reports (title and first 1,500 characters of the body), the 198-bug agent subset, including the paid frontier agents. Columns as in Table~\\ref{tab:full198}.",
            "tab:short198",
        ),  # fmt: skip
        "languages_full_all.tex": language_table(
            "fresh-full",
            "Function hit@10 by language, full reports, all 580 bugs. Bold: best in the column.",
            "tab:languages",
        ),
        "escalation.tex": escalation_table("fresh-full-agents", "tab:escalation"),
        "escalation_short.tex": escalation_table("fresh-agents", "tab:escalation-short"),
        "results.tex": results_macros(),
        "conditions.tex": condition_table("tab:conditions"),
        "reranker.tex": reranker_table("tab:reranker"),
        "numbers.tex": numbers(),
    }
    for name, text in files.items():
        (OUT / name).write_text(fit(text), encoding="utf-8", newline="\n")
    print(f"wrote {len(files)} files to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
