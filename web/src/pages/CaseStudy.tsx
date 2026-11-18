import { useRef } from "preact/hooks";
import { useLive } from "../components/Live.tsx";
import { PageHero } from "../components/PageHero.tsx";
import { Tile } from "../components/Tile.tsx";
import { bestBrowserStage, type Lite, type Summary, stagesAt } from "../lib/data.ts";
import { LIVE_MIN_BUGS } from "../lib/feedback.ts";
import { useHoldout } from "../lib/holdout.ts";
import { href } from "../lib/router.ts";


function decisions(lite: Lite | null): [string, string][] {
  const gains = Object.values(lite?.cv_per_language ?? {}).map((e) => e["hit@10_gain"].delta * 100);
  const range = gains.length ? ` All ${gains.length} passed, by ${Math.min(...gains).toFixed(1)} to ${Math.max(...gains).toFixed(1)} points.` : "";
  return [
    ["Measure first, build second",
      "I built the evaluation harness before the search engine: every issue is searched at the commit it was filed against, and the answer key is the functions the real fix changed. Every accuracy claim I make comes with a paired test on the same issues."],
    ["A cascade: cheap over everything, expensive over little",
      "Code-aware keyword search over every function, then learned ranking over a few hundred, then a fine-tuned language model over the top 20 to 50. I kept each stage of the full pipeline because it beats the one before at function level."],
    ["The same engine, twice",
      "I ported the Python engine to TypeScript so the website can run it in Web Workers. Parity tests run both on the same code and require identical units, keyword scores and ranker inputs, so I can measure the browser's accuracy in Python. The pinned parity run covers Python repositories; the other languages are covered by unit tests."],
    ["A GPU only where it pays",
      "I put the full pipeline's reranker on a GPU server for the website only after a test I fixed in advance showed +2.6 points; a second test showed I could then skip the browser's own language model, saving about 50 MB and 15 s. Scored once on held-out data, it adds 6.5 points on SWE-bench Lite and 2.7 on held-out projects. I trained and measured it on Python first; the site now runs one reranker trained on all six languages."],
    ["Six languages, each earning its ranker",
      `I added JavaScript, TypeScript, Go, Java and Rust under a rule I wrote before training: the learned ranker is used for a language only if it beats keywords and meaning by 2 points in cross-validation.${range}`],
    ["A reranker that travels",
      "The GPU reranker was trained on Python bugs only, so I tested it on the other five languages before training anything new. It helped all five in cross-validation, under the same 2-point rule, so I trained one reranker on all six languages, chose it by a rule fixed in advance, and switched it on for every language."],
    ["Correcting my own study",
      "I built a set of 580 recent bugs in six languages and wrote the comparison down before running anything. An outside review and an audit of my own code then found an import bug that had understated one baseline; with it fixed, Allfather's lead over SweRankEmbed-Large disappears. I withdrew that claim, rebuilt the scoring so it never consults the answer key to read a prediction, and now treat those results as exploratory."],
  ];
}

const FAILED: [string, string][] = [
  ["Following the call graph", "Expanding results to callers and callees added candidates but not hits; it is off by default."],
  ["One distilled reranker instead of two", "Better on validation, worse on the test set's first place: I rejected it, and the README says it was a test-set decision."],
  ["A learned query projection for the embeddings", "Semantic-only MRR fell from 0.287 to 0.220 on held-out projects."],
  ["A small language model in the browser", "It added nothing on held-out projects, so I replaced it with the GPU reranker."],
  ["A reranker that reads the whole report", "Retrained on 2,048-token reports, it gained 1.3 points on long reports, short of the 2-point bar I set in advance, so the site keeps the original."],
  ["Choosing the next step for each bug", "On a 47-bug pilot, no choice among wider retrieval and deeper reranking found a bug that reranking the top 50 every time missed, so I trained no router."],
];

const SAFEGUARDS = [
  "I train nothing on a test set, and I log every test-set evaluation with what I decided from it. I have evaluated on SWE-bench Lite 92 times and took one decision on it, rejecting a distilled reranker, so it is a development benchmark here, not a clean test.",
  "A recorded holdout of recent bugs from 189 projects that I excluded from every dataset I trained, tuned or tested on. I scored it once per level on 2026-10-20, after freezing the pipeline, hashing every model and declaring every metric. Excluding projects from my data does not prove the pretrained models never saw them.",
  "When an audit finds an error, I keep the original results and publish the correction beside them, with the reasoning in a decision record.",
  "Every number in the README is checked against its result file in CI, and result files from the evaluation harness record the commit, data and models behind them.",
  "I keep a decision record for every major choice, negative results included, and wrote the later ones before their tests.",
  "Unit, browser (Chromium, Firefox, WebKit) and Python/TypeScript parity tests run in CI.",
];

