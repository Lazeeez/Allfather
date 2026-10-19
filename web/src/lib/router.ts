import { useEffect, useMemo, useState } from "preact/hooks";
import { type LinkPage, PAGE_PATHS, type Page } from "./pages.ts";

export type { LinkPage, Page } from "./pages.ts";

export interface Route {
  page: Page;
  param: string | null;
  query: URLSearchParams;
}

const PAGES = Object.fromEntries(Object.entries(PAGE_PATHS).map(([page, path]) => [path, page])) as Record<string, Page>;
const NAVIGATE = "allfather:navigate";

export function parsePath(pathname: string, search = ""): Route {
  const [first = "", ...rest] = pathname.replace(/^\/+|\/+$/g, "").split("/");
  const page: Page = PAGES[first] ?? "notfound";
  return { page, param: rest.length && page !== "notfound" ? decodeURIComponent(rest.join("/")) : null, query: new URLSearchParams(search) };
}

export function href(page: LinkPage, param?: string | null, query?: Record<string, string | undefined>): string {
  let h = `/${PAGE_PATHS[page]}`;
  if (param) h += `${h.endsWith("/") ? "" : "/"}${encodeURIComponent(param)}`;
  const qs = new URLSearchParams(Object.entries(query ?? {}).filter((e): e is [string, string] => !!e[1])).toString();
  return qs ? `${h}?${qs}` : h;
}

const here = () => `${location.pathname}${location.search}`;

export function navigate(url: string): void {
  if (url === here()) return;
  history.pushState(null, "", url);
  dispatchEvent(new Event(NAVIGATE));
}

export function replaceUrl(url: string): void {
  if (url !== here()) history.replaceState(null, "", url);
}

export function useRoute(): Route {
  const [url, setUrl] = useState(here);
  useEffect(() => {
    const onChange = () => {
      upgradeLegacyUrl();
      setUrl(here());
    };
    addEventListener("popstate", onChange);
    addEventListener("hashchange", onChange);
    addEventListener(NAVIGATE, onChange);
    return () => {
      removeEventListener("popstate", onChange);
      removeEventListener("hashchange", onChange);
      removeEventListener(NAVIGATE, onChange);
    };
  }, []);
  return useMemo(() => {
    const at = url.indexOf("?");
    return parsePath(at < 0 ? url : url.slice(0, at), at < 0 ? "" : url.slice(at));
  }, [url]);
}

export function interceptLinks(): () => void {
  const onClick = (e: MouseEvent) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = (e.target as Element | null)?.closest?.("a");
    if (!a || a.target || a.hasAttribute("download") || a.getAttribute("rel")?.includes("external")) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || /^\/(relay|api|gh|rerank|data|assets|icons)\//.test(url.pathname) || /\.\w+$/.test(url.pathname)) return;
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
    e.preventDefault();
    navigate(`${url.pathname}${url.search}`);
  };
  document.addEventListener("click", onClick);
  return () => document.removeEventListener("click", onClick);
}

export function legacyTarget(pathname: string, search: string, hash: string): string | null {
  if (hash.startsWith("#/")) {
    const rest = hash.slice(1);
    return rest === "/" ? "/" : rest;
  }
  if (pathname !== "/") return null;
  const query = new URLSearchParams(search);
  if (query.get("repo")) return href("search", null, { repo: query.get("repo")!, q: query.get("q") ?? undefined });
  if (hash.startsWith("#issue=")) return href("explore", decodeURIComponent(hash.slice(7)));
  const anchors: Record<string, LinkPage> = { "#try": "search", "#explorer": "explore", "#results": "benchmarks", "#pipeline": "how", "#engineering": "how", "#top": "home" };
  return anchors[hash] ? href(anchors[hash]) : null;
}

export function upgradeLegacyUrl(): void {
  const next = legacyTarget(location.pathname, location.search, location.hash);
  if (next) history.replaceState(null, "", next);
}
