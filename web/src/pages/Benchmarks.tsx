import { useRef } from "preact/hooks";
import { Bars } from "../components/Bars.tsx";
import { LiveSection, useLive } from "../components/Live.tsx";
import { PageHero } from "../components/PageHero.tsx";
import { Tile } from "../components/Tile.tsx";
import { RepoTable, SignificanceTable, StageChart } from "../components/Results.tsx";
import { type BrowserEval, type GpuReranker, type LanguageEval, type Lite, type Summary, stagesAt } from "../lib/data.ts";
import { pct } from "../lib/format.ts";
import { type Holdout, useHoldout } from "../lib/holdout.ts";
import { href } from "../lib/router.ts";

const FROZEN_ROWS: [keyof Holdout["runs"], string, string][] = [
  ["holdout_function", "Sealed holdout", "function"],
  ["holdout_file", "Sealed holdout", "file"],
  ["lite_function", "SWE-bench Lite", "function"],
  ["lite_file", "SWE-bench Lite", "file"],
];

function HoldoutCard({ data, research }: { data: Holdout; research: number | null }) {
  const fn = data.runs.holdout_function;
  const file = data.runs.holdout_file;
  const lite = data.runs.lite_function;
  const [lo, hi] = fn["hit@10_ci95"];
  return (
    <section class="card frame block">
      <p class="kicker">Never seen before</p>
      <h2>On bugs filed after its models, in projects it never saw</h2>
      <p class="card-lede">
        A sealed set of recent bugs from 189 projects that appear nowhere in training, tuning or testing: {fn.issues} with a function to find
        and {file.issues} at file level, all filed after the pretrained models in the pipeline were published. The pipeline, allfather-fast, was
        frozen, every model hashed and every metric declared in advance, and then scored on it once per level.
      </p>
      <div class="table-wrap" tabIndex={0} role="region" aria-label="The frozen pipeline on the sealed holdout and on SWE-bench Lite">
        <table class="label-first">
          <thead><tr><th>Bugs</th><th class="phone-hide-col">Level</th><th class="phone-hide-col">Count</th><th>Top 10</th><th>Top 5</th><th class="phone-hide-col">Ranked first</th><th class="phone-hide-col wrap">All in top 10</th></tr></thead>
          <tbody>
            {FROZEN_ROWS.map(([key, set, level]) => {
              const r = data.runs[key];
              return (
                <tr key={key}>
                  <td class="label-cell">{set}<span class="phone-only">{level} · {r.issues} bugs</span></td>
                  <td class="phone-hide-col">{level}</td>
                  <td class="num phone-hide-col">{r.issues}</td>
                  <td class="num">{pct(r["hit@10"])}</td>
                  <td class="num">{pct(r["hit@5"])}</td>
                  <td class="num phone-hide-col">{pct(r["hit@1"])}</td>
                  <td class="num phone-hide-col">{pct(r["all@10"])}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p class="note">
        Function in the top 10 on the holdout: {pct(fn["hit@10"])}, 95% interval {pct(lo)} to {pct(hi)}. It finds one of the changed functions
        about as often as on Lite, but finding all of them is harder: these fixes change three functions on average against about one on Lite, and
        a fix with more changed functions is also easier to hit once. The two sets differ in projects, fix size and date, so this describes them
        rather than comparing them.
      </p>
      {research != null && (
        <p class="note">
          The Lite rows here are allfather-fast. The tiles and charts above show the research configuration it grew from, which scores{" "}
          {pct(research)} on Lite against allfather-fast's {pct(lite["hit@10"])}. Of the 291 issues, 13 come out differently, 8 in the research
          configuration's favour and 5 in allfather-fast's: not significant (exact paired test, p = 0.58). allfather-fast's rankers were trained on more data, and it is the system the holdout
          measures.
        </p>
      )}
    </section>
  );
}

function BrowserComparison({ e, full, depth }: { e: BrowserEval; full?: number; depth: number }) {
  const rows = [
    { label: "Keyword search only", value: e.keyword["hit@10"] },
    { label: "Instant ranking", value: e.instant["hit@10"], detail: "keyword and mention signals, milliseconds" },
    { label: "+ semantic index", value: e.semantic["hit@10"], detail: "every function embedded in the background", emphasis: !e.rerank },
    ...(e.rerank ? [{ label: `+ language-model rerank of the top ${depth}`, value: e.rerank["hit@10"], emphasis: true }] : []),
    ...(full != null ? [{ label: "Full research pipeline (GPU)", value: full, detail: "larger models, git history, LLM reranker" }] : []),
  ];
  return <Bars label="Function in the top 10, by in-browser stage" format={pct} rows={rows} />;
}

function FileComparison({ e }: { e: BrowserEval }) {
  const rows = [
    { label: "Files of the best functions", value: e.files_best_function["hit@5"] },
    { label: "File ranker", value: e.files["hit@5"], emphasis: true },
  ];
  return <Bars label="File in the top 5" format={pct} rows={rows} />;
}

/** Three terms the page uses, in plain words, before any chart. */
const GUIDE: [string, string][] = [
  ["Top 10", "hit@10: the share of issues with at least one gold function among the first 10 results; recall@10 counts every gold function."],
  ["Ranked first", "hit@1: the top-ranked unit is gold. MRR averages 1/rank of the first gold unit, so it rewards near misses too."],
  ["Significant", "A paired test on the same issues (a randomization test, exact for yes-or-no outcomes), with p adjusted by Holm's method for the number of tests in the table: ✓ when the adjusted p < 0.05."],
];

export function Benchmarks({ summary, lite, failed }: { summary: Summary | null; lite: Lite | null; failed: boolean }) {
  const root = useRef<HTMLDivElement>(null);
  const fn = summary ? stagesAt(summary, "function").at(-1)! : null;
  const fl = summary ? stagesAt(summary, "file").at(-1)! : null;
  const live = useLive();
  const holdout = useHoldout();
  return (
    <div class="container" ref={root}>
      <PageHero kicker="Benchmarks" title="How often Allfather finds the fix">
        <p>
          Measured on SWE-bench Lite: 300 real GitHub issues from 12 Python projects. Each is searched at the commit where the bug was
          reported, and a result counts only if the maintainers' actual fix changed it. None of these issues was used for training, but the
          rankers trained on other issues from the same 12 projects, and Lite guided development, so the clean test is the sealed holdout
          below.
        </p>
      </PageHero>
      {failed && <p class="error-text">Couldn't load the benchmark data. Try reloading the page.</p>}
      {!failed && (
        <div class="tiles">
          <Tile label="Function to fix in the top 10" value={fn ? fn["hit@10"] : null} ci={fn?.ci95["hit@10"]} note={fn ? `${fn.n} issues, 400 to 31,000 functions per snapshot` : "SWE-bench Lite"} />
          <Tile label="Function to fix ranked first" value={fn ? fn["hit@1"] : null} ci={fn?.ci95["hit@1"]} note={fn ? `${fn.n} issues: 300 minus ${300 - fn.n} with no function to find` : "SWE-bench Lite"} />
          <Tile label="File to fix in the top 5" value={fl ? fl["hit@5"] : null} ci={fl?.ci95["hit@5"]} note={fl ? `file level, all ${fl.n} issues` : "SWE-bench Lite"} />
        </div>
      )}

      <dl class="guide">
        {GUIDE.map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}
      </dl>

      {holdout && <HoldoutCard data={holdout} research={fn ? fn["hit@10"] : null} />}

      {summary && (
        <>
          <section class="card frame block">
            <p class="kicker">Stage by stage</p>
            <h2>What each stage adds</h2>
            <p class="card-lede">
              hit@k, recall@10 and MRR per stage, over 291 issues at function level and 300 at file level. At function level every stage
              finds more; at file level the last two mostly move the right file up, not into the top 10. Whiskers are 95% bootstrap intervals;
              hover for sample size and median latency per query, measured on a laptop GPU (RTX 4050).
            </p>
            <StageChart summary={summary} />
          </section>

          <section class="card frame block">
            <p class="kicker">No lucky gains</p>
            <h2>Is each step a real improvement?</h2>
            <p class="card-lede">Every step is tested against the one before it on the same bugs, so a gain from luck shows up as not significant.</p>
            <SignificanceTable summary={summary} />
          </section>

          <section class="card frame block">
            <p class="kicker">By project</p>
            <h2>Where it's easy, and where it's hard</h2>
            <p class="card-lede">Share of fix locations in the top 10, per project. pytest, whose bug reports rarely name the code, gains more than most from the smarter stages.</p>
            <RepoTable summary={summary} />
          </section>
        </>
      )}

      {lite && (
        <section class="card frame block">
          <p class="kicker">In your browser</p>
          <h2>On projects it has never seen</h2>
          <p class="card-lede">
            The <a href={href("search")}>search page</a> runs a lighter pipeline on your device. Its rankers were trained on 192 other
            projects in six languages; these {lite.held_out.unseen.keyword.n} bugs come from 30 projects that were kept out of training entirely, the
            situation the search page is in every time you paste a new repository.
          </p>
          <BrowserComparison e={lite.held_out.unseen} depth={lite.depth} />
          <p class="note">Share of bugs with a function the real fix changed in the top 10.</p>
          <h3 class="subhead">Finding the file</h3>
          <FileComparison e={lite.held_out.unseen} />
          <p class="note">Share of bugs with a file the real fix changed in the top 5.</p>
        </section>
      )}

      {lite?.held_out_per_language && <Languages sets={lite.held_out_per_language} />}

      {lite?.gpu_reranker && <Gpu g={lite.gpu_reranker} />}

      {lite && fn && (
        <section class="card frame block">
          <p class="kicker">In your browser</p>
          <h2>On SWE-bench Lite</h2>
          <p class="card-lede">The same pipeline on the {lite.held_out.lite.keyword.n} Lite issues above, next to the full GPU pipeline.</p>
          <BrowserComparison e={lite.held_out.lite} depth={lite.depth} full={fn["hit@10"]} />
          <p class="note">Share of issues with a function the real fix changed in the top 10.</p>
        </section>
      )}

      {live && <LiveSection live={live} />}

      <section class="card frame block">
        <p class="kicker">Method</p>
        <h2>How the numbers are kept honest</h2>
        <ul class="plain-list">
          <li>Every issue is searched at its own base commit. Indexing today's code would leak the fix.</li>
          <li>Nothing is trained on these 300 issues: fusion weights on a separate dev set, the learned rankers on 1,941 other SWE-bench issues (5,115 for allfather-fast), reranker weights on a held-out split. The ranker's cross-validation was split by issue, not by project, and the code embedding model (jina-code-embeddings) lists SWE-bench among its own training data, so Lite and development numbers may be optimistic; the sealed holdout is free of both.</li>
          <li>Git-history features only see commits before the bug; "similar past bugs" only see issues opened at least 30 days earlier. Both boundaries have tests.</li>
          <li>Every comparison on this page comes with a paired test on the same issues and a 95% bootstrap interval, with p adjusted for the number of tests in each table. Results that aren't significant are reported as such.</li>
          <li>Lite is not untouched. It has been evaluated 92 times, each logged with what was decided from it, and one decision, rejecting a distilled reranker, was taken on a Lite result, in the conservative direction.</li>
        </ul>
      </section>
    </div>
  );
}

const LANGUAGE_NAMES: Record<string, string> = { go: "Go", java: "Java", javascript: "JavaScript", rust: "Rust", typescript: "TypeScript" };
const SET_NAMES: Record<string, string> = { multilingual: "Multilingual", polybench: "PolyBench" };

function Languages({ sets }: { sets: Record<string, Record<string, LanguageEval>> }) {
  const rows = Object.entries(sets).flatMap(([set, langs]) =>
    Object.entries(langs).filter(([lang]) => lang in LANGUAGE_NAMES && langs[lang].issues >= 10).map(([lang, e]) => ({ set, lang, e })));
  return (
    <section class="card frame block">
      <p class="kicker">In your browser</p>
      <h2>In five more languages</h2>
      <p class="card-lede">
        Bugs from two public test sets, SWE-bench Multilingual and SWE-PolyBench, in projects the rankers never trained on. Allfather's learned
        ranker against ranking by keywords and meaning alone, the simpler signal the site would fall back to; the GPU reranker is not used for
        these languages. The sets were rescored after fixing labels and stale caches (logged; nothing was decided from them).
      </p>
      <div class="table-wrap" tabIndex={0} role="region" aria-label="Accuracy by language">
        <table>
          <thead><tr><th>Language</th><th class="phone-hide-col">Test set</th><th class="phone-hide-col">Bugs</th><th>Allfather</th><th class="wrap">Keywords and meaning</th><th>Change</th><th class="phone-hide-col">p</th><th class="phone-hide-col wrap">Adjusted p</th></tr></thead>
          <tbody>
            {rows.map(({ set, lang, e }) => {
              const g = e["hit@10_gain"];
              const adjusted = g.p_holm ?? g.p;
              return (
                <tr key={`${set}:${lang}`}>
                  <td class="label-cell">
                    {LANGUAGE_NAMES[lang]}
                    <span class="phone-only">{SET_NAMES[set] ?? set} · {e.issues} bugs</span>
                  </td>
                  <td class="phone-hide-col">{SET_NAMES[set] ?? set}</td>
                  <td class="num phone-hide-col">{e.issues}</td>
                  <td class="num">{pct(e.learned["hit@10"])}</td>
                  <td class="num">{pct(e.keyword_and_meaning["hit@10"])}</td>
                  <td class={`num${adjusted < 0.05 && g.delta > 0 ? " sig" : ""}`}>{g.delta >= 0 ? "+" : ""}{(g.delta * 100).toFixed(1)}</td>
                  <td class="num phone-hide-col">{g.p < 0.001 ? "<0.001" : g.p.toFixed(3)}</td>
                  <td class="num phone-hide-col">{adjusted < 0.001 ? "<0.001" : adjusted.toFixed(3)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p class="note">
        Share of bugs with a function the real fix changed in the top 10. p: exact paired test on each row. Adjusted p: Holm's correction across
        the {rows.length} rows. Bold changes are significant after adjustment (p &lt; 0.05); a small set can show a real gain that is not.
      </p>
    </section>
  );
}

function Gpu({ g }: { g: GpuReranker }) {
  const rows: [string, Record<string, number>][] = [
    ["The browser's ranking", g.website],
    ["With the GPU reranker", g.with_reranker],
    ["GPU reranker, no browser language model (what the site runs)", g.without_language_model],
  ];
  const gain = g["hit@10_gain"];
  return (
    <section class="card frame block">
      <p class="kicker">On a GPU server</p>
      <h2>The fine-tuned reranker</h2>
      <p class="card-lede">
        For a Python repository, the search page can send your bug report and its top 50 functions to a GPU, where the full pipeline's
        reranker re-reads them.
        Measured before it was built, by cross-validation on {g.issues.toLocaleString()} bugs from {g.projects} projects the reranker never
        trained on: function hit@10 {gain.delta >= 0 ? "+" : ""}{(gain.delta * 100).toFixed(1)} points (95% interval {(gain.ci95[0] * 100).toFixed(1)} to{" "}
        {(gain.ci95[1] * 100).toFixed(1)}, p {gain.p_value < 0.001 ? "< 0.001" : `= ${gain.p_value.toFixed(3)}`}).
      </p>
      <div class="table-wrap" tabIndex={0} role="region" aria-label="The GPU reranker's effect">
        <table class="label-first">
          <thead><tr><th>Ranking</th><th>hit@1</th><th>hit@5</th><th>hit@10</th><th>MRR</th></tr></thead>
          <tbody>
            {rows.map(([label, m]) => (
              <tr key={label}>
                <td>{label}</td>
                <td class="num">{pct(m["hit@1"])}</td>
                <td class="num">{pct(m["hit@5"])}</td>
                <td class="num">{pct(m["hit@10"])}</td>
                <td class="num">{m.mrr.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p class="note">Cross-validated on training projects.</p>
      {g.held_out && (
        <>
          <h3 class="subhead">Held out, scored once</h3>
          <div class="table-wrap" tabIndex={0} role="region" aria-label="The GPU reranker on held-out sets">
            <table class="label-first">
              <thead><tr><th>Bugs</th><th>Without the GPU</th><th>With it</th><th>Change</th><th class="phone-hide-col">95% interval</th></tr></thead>
              <tbody>
                {Object.entries(g.held_out).map(([set, h]) => {
                  const d = h["hit@10_gain"];
                  return (
                    <tr key={set}>
                      <td>{set === "lite" ? "SWE-bench Lite" : "30 unseen projects"} <span class="muted">({h.issues})</span></td>
                      <td class="num">{pct(h.website["hit@10"])}</td>
                      <td class="num">{pct(h.with_reranker["hit@10"])}</td>
                      <td class={`num${d.p_value < 0.05 && d.delta > 0 ? " sig" : ""}`}>{d.delta >= 0 ? "+" : ""}{(d.delta * 100).toFixed(1)}</td>
                      <td class="num phone-hide-col">{(d.ci95[0] * 100).toFixed(1)} to {(d.ci95[1] * 100).toFixed(1)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p class="note">Function in the top 10, what the site runs (the GPU reranker blended into the browser's semantic ranking), on projects nothing was trained on.</p>
        </>
      )}
    </section>
  );
}
