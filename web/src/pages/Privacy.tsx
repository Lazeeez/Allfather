import { PageHero } from "../components/PageHero.tsx";
import { href } from "../lib/router.ts";

const GPU = !!import.meta.env.VITE_RERANK_SERVER;

export function Privacy() {
  return (
    <div class="container narrow">
      <PageHero kicker="Privacy" title="What Allfather keeps, and what it never sees">
        <p>No accounts, no cookies, no advertising. The search runs in your browser; this page lists every piece of information that leaves it.</p>
      </PageHero>
      <section class="block">
        <h2>Your bug report</h2>
        <p>
          Parsing, indexing and ranking run in your browser. {GPU
            ? "Your bug report leaves it only when the GPU reranker is on (it is by default, and you can switch it off next to the results): the report and the text of the top 50 functions are sent to Allfather's server, which passes them to a GPU to be scored. Only the scores are kept, for a day, under a hash of the request, so an identical search is answered at once. Allfather's code on the GPU server does not log or store the text."
            : "Your bug report never leaves it."}
        </p>
      </section>
      <section class="block">
        <h2>What is counted</h2>
        <ul class="plain-list">
          <li><b>Searches</b>, as a count per day and repository, with where the query came from (typed, an example, a GitHub issue or a link). Not the query itself.</li>
          <li><b>Your 👍/👎 votes</b>, when you give one: the repository and commit, the function you rated, its rank, the stage that ranked it, the public GitHub issue's link if the query came from one, and a random number that groups the votes of one search. They measure how often the right place is ranked first, and are shown as totals on the home page.</li>
          <li><b>Page views</b>, through Cloudflare Web Analytics, which uses no cookies and does not identify visitors.</li>
        </ul>
        <p>Your IP address is used for a moment to limit how many requests one address can make, and is not stored.</p>
      </section>
      <section class="block">
        <h2>Other services your browser talks to</h2>
        <ul class="plain-list">
          <li><b>GitHub</b>, for the repository you load (through Allfather's relay, which passes GitHub's download through without keeping it), and for issues and file history.</li>
          <li><b>Hugging Face, jsDelivr and unpkg</b>, only if the browser's language-model rerank runs, to download the model and its runtime once.</li>
        </ul>
      </section>
      <section class="block">
        <h2>In your browser</h2>
        <p>
          Your browser keeps the repositories you load (so the next visit is instant), your recent repositories, the light or dark theme, the GPU reranker switch and your Beat Allfather score. They stay on your device; clearing this site's data in your browser removes them.
        </p>
        <p><a href={href("search")}>Back to searching</a></p>
      </section>
    </div>
  );
}
