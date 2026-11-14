"""Write every table and number the paper uses, from the committed results only.

    uv run python scripts/paper_tables.py --out reports/paper-tables-review

Reads results/research/analysis_<set>.json, the run records in results/research/frontier/ (for cost
and time), data/fresh/ (for the test set's composition) and the reranker study's choice.json, and
writes docs/paper/generated/: one .tex file per table and numbers.tex, a list of \\newcommand macros
the text uses instead of typing numbers. Monetary accounting shares the analysis module's
per-record evidence rules. Missing costs remain unknown; historical aggregate token counts
and unattributed wall times are not silently converted into list-price or GPU estimates.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "research"
RUNS = RESULTS / "frontier"
OUT = ROOT / "docs" / "paper" / "generated"
sys.path.insert(0, str(ROOT / "scripts"))
from fresh_analysis import load_set, per_issue  # noqa: E402

from allfather.eval.costs import (  # noqa: E402
    cost_from_scored,
    nonnegative,
    selected_costs,
    summarize,
)

NAMES = {
    "website-gpu": "\\toolgpu{}",
    "website": "\\tool{}, browser only",
    "website-files": "\\tool{}, file ranker",
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
MIN_ISSUES = 50
CHECK = "\\checkmark"


def analysis(name: str) -> dict:
    return json.loads((RESULTS / f"analysis_{name}.json").read_text(encoding="utf-8"))


def rows(set_name: str, system: str) -> list[dict]:
    path = RUNS / f"{set_name}_{system}.jsonl"
    return [json.loads(line) for line in path.open(encoding="utf-8")] if path.exists() else []


def cost_per_bug(set_name: str, system: str) -> float | None:
    rs = rows(set_name, system)
    if not rs:
        return None
    _, items = load_set(set_name)
    scored = per_issue(rs, items)
    return summarize([cost_from_scored(r) for r in scored.values()])["mean_usd"]


def median_seconds(set_name: str, system: str) -> float | None:
    timings = [nonnegative(r.get("seconds")) for r in rows(set_name, system)]
    return st.median(timings) if timings and all(t is not None for t in timings) else None


def cascade_cost(set_name: str, reference: str, system: str, threshold: float) -> dict:
    _, items = load_set(set_name)
    ref, other = (per_issue(rows(set_name, s), items) for s in (reference, system))
    ids = sorted(set(ref) & set(other))
    if any(ref[q]["confidence"] is None for q in ids):
        raise ValueError("cascade requires observed confidence for every paired issue")
    return selected_costs(ref, other, ids, [ref[q]["confidence"] < threshold for q in ids])


def pct(x: float) -> str:
    return f"{x * 100:.1f}"


def money(x: float | None) -> str:
    if x is None:
        return "--"
    if x == 0:
        return "\\$0"
    return f"\\${x:.3f}" if x < 0.1 else f"\\${x:.2f}"


def pmath(p: float | None) -> str:
    if p is None:
        return "=?"
    return "<0.001" if p < 0.001 else f"={p:.3f}"


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
             "\\caption{Confidence-gated escalation (RQ3): the bugs \\tool{} is least confident about, at the threshold fixed before the study (0.7899), go to an agent; the rest keep \\tool{}'s answer. Random escalates the same share at random.}",
             f"\\label{{{label}}}", "\\begin{tabular}{lrrrrr}", "\\toprule",
             "Agent & Escalated & Cascade & Random & Agent alone & Cascade cost/bug \\\\", "\\midrule"]  # fmt: skip
    for s, e in sorted(a["escalation"].items(), key=lambda kv: -kv[1]["chosen"]["hit@10"]):
        if s not in NAMES or "agent" not in s:
            continue
        c = e["chosen"]
        accounting = cascade_cost(set_name, a["reference"], s, c["threshold"])
        lines.append(
            f"{NAMES[s]} & {pct(c['escalated'])}\\% & {pct(c['hit@10'])} & {pct(c['random_hit@10'])} & "
            f"{pct(e['other_hit@10'])} & {money(accounting['mean_usd'])} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def outcomes(set_name: str, system: str) -> dict[str, float]:
    _, items = load_set(set_name)
    return {q: v["hit@10"] for q, v in per_issue(rows(set_name, system), items).items()}


def condition_table(label: str) -> str:
    rows_out = []
    for short, full in (("fresh-agents", "fresh-full-agents"), ("fresh", "fresh-full")):
        s, f = analysis(short), analysis(full)
        for name in sorted(
            set(s["systems"]) & set(f["systems"]), key=lambda x: -f["systems"][x]["hit@10"]
        ):
            if name not in NAMES:
                continue
            a, b = outcomes(short, name), outcomes(full, name)
            common = sorted(set(a) & set(b))
            if len(common) < MIN_ISSUES:
                continue
            x = sum(a[q] for q in common) / len(common)
            y = sum(b[q] for q in common) / len(common)
            rows_out.append(
                f"{NAMES[name]} & {len(common)} & {pct(x)} & {pct(y)} & {(y - x) * 100:+.1f} \\\\"
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
    vetted = [
        json.loads(line)
        for line in (ROOT / "data" / "fresh" / "vetted.jsonl").open(encoding="utf-8")
    ]
    excluded = [v["excluded"] for v in vetted if v["excluded"]]
    out = {
        "NVetted": len(vetted),
        "NVetExcluded": len(excluded),
        "NVetAI": sum("AI-written" in e for e in excluded),
        "NVetBot": sum("AI-written" not in e for e in excluded),
        "NBugs": len(gold),
        "NProjects": len({r["repo"] for r in gold}),
        "NAgent": len(m["agent_subsample"]),
        "NCandidates": f"{m['candidates']:,}",
        "NUsable": f"{m['usable']:,}",
        "GoldHash": m["gold_sha256"][:8],
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
            seconds = median_seconds(name, system)
            put(name, system, "sec", f"{seconds:.1f}" if seconds is not None else "--")
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
                put(name, system, f"{prefix}p{m}", pmath(v.get("p_holm")))
        for system, strata in a["strata"].items():
            for stratum, v in strata.items():
                put(name, system, f"s-{stratum}", pct(v["hit@10"]))
                put(name, system, f"sn-{stratum}", str(v["issues"]))
        for system, e in a["escalation"].items():
            if c := e.get("chosen"):
                for k in ("escalated", "hit@10", "random_hit@10"):
                    put(name, system, f"esc-{k}", pct(c[k]))
    return "\n".join(out) + "\n"


FIGURE_SYSTEMS = [
    "website-gpu",
    "website",
    "codex-agent",
    "codex-single",
    "gemini-single",
    "open-agent-qwen3-coder-next-fp8",
    "open-single-qwen3-coder-next-fp8",
    "open-agent-gpt-oss-120b",
    "open-single-gpt-oss-120b",
    "codex-agent-astra",
    "codex-single-astra",
    "claude-agent",
]
FREE_FLOOR = 1e-4


def cost_figure(set_name: str, label: str, caption: str) -> str:
    a = analysis(set_name)
    points = []
    for s in FIGURE_SYSTEMS:
        e = a["systems"].get(s)
        if not e or e["issues"] < MIN_ISSUES:
            continue
        c = cost_per_bug(set_name, s)
        if c is None:
            continue
        points.append((max(c, FREE_FLOOR), e["hit@10"] * 100, NAMES[s], s in FREE))
    lines = [
        "\\begin{figure}[t]",
        "\\centering",
        "\\begin{tikzpicture}",
        "\\begin{axis}[width=0.92\\linewidth, height=6.2cm, xmode=log, xmin=5e-5, xmax=2,",
        "  xlabel={Recorded run charge per bug (US\\$, log scale)}, ylabel={Function hit@10 (\\%)},",
        "  ymin=20, ymax=100, grid=major, grid style={gray!20}, tick label style={font=\\footnotesize},",
        "  label style={font=\\small}, legend style={font=\\footnotesize, at={(0.98,0.03)}, anchor=south east}]",
    ]
    for free, style, name in (
        (True, "mark=*, color=black", "free to use"),
        (False, "mark=triangle*, color=gray", "paid"),
    ):
        coords = " ".join(f"({x:.6f},{y:.2f})" for x, y, _, f in points if f == free)
        if coords:
            lines.append(
                f"\\addplot[only marks, {style}, mark size=2.4pt] coordinates {{{coords}}};"
            )
            lines.append(f"\\addlegendentry{{{name}}}")
    for x, y, n, _ in points:
        lines.append(
            f"\\node[font=\\scriptsize, anchor=west] at (axis cs:{x * 1.25:.6f},{y:.2f}) {{{n}}};"
        )
    lines += [
        "\\end{axis}",
        "\\end{tikzpicture}",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\end{figure}",
        "",
    ]
    return "\n".join(lines)


def escalation_figure(label: str, caption: str) -> str:
    panels = []
    for set_name, system, title in (
        ("fresh-full-agents", "codex-agent", "Full reports, gpt-6-luna agent"),
        ("fresh-agents", "claude-agent", "Shortened reports, Claude Opus 5.5 agent"),
    ):
        e = analysis(set_name)["escalation"].get(system)
        if not e:
            continue
        curve = sorted(e["curve"], key=lambda p: p["escalated"])
        gate = " ".join(f"({p['escalated'] * 100:.2f},{p['hit@10'] * 100:.2f})" for p in curve)
        rand = " ".join(
            f"({p['escalated'] * 100:.2f},{p['random_hit@10'] * 100:.2f})" for p in curve
        )
        c = e["chosen"]
        panels.append(
            "\n".join(
                [
                    "\\begin{tikzpicture}",
                    f"\\begin{{axis}}[width=0.49\\linewidth, height=5.4cm, title={{\\small {title}}}, xmin=0, xmax=100, ymin=55, ymax=100,",
                    "  xlabel={Bugs escalated (\\%)}, ylabel={Function hit@10 (\\%)}, grid=major, grid style={gray!20},",
                    "  tick label style={font=\\footnotesize}, label style={font=\\small}, legend style={font=\\footnotesize, at={(0.98,0.03)}, anchor=south east}]",
                    f"\\addplot[thick, color=black, mark=none] coordinates {{{gate}}};",
                    "\\addlegendentry{confidence gate}",
                    f"\\addplot[thick, dashed, color=gray, mark=none] coordinates {{{rand}}};",
                    "\\addlegendentry{random}",
                    f"\\addplot[only marks, mark=*, mark size=2.6pt, color=black, forget plot] coordinates {{({c['escalated'] * 100:.2f},{c['hit@10'] * 100:.2f})}};",
                    f"\\node[font=\\scriptsize, anchor=south east] at (axis cs:{c['escalated'] * 100:.2f},{c['hit@10'] * 100 + 1:.2f}) {{fixed threshold}};",
                    "\\end{axis}",
                    "\\end{tikzpicture}",
                ]
            )
        )
    return "\n".join(
        [
            "\\begin{figure}[t]",
            "\\centering",
            "\\hfill".join(panels),
            f"\\caption{{{caption}}}",
            f"\\label{{{label}}}",
            "\\end{figure}",
            "",
        ]
    )


def hitk_figure(set_name: str, label: str, caption: str) -> str:
    a = analysis(set_name)
    chosen = [s for s in ("website-gpu", "website", "codex-agent", "swerank-embed-large", "open-agent-qwen3-coder-next-fp8", "gemini-single", "codex-single")
              if a["systems"].get(s, {}).get("issues", 0) >= MIN_ISSUES]  # fmt: skip
    marks = ["*", "o", "triangle*", "square*", "diamond*", "triangle", "square"]
    lines = [
        "\\begin{figure}[t]",
        "\\centering",
        "\\begin{tikzpicture}",
        "\\begin{axis}[width=0.7\\linewidth, height=6cm, xtick={1,5,10}, xmin=0.5, xmax=10.5, ymin=10, ymax=90,",
        "  xlabel={$k$}, ylabel={Function hit@$k$ (\\%)}, grid=major, grid style={gray!20}, tick label style={font=\\footnotesize},",
        "  label style={font=\\small}, legend style={font=\\footnotesize, at={(1.03,0.5)}, anchor=west}]",
    ]
    for s, m in zip(chosen, marks, strict=False):
        e = a["systems"][s]
        coords = " ".join(f"({k},{e[f'hit@{k}'] * 100:.2f})" for k in (1, 5, 10))
        lines.append(f"\\addplot[mark={m}, color=black] coordinates {{{coords}}};")
        lines.append(f"\\addlegendentry{{{NAMES[s]}}}")
    lines += [
        "\\end{axis}",
        "\\end{tikzpicture}",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\end{figure}",
        "",
    ]
    return "\n".join(lines)


def no_answer_table(set_name: str, label: str) -> str:
    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\caption{Bugs for which a system returned no function, full reports, 198-bug subset. Each counts as a miss. \\emph{Turns}: the agent used all 40 turns and a final request without answering; \\emph{Context}: the prompt or conversation outgrew the model's context; \\emph{Empty}: the reply had no function that could be read.}",
        f"\\label{{{label}}}",
        "\\begin{tabular}{lrrrrr}",
        "\\toprule",
        "System & Bugs & Turns & Context & Empty & Total \\\\",
        "\\midrule",
    ]
    for s in FIGURE_SYSTEMS + ["swerank-embed-large", "swerank-embed-small"]:
        rs = rows(set_name, s)
        if len(rs) < MIN_ISSUES or s not in NAMES:
            continue
        turns = context = empty = 0
        for r in rs:
            if (r.get("answer") or {}).get("functions"):
                continue
            reason = r.get("no_answer") or ""
            if reason.startswith("no answer after"):
                turns += 1
            elif reason.startswith("context full"):
                context += 1
            else:
                empty += 1
        lines.append(
            f"{NAMES[s]} & {len(rs)} & {turns} & {context} & {empty} & {turns + context + empty} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def file_table(set_name: str, label: str, caption: str) -> str:
    a = analysis(set_name)["file_level"]
    order = sorted(
        (s for s, e in a["systems"].items() if e["issues"] >= MIN_ISSUES and s in NAMES),
        key=lambda s: -a["systems"][s]["file_hit@10"],
    )
    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\begin{tabular}{lrrrrr}",
        "\\toprule",
        "System & $n$ & File hit@1 & File hit@5 & File hit@10 & $\\Delta$ hit@10 ($p_{\\mathrm{Holm}}$) \\\\",
        "\\midrule",
    ]
    for s in order:
        e = a["systems"][s]
        pr = a["paired"].get(s)
        delta = (
            "reference" if pr is None else f"{pr['delta'] * 100:+.1f} ({pvalue(pr.get('p_holm'))})"
        )
        lines.append(
            f"{NAMES[s]} & {e['issues']} & {pct(e['file_hit@1'])} & {pct(e['file_hit@5'])} & {pct(e['file_hit@10'])} & {delta} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def fit(text: str) -> str:
    if not text.startswith("\\begin{table"):
        return text
    text = text.replace(
        "\\begin{tabular}", "\\begin{adjustbox}{max width=\\linewidth}\\begin{tabular}", 1
    )
    return text.replace("\\end{tabular}", "\\end{tabular}\\end{adjustbox}", 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if args.out.exists():
        ap.error("use a new output directory; preserve historical tables")
    files = {
        "dataset.tex": dataset_table("tab:dataset"),
        "main_full_agents.tex": systems_table(
            "fresh-full-agents",
            "website-gpu",
            "Full bug reports, the 198-bug agent subset: every free system and \\tool{}. hit@k: a function the fix changed is in the top $k$; all@10: every changed function is in the top 10. 95\\% intervals from a bootstrap over projects. $\\Delta$: against \\toolgpu{}, with wins/losses and the exact paired test, Holm-adjusted across the table.",
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
        "fig_cost.tex": cost_figure(
            "fresh-full-agents",
            "fig:cost",
            "Accuracy against recorded run charge, full reports, 198-bug subset. Unknown costs are omitted, not treated as zero. Recorded charges are harness reports, not independently verified bills or total compute costs.",
        ),
        "fig_escalation.tex": escalation_figure(
            "fig:escalation",
            "Escalating the bugs \tool{} is least confident about to an agent (solid) against escalating the same number of bugs at random (dashed). The dot is the threshold fixed before the study.",
        ),
        "fig_hitk.tex": hitk_figure(
            "fresh-full-agents",
            "fig:hitk",
            "Function hit@$k$ for $k=1,5,10$, full reports, 198-bug subset.",
        ),
        "no_answer.tex": no_answer_table("fresh-full-agents", "tab:noanswer"),
        "files_full_agents.tex": file_table(
            "fresh-full-agents",
            "tab:files198",
            "File-level results, full reports, 198-bug subset. For every system, its ranked functions' files in order; \\tool{}'s file ranker (the site's Files view) is its own file-level answer. $\\Delta$: against \\toolgpu{}'s function-derived files, Holm-adjusted.",
        ),
        "files_full_all.tex": file_table(
            "fresh-full",
            "tab:files580",
            "File-level results, full reports, all 580 bugs; systems still running are shown on the bugs completed. Columns as in Table~\\ref{tab:files198}.",
        ),
    }
    args.out.mkdir(parents=True)
    for name, text in files.items():
        (args.out / name).write_text(fit(text), encoding="utf-8", newline="\n")
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
