export type Page = "home" | "search" | "benchmarks" | "explore" | "how" | "case" | "privacy" | "notfound";
export type LinkPage = Exclude<Page, "notfound">;

export const SITE = "https://allfather.dev";

export const PAGE_PATHS: Record<LinkPage, string> = {
  home: "",
  search: "search",
  benchmarks: "benchmarks",
  explore: "explore",
  how: "how-it-works",
  case: "case-study",
  privacy: "privacy",
};

export interface PageMeta {
  title: string;
  description: string;
}

export const PAGE_META: Record<Page, PageMeta> = {
  home: {
    title: "Allfather: find the code behind any bug report",
    description: "Paste a bug report, get the functions most likely to need the fix. Allfather searches public repositories in Python, JavaScript, TypeScript, Go, Java and Rust, right in your browser.",
  },
  search: {
    title: "Search a repository · Allfather",
    description: "Load any public GitHub repository in Python, JavaScript, TypeScript, Go, Java or Rust, paste a bug report or a stack trace, and see the functions most likely to need the fix, with the evidence for each.",
  },
  benchmarks: {
    title: "Benchmarks · Allfather",
    description: "How often Allfather finds the function a real fix changed: stage-by-stage results on SWE-bench Lite, held-out projects and five more languages, with confidence intervals and paired significance tests, and the correction of my fresh-2026 study now in progress.",
  },
  explore: {
    title: "Explore real bugs · Allfather",
    description: "Step through real GitHub bugs one at a time: the report, the functions the maintainers' fix changed, and where each stage of Allfather's pipeline ranked them. Or guess the fixed file against Allfather.",
  },
  how: {
    title: "How it works · Allfather",
    description: "How Allfather localizes bugs: code-aware BM25, LambdaMART rankers, static code embeddings and a fine-tuned GPU reranker, running in Web Workers in your browser, and what I tried and dropped.",
  },
  case: {
    title: "Case study · Allfather",
    description: "The case study behind Allfather, a bug localization search engine: the problem, the measured results, the decisions that mattered, the negative results and the safeguards behind the numbers.",
  },
  privacy: {
    title: "Privacy · Allfather",
    description: "What I store and what I never see: search counts and votes without your bug report, no accounts, no cookies, and the optional GPU reranker.",
  },
  notfound: {
    title: "Page not found · Allfather",
    description: "This page does not exist on Allfather.",
  },
};

export const pageUrl = (page: LinkPage) => `${SITE}/${PAGE_PATHS[page]}`;
