import { test as base, expect } from "@playwright/test";
import { GO_REPO, REPO, serveFixture } from "./fixture.ts";

// Every test gets the fixture repository, and fails on any uncaught page error.
const test = base.extend<{ guard: void }>({
  guard: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await serveFixture(page);
      await use();
      expect(errors).toEqual([]);
    },
    { auto: true },
  ],
});

test("home shows the product and the measured numbers", async ({ page }) => {
  await page.goto("./");
  await expect(page).toHaveTitle(/^Allfather/);
  await expect(page.locator(".hero h1")).toContainText("Find the code");
  await expect(page.locator(".tile-value").first()).toHaveText(/%$/);
});

test("pages route and set their titles", async ({ page }) => {
  await page.goto("./");
  for (const [link, title, marker] of [
    ["Benchmarks", /^Benchmarks/, ".bar-row"],
    ["How it works", /^How it works/, ".pipeline .stage"],
    ["Explore", /^Explore/, "#explorer .bug-title"],
    ["Search", /^Search/, "#repo-input"],
    ["Case study", /^Case study/, ".case-list li"],
  ] as const) {
    await page.locator("#site-menu a", { hasText: link }).click();
    await expect(page).toHaveTitle(title);
    await expect(page.locator(marker).first()).toBeVisible();
  }
});

test("the theme toggles between light and dark only, and persists", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  const theme = () => page.evaluate(() => document.documentElement.dataset.theme);
  const first = await theme();
  const toggle = page.locator("button[aria-label^='Switch to']");
  await toggle.click();
  await expect.poll(theme).not.toBe(first);
  const second = await theme();
  expect(new Set([first, second])).toEqual(new Set(["light", "dark"]));
  await page.reload();
  expect(await theme()).toBe(second);
  await toggle.click();
  await expect.poll(theme).toBe(first);
});

