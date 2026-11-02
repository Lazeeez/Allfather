import { useRef } from "preact/hooks";
import { Highlights, Lessons, Worked } from "../components/Engineering.tsx";
import { Icon, type IconName } from "../components/Icons.tsx";
import { PageHero } from "../components/PageHero.tsx";
import { Pipeline } from "../components/Pipeline.tsx";
import type { Summary } from "../lib/data.ts";
import { href } from "../lib/router.ts";

const GPU_RERANK = !!import.meta.env.VITE_RERANK_SERVER;

/** The browser's journey, each step in plain words first, then the detail for engineers. */
const JOURNEY: [IconName, string, string, string][] = [
  ["download", "Fetch", "Allfather downloads the project's code from GitHub: Python, JavaScript, TypeScript, Go, Java and Rust.",
    "The whole repository arrives as one archive through Allfather's relay, which passes GitHub's own download through; Cloudflare keeps a copy for up to a day so the next load is faster. If the relay is down, the file list comes from GitHub's API and the files sixteen at a time; jsDelivr stands in if GitHub's API is down."],
  ["code", "Read", "Every file is split into its functions, methods and classes.",
    "Tree-sitter, compiled to WebAssembly, parses on up to four threads with one grammar per language, unit for unit like the research pipeline's parser. Big repositories are searchable while they are still loading."],
  ["search", "Index", "A word index is built, so any word in the report can be looked up instantly.",
    "A code-aware BM25 index: snake_case and camelCase names are split into words and also kept whole, so both prose and exact names match."],
  ["rank", "Rank", "A model trained on thousands of real bugs weighs the clues as you type.",
    "LambdaMART, shipped as JSON trees, over 33 signals: keyword scores for the issue, its title and quoted code, whether a stack trace or the issue names the function, file-level evidence and the shape of the code."],
  ["vector", "Understand", "In the background, Allfather learns what every function means, to find code the report never names.",
    "A static code-embedding model (16.8 MB, downloaded once) embeds every function in the background; a second ranker adds how close each function is in meaning to the issue."],
  ["layers", "Reread", "The top 20 get a closer read, the way a developer would skim them.",
    `A small language model (MiniLM: 45 MB on a GPU through WebGPU, 23 MB on the CPU, downloaded once) embeds the issue and the top 20 functions; a third ranker reorders them with that evidence. A file ranker orders whole files for the Files view.${GPU_RERANK ? " With the GPU reranker on, this step runs only if the server does not answer: the reranker does as well without it." : ""}`],
  ...(GPU_RERANK ? [["chip", "Judge", "Allfather's own fine-tuned reranker reads the top 50 against the report, on a GPU server.",
    "The full pipeline's reranker (two LoRA adapters on Qwen3-Reranker-0.6B, too large and too slow for a browser) scores the top 50 on a GPU; its scores are blended with the browser's order, without waiting for the language model above. Cross-validated on 3,174 bugs from 119 projects it never trained on, it lifts function hit@10 from 79.3% to 81.9%. It was trained and measured on Python, so it is used only for Python repositories; you can switch it off, and the browser's ranking stays if the server does not answer."]] as typeof JOURNEY : []),
  ["clock", "Remember", "The next visit to the same repository skips the download and the parsing.",
    "Parsed repositories are cached by git tree hash in IndexedDB. Everything heavy runs in background threads, so the page stays responsive."],
];

export function HowItWorks({ summary }: { summary: Summary | null }) {
  const root = useRef<HTMLDivElement>(null);
  return (
    <div class="container" ref={root}>
      <PageHero kicker="How it works" title="From bug report to the right function">
        <p>
          A ranking cascade: cheap lexical scoring over every function, then learned and neural models over progressively smaller
          candidate pools. The full pipeline runs on a GPU; a lighter version, with its own rankers, runs in your browser.
        </p>
      </PageHero>

      <section class="block">
        <p class="kicker">In your browser</p>
        <h2>What happens when you press Search</h2>
        <p class="section-lede">When you <a href={href("search")}>search a repository</a>, everything below runs in Web Workers in your tab.{GPU_RERANK
          ? " Two steps use servers of ours: the relay that passes the repository download through, and, for Python repositories, the GPU reranker, which receives your bug report and the top 50 functions to score them."
          : " The only server of ours is the relay that passes the repository download through, and your bug report is never sent anywhere."}</p>
        <ol class="journey">
          {JOURNEY.map(([icon, title, plain, detail]) => (
            <li key={title}>
              <span class="journey-node"><Icon name={icon} /></span>
              <div>
                <h3>{title} <span class="journey-sub">{plain}</span></h3>
                <p class="tech">{detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section class="card frame block">
        <p class="kicker">The full pipeline</p>
        <h2>Five stages, each one smarter</h2>
        <p class="card-lede">Evaluated on the 291 SWE-bench Lite issues with a function-level gold label. Select a stage for its candidate pool, model, metrics and latency.</p>
        {summary ? <Pipeline summary={summary} /> : <p class="muted">Loading…</p>}
      </section>

      <section class="block">
        <p class="kicker">Engineering</p>
        <h2>What makes it fast</h2>
        <Highlights />
      </section>

      <section class="block">
        <p class="kicker">Things we tried</p>
        <h2>What worked</h2>
        <p class="section-lede">Each accuracy change was tested against what it replaced, on the same bugs, with a paired test; speed changes were timed. These made the cut.</p>
        <Worked summary={summary} />
      </section>

      <section class="block">
        <p class="kicker">Things we tried</p>
        <h2>What didn't work</h2>
        <p class="section-lede">Negative results, kept because they explain the design as much as the wins do.</p>
        <Lessons />
      </section>
    </div>
  );
}
