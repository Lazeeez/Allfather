import { describe, expect, it } from "vitest";
import { href, legacyTarget, parsePath, searchHref } from "../src/lib/router.ts";

describe("page addresses", () => {
  it("reads a page, its parameter and its query from a path", () => {
    expect(parsePath("/", "").page).toBe("home");
    expect(parsePath("/benchmarks").page).toBe("benchmarks");
    const deep = parsePath("/explore/django__django-11019", "?set=languages");
    expect([deep.page, deep.param, deep.query.get("set")]).toEqual(["explore", "django__django-11019", "languages"]);
    expect(parsePath("/no-such-page").page).toBe("notfound");
  });

  it("writes paths that read back as the same page", () => {
    expect(href("home")).toBe("/");
    expect(href("search", null, { repo: "pallets/flask", q: undefined })).toBe("/search?repo=pallets%2Fflask");
    expect(href("explore", "a/b")).toBe("/explore/a%2Fb");
    expect(parsePath("/explore/a%2Fb").param).toBe("a/b");
  });

  it("sends every old link to its page", () => {
    expect(legacyTarget("/", "", "#/benchmarks")).toBe("/benchmarks");
    expect(legacyTarget("/", "", "#/search?repo=a/b&q=x")).toBe("/search?repo=a%2Fb#q=x");
    expect(legacyTarget("/", "", "#/")).toBe("/");
    expect(legacyTarget("/", "?repo=a/b&q=x", "")).toBe("/search?repo=a%2Fb#q=x");
    expect(legacyTarget("/search", "?repo=a/b&q=x+y", "")).toBe("/search?repo=a%2Fb#q=x+y");
    expect(legacyTarget("/search", "?repo=a/b", "")).toBeNull();
    expect(legacyTarget("/", "", "#issue=django__django-1")).toBe("/explore/django__django-1");
    expect(legacyTarget("/", "", "#results")).toBe("/benchmarks");
    expect(legacyTarget("/benchmarks", "", "")).toBeNull();
  });
});

describe("search links", () => {
  it("keep the bug report out of the query string", () => {
    expect(searchHref({ repo: "a/b" }, "crash in x()")).toBe("/search?repo=a%2Fb#q=crash+in+x%28%29");
    expect(searchHref({ repo: "a/b" })).toBe("/search?repo=a%2Fb");
  });
});