test("search: load a repository, describe a bug, get the right function", async ({ page }) => {
  await page.goto("./");
  await page.locator(".quickstart input").fill(REPO);
  await page.locator(".quickstart button").click();
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await expect(page.locator(".repo-summary")).toContainText("5 functions and classes in 2 files"); // tests left out
  // The language-model stage needs a download these tests do not make: switch it off.
  await page.locator(".toolbar .switch", { hasText: "Language-model" }).click();
  await page.locator("#demo-query").fill("load_config crashes with KeyError when the settings file is missing");
  await expect(page.locator("#search-app ol.hits .qual").first()).toHaveText("load_config");
  await expect(page.locator("#search-app .why .reason").first()).toBeVisible();
  await expect(page.locator(".confidence")).toContainText(/(High|Medium|Low) confidence · \d+% chance/);
  await page.locator("#demo-query").fill("load_config fails");
  await expect(page.locator(".confidence")).toContainText("Too short to estimate");
  await expect(page).toHaveURL(/\/search\?repo=allfather-e2e%2Ffixture#q=load_config\+fails$/);

  // A traceback points at the function where it ended.
  await page.locator("#demo-query").fill('Traceback (most recent call last):\n  File "/srv/pkg/http.py", line 3, in fetch\nConnectionError');
  await expect(page.locator("#search-app ol.hits .qual").first()).toHaveText("Client.fetch");
  await expect(page.locator("#search-app .why .reason").first()).toContainText("traceback");

  // Keyboard: j moves to the next result.
  await page.locator("#search-app .hit-head").first().focus();
  await page.keyboard.press("j");
  await expect(page.locator("#search-app ol.hits > li").nth(1).locator(".hit-head")).toBeFocused();

  // File view groups by file.
  await page.locator("[aria-label='Result granularity'] button", { hasText: "Files" }).click();
  await expect(page.locator("#search-app ol.hits .qual").first()).toHaveText("pkg/http.py");
});

test("search state survives a visit to another page", async ({ page }) => {
  await page.goto(`./#/search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator("#site-menu a", { hasText: "Benchmarks" }).click();
  await page.locator("#site-menu a", { hasText: "Search" }).click();
  await expect(page.locator(".repo-pill")).toContainText(REPO);
});

test("bad input and unknown repositories are explained", async ({ page }) => {
  await page.route("https://api.github.com/repos/allfather-e2e/missing/**", (route) => route.fulfill({ status: 404, json: {} }));
  await page.goto("./#/search");
  await page.locator("#repo-input").fill("not a repo");
  await page.locator(".repo-card button[type=submit]").click();
  await expect(page.locator(".progress-text.error")).toContainText("owner/name");
  await page.locator("#repo-input").fill("allfather-e2e/missing");
  await page.locator(".repo-card button[type=submit]").click();
  await expect(page.locator(".progress-text.error")).toContainText("Couldn't find");
});

test("explorer deep links and old-style links", async ({ page }) => {
  await page.goto("./#/explore/sympy__sympy-20590");
  await expect(page.locator("#explorer .bug-id")).toHaveText("sympy__sympy-20590");
  // a newcomer's path: a verdict in words, a stage's list on request, another bug from the list
  await expect(page.locator(".verdict")).not.toBeEmpty();
  await page.locator(".climb-head").first().click();
  await expect(page.locator(".climb-list li").first()).toBeVisible();
  await page.locator(".picker button", { hasText: "Browse all" }).click();
  await page.locator(".bug-filters select").selectOption("django/django");
  await page.locator(".bug-card").first().click();
  await expect(page.locator("#explorer .bug-id")).toContainText("django__django-");
  await expect(page).toHaveURL(/\/explore\/django__django-/);
  await page.goto("./#issue=django__django-11019");
  await expect(page).toHaveURL(/\/explore\/django__django-11019$/);
  await expect(page.locator("#explorer .bug-id")).toHaveText("django__django-11019");
  await page.goto(`./?repo=${encodeURIComponent(REPO)}&q=config`);
  await expect(page).toHaveURL(/\/search\?repo=allfather-e2e%2Ffixture#q=config$/);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await expect(page.locator("#demo-query")).toHaveValue("config");
  await page.goto(`./search?repo=${encodeURIComponent(REPO)}&q=old+link`);
  await expect(page).toHaveURL(/\/search\?repo=allfather-e2e%2Ffixture#q=old\+link$/);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await expect(page.locator("#demo-query")).toHaveValue("old link");
});

test("an issue link pasted into the bug report box imports that issue", async ({ page }) => {
  await page.route("https://api.github.com/repos/allfather-e2e/fixture/issues/7", (route) =>
    route.fulfill({ json: { number: 7, title: "load_config crashes with KeyError", body: "when the settings file is missing", html_url: "https://github.com/allfather-e2e/fixture/issues/7" } }));
  await page.goto(`./#/search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator("#demo-query").fill("https://github.com/allfather-e2e/fixture/issues/7");
  await expect(page.locator("#demo-query")).toHaveValue(/^load_config crashes with KeyError\s+when the settings file is missing/);
});

test("the tools: why-bars, recent change, map, bookmarklet, issue links, palette, Beat Allfather", async ({ page }) => {
  await page.route("https://api.github.com/repos/allfather-e2e/fixture/issues/7", (route) =>
    route.fulfill({ json: { number: 7, title: "load_config crashes with KeyError", body: "when the settings file is missing", html_url: "https://github.com/allfather-e2e/fixture/issues/7" } }));
  await page.route("https://api.github.com/repos/allfather-e2e/fixture/commits**", (route) =>
    route.fulfill({ json: [{ sha: "abc", html_url: "https://github.com/allfather-e2e/fixture/commit/abc", commit: { message: "Read settings lazily", author: { name: "Ada", date: new Date().toISOString() } } }] }));

  // A GitHub issue link (what the bookmarklet opens) fills the query from the issue.
  await page.goto(`./#/search?repo=${encodeURIComponent(REPO)}&issue=7`);
  await expect(page.locator("#demo-query")).toHaveValue(/load_config crashes with KeyError/);
  await page.locator(".toolbar .switch", { hasText: "Language-model" }).click();
  await expect(page.locator("#search-app ol.hits .qual").first()).toHaveText("load_config");

  // The first result is open: why it ranks there, and when its file last changed.
  await expect(page.locator(".whybox li").first()).toBeVisible();
  await expect(page.locator(".recent-change")).toContainText("recently changed");

  // The map draws the repository, with the results on it.
  await page.locator("button", { hasText: "Show the map" }).click();
  await expect(page.locator(".repo-map canvas")).toBeVisible();

  // The bookmarklet, run as a saved bookmark runs it, on a GitHub issue page opens this site
  // with that repository and issue.
  await page.goto("./");
  const bookmark = (await page.locator("a.bookmarklet-btn").getAttribute("href"))!;
  expect(bookmark).toMatch(/^javascript:[^#]+$/); // no raw "#": a bookmark would end there
  await page.context().route("https://github.com/**", (route) => route.fulfill({ body: "<p>issue</p>", contentType: "text/html" }));
  const github = await page.context().newPage();
  await github.goto("https://github.com/allfather-e2e/fixture/issues/7");
  await github.evaluate((h) => { const a = document.createElement("a"); a.href = h; a.id = "bm"; a.textContent = "Allfather this"; document.body.append(a); }, bookmark);
  const [opened] = await Promise.all([page.context().waitForEvent("page"), github.click("#bm")]);
  expect(opened.url()).toMatch(/\/search\?repo=allfather-e2e\/fixture&issue=7$/);
  await github.close();
  await opened.close();

  // Ctrl+K opens the palette; typing narrows it; Enter runs the command.
  await page.keyboard.press("Control+k");
  await page.locator(".palette input").fill("bench");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/benchmarks$/);

  // Beat Allfather: six files, one guess, then the reveal and the score.
  await page.goto("./#/explore?mode=game");
  await expect(page.locator(".choice")).toHaveCount(6);
  await page.locator(".choice").first().click();
  await expect(page.locator(".reveal-box .verdict")).not.toBeEmpty();
  await expect(page.locator(".game-score")).toContainText("after 1 round");
});

test("sections that render after their data arrives are visible at once", async ({ page }) => {
  await page.goto("./#/benchmarks");
  const table = page.locator("table.heat");
  await table.scrollIntoViewIfNeeded();
  await expect(page.locator("section", { has: table })).toBeVisible();
  await expect(page.locator(".tiles .tile-value").first()).toHaveText(/%$/);
});

test("asking for another repository mid-load cancels the first and loads the new one", async ({ page }) => {
  await page.route(/allfather-e2e\/missing/, (route) => route.fulfill({ status: 404, contentType: "application/json", body: "{}" }));
  // Slow the first repository's files down so the second request lands while it is loading.
  await page.route("https://raw.githubusercontent.com/allfather-e2e/fixture/**", async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.fallback();
  });
  await page.goto(`./#/search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".progress-text")).toBeVisible();
  await page.evaluate(() => { location.hash = "#/search?repo=allfather-e2e/missing"; });
  await expect(page.locator(".progress-text.error")).toContainText("Couldn't find");
});

test("pressing Enter on another repository mid-load switches to it", async ({ page }) => {
  await page.route(/allfather-e2e\/missing/, (route) => route.fulfill({ status: 404, contentType: "application/json", body: "{}" }));
  await page.route("https://raw.githubusercontent.com/allfather-e2e/fixture/**", async (route) => {
    await new Promise((r) => setTimeout(r, 4000));
    await route.fallback();
  });
  await page.goto(`./#/search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".progress-text")).toBeVisible();
  await page.fill("#repo-input", "allfather-e2e/missing");
  await expect(page.getByRole("button", { name: "Load", exact: true })).toBeEnabled();
  await page.press("#repo-input", "Enter");
  await expect(page.locator(".progress-text.error")).toContainText("Couldn't find", { timeout: 15_000 });
  await expect(page.locator(".repo-summary")).toHaveCount(0);
});

test("a repository asked for while another is failing slowly still loads", async ({ page }) => {
  await page.route("https://api.github.com/repos/allfather-e2e/limited/**", (route) =>
    route.fulfill({ status: 403, headers: { "x-ratelimit-remaining": "0", "x-ratelimit-reset": String(Math.floor(Date.now() / 1000) + 600) }, json: {} }));
  await page.route(/jsdelivr\.(com|net)\/.*allfather-e2e\/limited/, async (route) => {
    await new Promise((r) => setTimeout(r, 1200));
    await route.fulfill({ status: 404, json: {} });
  });
  await page.goto("./#/search?repo=allfather-e2e/limited");
  await expect(page.locator(".progress-text")).toBeVisible();
  await page.fill("#repo-input", REPO);
  await page.press("#repo-input", "Enter");
  await expect(page.locator(".repo-summary")).toContainText(REPO);
});

test("the landing page shows a real example bug, with the fix marked", async ({ page }) => {
  await page.goto("./");
  await expect(page.locator(".preview-issue p")).not.toBeEmpty();
  await expect(page.locator(".preview-results li")).toHaveCount(4);
  await expect(page.locator(".preview-results li").first().locator(".reason")).toHaveText("changed by the real fix");
});

test("the GPU reranker is off until the visitor turns it on from the hint, and the choice is remembered", async ({ page }) => {
  const calls: string[] = [];
  await page.route("https://rerank.allfather-e2e.test/rerank/warm", (route) => {
    calls.push("warm");
    return route.fulfill({ status: 202, json: { warming: true } });
  });
  await page.route("https://rerank.allfather-e2e.test/rerank", (route) => {
    calls.push("rerank");
    return route.fulfill({ json: { scores: [[0, 0]] } });
  });
  await page.goto(`./search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator("#demo-query").fill("load_config crashes with KeyError when the settings file is missing");
  const hint = page.locator(".gpu-hint");
  await expect(hint).toBeVisible();
  await expect(page.locator(".fineprint")).toContainText("Your bug report never leaves this tab.");
  expect(calls).toEqual([]);
  await hint.getByRole("button", { name: "Turn on the GPU reranker" }).click();
  await expect.poll(() => calls.includes("rerank")).toBe(true);
  await expect(hint).toBeHidden();
  await page.reload();
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator("#demo-query").fill("load_config crashes with KeyError when the settings file is missing");
  await expect(page.locator("label.switch", { hasText: "GPU reranker" }).locator("input")).toBeChecked();
  await expect(page.locator(".gpu-hint")).toHaveCount(0);
});

test("dismissing the GPU hint keeps it away", async ({ page }) => {
  await page.route("https://rerank.allfather-e2e.test/rerank/warm", (route) => route.fulfill({ status: 202, json: { warming: true } }));
  await page.goto(`./search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator("#demo-query").fill("load_config crashes with KeyError when the settings file is missing");
  await page.locator(".gpu-hint").getByRole("button", { name: "Not now" }).click();
  await expect(page.locator(".gpu-hint")).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator("#demo-query").fill("load_config crashes with KeyError when the settings file is missing");
  await expect(page.locator("#search-app ol.hits > li").first()).toBeVisible();
  await expect(page.locator(".gpu-hint")).toHaveCount(0);
});

test("the GPU reranker reorders the top results without downloading the browser's language model", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("gpuRerank", "true"));
  const languageModel: string[] = [];
  page.on("request", (r) => { if (/onnx|ort-wasm|transformers@/.test(r.url())) languageModel.push(r.url()); });
  await page.route("https://rerank.allfather-e2e.test/rerank/warm", (route) => route.fulfill({ status: 202, json: { warming: true } }));
  let boosted = "";
  await page.route("https://rerank.allfather-e2e.test/rerank", async (route) => {
    const { texts } = route.request().postDataJSON() as { texts: string[] };
    boosted = texts[1].split("\n")[0];
    const scores = texts.map((_, i) => (i === 1 ? 10 : 0));
    await route.fulfill({ json: { scores: [scores, scores] } });
  });
  await page.goto(`./#/search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator("#demo-query").fill("load_config crashes with KeyError when the settings file is missing");
  await expect(page.locator("p.status-line", { hasText: "Re-read the top 50" })).toBeVisible();
  await expect(page.locator("#search-app ol.hits .qual").first()).toHaveText(boosted);
  await expect(page.locator("#search-app ol.hits > li").first().locator(".moved")).toHaveText("↑ from #2");
  expect(languageModel).toEqual([]);
});

test("the GPU is woken for a repository in another language and re-reads its results", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("gpuRerank", "true"));
  const calls: string[] = [];
  await page.route("https://rerank.allfather-e2e.test/rerank/warm", (route) => {
    calls.push("warm");
    return route.fulfill({ status: 202, json: { warming: true } });
  });
  await page.route("https://rerank.allfather-e2e.test/rerank", (route) => {
    calls.push("rerank");
    return route.fulfill({ json: { scores: [[0, 0], [0, 0]] } });
  });
  await page.goto(`./search?repo=${encodeURIComponent(GO_REPO)}`);
  await expect(page.locator(".repo-pill")).toContainText(GO_REPO);
  await expect.poll(() => calls.includes("warm")).toBe(true);
  await page.locator("#demo-query").fill("LoadConfig fails when the settings file is missing");
  await expect.poll(() => calls.includes("rerank")).toBe(true);
  await expect(page.locator("#search-app ol.hits .qual").first()).toHaveText("LoadConfig");
});

test("Explore shows bugs in other languages, ranked by the website's own stages", async ({ page }) => {
  const issue = {
    id: "gin-gonic__gin-1234", repo: "gin-gonic/gin", language: "go", set: "multilingual",
    text: "ShouldBindJSON accepts unknown fields\n\nBinding should reject a body with fields the struct does not have.",
    gold_files: ["binding/json.go"], gold_functions: ["binding/json.go::jsonBinding.Bind"],
    functions: {
      keyword: ["context.go::Context.ShouldBindJSON", "binding/json.go::jsonBinding.Bind"],
      instant: ["binding/json.go::jsonBinding.Bind"], semantic: ["binding/json.go::jsonBinding.Bind"], rerank: ["binding/json.go::jsonBinding.Bind"],
    },
    files: { files: ["binding/json.go"] },
  };
  await page.route("**/data/issues-multi/index.json", (route) => route.fulfill({
    json: [{ id: issue.id, repo: issue.repo, language: "go", title: "ShouldBindJSON accepts unknown fields", first: true, missed: false, rescued: false }],
  }));
  await page.route(`**/data/issues-multi/${issue.id}.json`, (route) => route.fulfill({ json: issue }));
  await page.goto("./#/explore");
  await page.getByRole("button", { name: "Five more languages" }).click();
  await expect(page).toHaveURL(/\/explore\?set=languages$/);
  await expect(page.locator("#explorer .bug-title")).toHaveText("ShouldBindJSON accepts unknown fields");
  await expect(page.locator("#explorer .bug-meta")).toContainText("Go");
  await expect(page.locator(".climb-name b").first()).toHaveText("Plain keyword search");
  await expect(page.locator(".verdict")).toContainText("website pipeline lifted it to #1");
  await page.locator(".picker button", { hasText: "Browse all" }).click();
  await expect(page.locator(".bug-filters select[aria-label='Language']")).toBeVisible();
});

test("Share card draws the top results as an image", async ({ page }) => {
  await page.goto(`./#/search?repo=${encodeURIComponent(REPO)}`);
  await expect(page.locator(".repo-pill")).toContainText(REPO);
  await page.locator(".toolbar .switch", { hasText: "Language-model" }).click();
  await page.locator("#demo-query").fill("load_config crashes with KeyError when the settings file is missing");
  await expect(page.locator("#search-app ol.hits .qual").first()).toHaveText("load_config");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Share card" }).click()]);
  expect(download.suggestedFilename()).toBe("allfather-allfather-e2e-fixture.png");
  const path = await download.path();
  const { statSync, copyFileSync } = await import("node:fs");
  expect(statSync(path).size).toBeGreaterThan(10_000);
  if (process.env.CARD_OUT) copyFileSync(path, process.env.CARD_OUT);
});

test("every page has its own address, title and canonical link, and old hash links still land", async ({ page }) => {
  for (const [path, title] of [["/benchmarks", /^Benchmarks/], ["/how-it-works", /^How it works/], ["/case-study", /^Case study/], ["/privacy", /^Privacy/]] as const) {
    await page.goto(path);
    await expect(page).toHaveTitle(title);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://allfather.dev${path}`);
  }
  await page.goto("./#/explore?mode=game");
  await expect(page).toHaveURL(/\/explore\?mode=game$/);
  await expect(page.locator(".choice").first()).toBeVisible();
});

test("moving between pages never reloads the page", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => { (window as unknown as { marker: number }).marker = 1; });
  await page.locator("#site-menu a", { hasText: "Benchmarks" }).click();
  await expect(page).toHaveURL(/\/benchmarks$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  expect(await page.evaluate(() => (window as unknown as { marker?: number }).marker)).toBe(1);
});

test("an unknown address shows a not-found page that asks not to be indexed", async ({ page }) => {
  await page.goto("/no-such-page");
  await expect(page.locator("h1")).toHaveText("This page doesn't exist");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex");
});
