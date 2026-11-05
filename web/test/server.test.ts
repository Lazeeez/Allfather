import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { blend, forServer, SERVER, SERVER_LANGUAGES, SERVER_WEIGHTS, serverLanguage, servedLanguage, ServerUnavailable, serverScores, SKIP_LANGUAGE_MODEL } from "../src/engine/server.ts";
import cases from "./server-blend.json";

afterEach(() => vi.unstubAllGlobals());

describe("GPU reranker blend", () => {
  it("orders candidates exactly as scripts/website_rerank.py did when ADR 0021 was measured", () => {
    for (const c of cases as { n: number; depth: number; scores: number[][]; order: string[] }[]) {
      const ids = Array.from({ length: c.n }, (_, i) => `u${i}`);
      expect(blend(ids, c.scores, c.depth, 1)).toEqual(c.order);
    }
  });

  it("keeps the browser's order when there is nothing to blend", () => {
    expect(blend(["a", "b", "c"], [])).toEqual(["a", "b", "c"]);
    expect(blend(["a"], [[3]])).toEqual(["a"]);
  });
});

describe("GPU reranker call", () => {
  const answer = (status: number, body: unknown = {}) =>
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status })));

  it("sends at most 50 texts, each cut to 8000 characters, and returns the scores", async () => {
    answer(200, { scores: [[1, 2], [3, 4]] });
    const texts = Array.from({ length: 60 }, () => "x".repeat(9000));
    expect(await serverScores("/rerank", "q".repeat(9000), texts)).toEqual([[1, 2], [3, 4]]);
    const sent = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string);
    expect(sent.texts).toHaveLength(50);
    expect(sent.texts[0]).toHaveLength(8000);
    expect(sent.query).toHaveLength(8000);
  });

  it("treats a site without a server as permanent, and other failures as passing", async () => {
    answer(501);
    await expect(serverScores("/rerank", "q", ["a", "b"])).rejects.toMatchObject({ permanent: true });
    answer(429);
    await expect(serverScores("/rerank", "q", ["a", "b"])).rejects.toMatchObject({ permanent: false });
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
    await expect(serverScores("/rerank", "q", ["a", "b"])).rejects.toBeInstanceOf(ServerUnavailable);
  });
});

describe("which searches go to the GPU reranker", () => {
  it("sends a list whose top functions are mostly in one of the six languages, and names it", () => {
    expect(forServer(["a.py", "b.py", "c.ts"])).toBe("python");
    expect(forServer(["a.go", "b.go", "c.py"])).toBe("go");
    expect(forServer(["a.ts", "b.tsx", "c.py"])).toBe("typescript");
  });

  it("keeps mixed lists in the browser, since no language has a majority", () => {
    expect(forServer(["src/a.ts", "src/b.go", "lib/c.py"])).toBeNull();
    expect(forServer(["a.py", "b.java"])).toBeNull();
    expect(forServer([])).toBeNull();
  });

  it("decides on the 50 functions the server would re-read", () => {
    expect(forServer([...Array(50).fill("a.py"), ...Array(200).fill("b.rs")])).toBe("python");
  });
});

describe("the frozen setting for each language (ADR 0034)", () => {
  it("serves all six languages, weight 1 for Python and 2 for the rest", () => {
    expect([...SERVER_LANGUAGES].sort()).toEqual(["go", "java", "javascript", "python", "rust", "typescript"]);
    expect(SERVER_WEIGHTS).toEqual({ python: 1, go: 2, java: 2, javascript: 2, typescript: 2, rust: 2 });
  });

  it("skips the browser's language model only where a test showed it safe", () => {
    expect([...SKIP_LANGUAGE_MODEL]).toEqual(["python"]);
  });

  it("matches the configuration the study froze", () => {
    const config = JSON.parse(readFileSync(new URL("../../results/website-rerank/gpu_config.json", import.meta.url), "utf-8"));
    for (const [lang, setting] of Object.entries(config.languages) as [string, { depth: number; weight: number }][]) {
      expect(SERVER_WEIGHTS[lang]).toBe(setting.weight);
      expect(setting.depth).toBe(SERVER.depth);
    }
  });
});

describe("repositories the GPU is woken for", () => {
  it("counts every indexed function, not only the top of a list", () => {
    expect(servedLanguage(["a.py", "b.py", "c.go"])).toBe(true);
    expect(servedLanguage(["a.go", "b.rs", "c.py"])).toBe(false);
    expect(servedLanguage([])).toBe(false);
  });

  it("counts .tsx as TypeScript", () => {
    expect(serverLanguage(["a.ts", "b.tsx", "c.py"])).toBe("typescript");
  });
});