export function CaseStudy({ summary, lite }: { summary: Summary | null; lite: Lite | null }) {
  const root = useRef<HTMLDivElement>(null);
  const live = useLive();
  const holdout = useHoldout();
  const fn = summary ? stagesAt(summary, "function").at(-1)! : null;
  const unseen = lite ? bestBrowserStage(lite.held_out.unseen)["hit@10"] : null;
  const multi = lite?.held_out.multilingual;
  const gpu = lite?.gpu_reranker;
  const liveWindow = live?.last_30_days;
  return (
    <div class="container case-study" ref={root}>
      <PageHero kicker="Case study" title="Finding the code behind a bug report">
        <p>
          Given a bug report and a repository, Allfather ranks the functions most likely to need the fix. It is a research pipeline measured on
          real bug fixes, a website that runs a lighter version of it in your browser on public code in six languages, and a GitHub Action that comments on new issues.
        </p>
      </PageHero>

      <section class="block">
        <p class="kicker">The problem</p>
        <h2>Most of fixing a bug is finding it.</h2>
        <p class="section-lede">
          A report says what went wrong, not where. In a large repository the answer is one of tens of thousands of functions, and the report
          may name it, quote a stack trace through it, or only describe a symptom. Allfather is scored the way a developer would judge it: is a
          function the maintainers' real fix changed among the first ten it suggests?
        </p>
      </section>

      <section class="block">
        <p class="kicker">Results</p>
        <h2>Results on recorded evaluation splits</h2>
        <div class="tiles four">
          <Tile label="Recorded holdout" value={holdout ? holdout.runs.holdout_function["hit@10"] : null}
            ci={holdout?.runs.holdout_function["hit@10_ci95"]}
            note={holdout ? `allfather-fast, ${holdout.runs.holdout_function.issues} issues; project exclusions apply to declared ranker data` : ""} />
          <Tile label="SWE-bench Lite" value={holdout ? holdout.runs.lite_function["hit@10"] : fn ? fn["hit@10"] : null}
            note={holdout ? `allfather-fast, ${holdout.runs.lite_function.issues} issues from 12 projects in its training data` : fn ? `full pipeline, ${fn.n} issues` : ""} />
          <Tile label="Browser pipeline, 30 held-out projects" value={gpu?.held_out?.unseen ? gpu.held_out.unseen.website["hit@10"] : unseen}
            note={gpu?.held_out?.unseen
              ? `${gpu.held_out.unseen.issues} bugs, Python; ${Math.round(gpu.held_out.unseen.with_reranker["hit@10"] * 1000) / 10}% with the first, Python-only GPU reranker`
              : lite ? `${lite.held_out.unseen.keyword.n} bugs, Python` : ""} />
          {liveWindow && liveWindow.bugs >= LIVE_MIN_BUGS && liveWindow.function ? (
            <Tile label="Live, bugs fixed this month" value={liveWindow.function["hit@10"]} note={`${liveWindow.bugs} bugs from ${liveWindow.projects} projects`} />
          ) : (
            <Tile label="In the browser, five more languages" value={multi ? bestBrowserStage(multi)["hit@10"] : null} note={multi ? `${multi.keyword.n} bugs, SWE-bench Multilingual` : ""} />
          )}
        </div>
        <p class="note">
          Share of bugs with a function the real fix changed in Allfather's top 10. The first two tiles are the frozen full pipeline, allfather-fast;
          the others are the website, and the live monitor runs it without the GPU reranker. The sets differ in projects and difficulty, so the
          tiles describe each setting rather than compare them. Full methodology, intervals and every stage on <a href={href("benchmarks")}>Benchmarks</a>.
        </p>
      </section>

      <section class="block">
        <p class="kicker">Architecture</p>
        <h2>What runs where.</h2>
        <p class="section-lede">
          Most ranking happens in the visitor's browser; a GPU server re-reads the top 50. One Cloudflare Worker serves the
          site and relays GitHub and the GPU; the GPU reranker on Modal scales to zero when idle. The research pipeline trains every model the site ships.
        </p>
        <figure class="architecture">
          <img src="/system.svg" width="1200" height="800" loading="lazy" decoding="async"
            alt="The browser downloads a repository through a Cloudflare Worker relay, parses and ranks it in Web Workers, and sends the top 50 functions to a GPU reranker on Modal through the same Worker. A Python research pipeline on a laptop and the PACE cluster trains the models the site ships." />
        </figure>
      </section>

      <section class="block">
        <p class="kicker">Decisions</p>
        <h2>What mattered most.</h2>
        <ol class="case-list">
          {decisions(lite).map(([title, text]) => (
            <li key={title}>
              <h3>{title}</h3>
              <p>{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section class="block">
        <p class="kicker">Negative results</p>
        <h2>What didn't work.</h2>
        <ul class="case-list">
          {FAILED.map(([title, text]) => <li key={title}><h3>{title}</h3><p>{text}</p></li>)}
        </ul>
        <p class="note">Every experiment, kept or not, is on <a href={href("how")}>How it works</a>.</p>
      </section>

      <section class="block">
        <p class="kicker">Rigor</p>
        <h2>Why the numbers can be trusted.</h2>
        <ul class="case-list plain">
          {SAFEGUARDS.map((s) => <li key={s}>{s}</li>)}
        </ul>
      </section>

      <section class="block">
        <p class="kicker">Go deeper</p>
        <div class="case-links">
          <a class="btn primary" href={href("search")}>Try it on a repository</a>
          <a class="btn" href={href("explore")}>Watch it on real bugs</a>
        </div>
      </section>
    </div>
  );
}
