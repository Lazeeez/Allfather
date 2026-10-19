import { useEffect, useRef, useState } from "preact/hooks";
import { Footer, Nav } from "./components/Nav.tsx";
import { type Lite, type Summary, getJSON } from "./lib/data.ts";
import { useLazy } from "./lib/lazy.ts";
import { scrollHints } from "./lib/scrollHints.ts";
import { spotlight } from "./lib/spotlight.ts";
import { PAGE_META, SITE } from "./lib/pages.ts";
import { interceptLinks, useRoute } from "./lib/router.ts";
import { Benchmarks } from "./pages/Benchmarks.tsx";
import { CaseStudy } from "./pages/CaseStudy.tsx";
import { Explore } from "./pages/Explore.tsx";
import { Home } from "./pages/Home.tsx";
import { HowItWorks } from "./pages/HowItWorks.tsx";
import { NotFound } from "./pages/NotFound.tsx";
import { Privacy } from "./pages/Privacy.tsx";
import { Search } from "./pages/Search.tsx";

function setHead(name: string, attr: "name" | "property", content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${name}"]`);
  if (!el) {
    el = Object.assign(document.createElement("meta"), { content });
    el.setAttribute(attr, name);
    document.head.append(el);
  }
  el.content = content;
}

function describePage(page: keyof typeof PAGE_META, path: string) {
  const meta = PAGE_META[page];
  const url = `${SITE}${path === "/" ? "/" : path.replace(/\/+$/, "")}`;
  document.title = meta.title;
  setHead("description", "name", meta.description);
  setHead("og:title", "property", meta.title);
  setHead("og:description", "property", meta.description);
  setHead("og:url", "property", url);
  setHead("robots", "name", page === "notfound" ? "noindex" : "index, follow");
  document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.setAttribute("href", url);
}

export function App() {
  const route = useRoute();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [lite, setLite] = useState<Lite | null>(null);
  const [failed, setFailed] = useState(false);
  // The search app is created on first visit and then kept (hidden) so a loaded repository
  // survives browsing the other pages.
  const [searchOpened, setSearchOpened] = useState(route.page === "search");
  const first = useRef(true);
  // The command palette loads on first use: Ctrl+K (or Cmd+K), or the nav's button.
  const [palette, setPalette] = useState(false);
  const paletteModule = useLazy(() => import("./components/CommandPalette.tsx"), palette);
  const Palette = paletteModule?.default;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((v) => !v);
      }
    };
    const open = () => setPalette(true);
    addEventListener("keydown", onKey);
    addEventListener("allfather:palette", open);
    return () => {
      removeEventListener("keydown", onKey);
      removeEventListener("allfather:palette", open);
    };
  }, []);

  useEffect(() => scrollHints(), []);
  useEffect(() => interceptLinks(), []);
  useEffect(() => spotlight(), []);

  useEffect(() => {
    getJSON<Summary>("data/summary.json").then(setSummary, () => setFailed(true));
    getJSON<Lite>("data/lite.json").then(setLite, () => {});
  }, []);

  useEffect(() => describePage(route.page, location.pathname), [route.page, route.param]);

  useEffect(() => {
    if (route.page === "search") setSearchOpened(true);
    if (!first.current) window.scrollTo({ top: 0, behavior: "instant" });
    first.current = false;
  }, [route.page]);

  const page = route.page;
  return (
    <>
      <a class="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>Skip to content</a>
      <Nav page={page} />
      <main id="main" tabIndex={-1} class={`page-${page}`}>
        {page === "home" && <Home summary={summary} lite={lite} />}
        {searchOpened && (
          <div hidden={page !== "search"}>
            <Search active={page === "search"} request={route.query} />
          </div>
        )}
        {page === "benchmarks" && <Benchmarks summary={summary} lite={lite} failed={failed} />}
        {page === "explore" && <Explore summary={summary} linked={route.param} failed={failed} mode={route.query.get("mode")} set={route.query.get("set")} />}
        {page === "how" && <HowItWorks summary={summary} />}
        {page === "case" && <CaseStudy summary={summary} lite={lite} />}
        {page === "privacy" && <Privacy />}
        {page === "notfound" && <NotFound />}
      </main>
      <Footer />
      {palette && Palette && <Palette onClose={() => setPalette(false)} />}
    </>
  );
}
