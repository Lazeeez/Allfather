import { PageHero } from "../components/PageHero.tsx";
import { href } from "../lib/router.ts";

const GPU = !!import.meta.env.VITE_RERANK_SERVER;

export function Privacy() {
  return (
    <div class="container narrow">
      <PageHero kicker="Privacy" title="What I keep, and what I never see">
        <p>No accounts, no cookies, no advertising. The search runs in your browser; this page lists what leaves it, where it goes and what I keep.</p>
      </PageHero>
      <section class="block">
        <h2>Your bug report</h2>
        <p>
          Parsing, indexing and ranking run in your browser. The report is kept in the page's own address after a # sign, so you can share the
          search, but browsers never send that part of an address to a server.{" "}
          {GPU
            ? "It leaves your browser only through the GPU reranker, which is on by default and used for Python repositories (you can switch it off next to the results). Then the report and the text of the top 50 functions go to my server, which passes them to a GPU to be scored. This happens each time you pause typing, so a report you are still writing is sent too. I keep only the scores, for a day, under a hash of the request, so an identical search is answered at once. My code on the GPU server does not log or store the text."
            : "It never leaves your browser."}
        </p>
      </section>
      <section class="block">
        <h2>What I count</h2>
        <ul class="plain-list">
          <li><b>Searches</b>, as a count per day and repository, with where the query came from (typed, an example, a GitHub issue or a link). Not the query itself. I count nothing if your browser sends Do Not Track or Global Privacy Control.</li>
          <li><b>Your 👍/👎 votes</b>, when you give one: the day, the repository and commit, the function you rated, its rank, the stage that ranked it, the public GitHub issue's link if the query came from one, and a random number that groups the votes of one search. I use them to measure how often the right place is ranked first, and the home page shows the totals once there are enough of them.</li>
          <li><b>Page views</b>, through Cloudflare Web Analytics, which uses no cookies and does not identify visitors. It sees the page's path and the repository in its address, not the report.</li>
        </ul>
        <p>I use your IP address for a moment to limit how many requests one address can make, and I don't store it.</p>
      </section>
      <section class="block">
        <h2>Other services your browser talks to</h2>
        <ul class="plain-list">
          <li><b>My server</b>, which relays the public repository you load from GitHub. Cloudflare keeps a copy of that download for up to a day (five minutes for a repository's latest commit), so the next visitor loads it faster. Issue text, file lists and file history also come through it, cached for 10 minutes to an hour. Pages also read public totals and the live accuracy from it.</li>
          <li><b>GitHub, jsDelivr and raw.githubusercontent.com</b>, directly, when the relay is unavailable: the same public files, from their own servers.</li>
          <li><b>Hugging Face, jsDelivr and unpkg</b>, only if the browser's language-model rerank runs, to download the model and its runtime once.</li>
          <li><b>Cloudflare</b>, which hosts the site, asks browsers to report connections that fail (Network Error Logging). A report names the address that failed, which never includes the bug report.</li>
        </ul>
      </section>
      <section class="block">
        <h2>In your browser</h2>
        <p>
          Your browser keeps the repositories you load and the embeddings computed for them (up to 12 repositories, so the next visit skips the download), the site's files and its 16 MB embedding model, so they load faster, the language model if it was downloaded, your recent repositories, the light or dark theme, the GPU reranker switch, which example the home page showed last, and your Beat Allfather score. They stay on your device; clearing this site's data in your browser removes them.
        </p>
        <p><a href={href("search")}>Back to searching</a></p>
      </section>
    </div>
  );
}
