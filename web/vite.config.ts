import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import preact from "@preact/preset-vite";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";
import { contentSecurityPolicy } from "./csp.ts";
import { type LinkPage, PAGE_META, PAGE_PATHS, SITE } from "./src/lib/pages.ts";

/**
 * Preload the two faces the first screen needs (Inter for text, Fraunces for headings), so they are
 * fetched with the HTML instead of after the CSS: no flash of the fallback font on the headline.
 */
const preloadFonts = (): Plugin => ({
  name: "preload-fonts",
  apply: "build",
  transformIndexHtml: {
    order: "post",
    handler: (_html, ctx) =>
      Object.keys(ctx.bundle ?? {})
        .filter((f) => /\/(inter|fraunces)-latin-wght-normal-[\w-]+\.woff2$/.test(f))
        .map((f) => ({ tag: "link", attrs: { rel: "preload", as: "font", type: "font/woff2", crossorigin: "", href: `./${f}` }, injectTo: "head" as const })),
  },
});

/**
 * public/sw.js drops an older build of a file when it caches a newer one, matching them by the
 * name before the hash. Two different files with the same name and extension in one build would
 * evict each other, so the build refuses them.
 */
const uniqueAssetNames = (): Plugin => ({
  name: "unique-asset-names",
  apply: "build",
  generateBundle(_options, bundle) {
    const seen = new Map<string, string>();
    for (const file of Object.keys(bundle)) {
      const m = file.match(/^(.*)-[\w-]{8}(\.\w+)$/);
      if (!m) continue;
      const stem = m[1] + m[2];
      if (seen.has(stem)) this.error(`${file} and ${seen.get(stem)} share a name: rename one (see public/sw.js).`);
      seen.set(stem, file);
    }
  },
});

const securityHeaders = (): Plugin => ({
  name: "security-headers",
  apply: "build",
  closeBundle() {
    const html = readFileSync("dist/index.html", "utf8");
    const inline = [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) =>
      createHash("sha256").update(m[1]).digest("base64"),
    );
    const everywhere = [
      "/*",
      `  Content-Security-Policy: ${contentSecurityPolicy(inline)}`,
      "  Cross-Origin-Opener-Policy: same-origin",
      "  Cross-Origin-Embedder-Policy: credentialless",
      "  X-Content-Type-Options: nosniff",
      "  Referrer-Policy: strict-origin-when-cross-origin",
      "  Permissions-Policy: camera=(), microphone=(), geolocation=()",
      "  Strict-Transport-Security: max-age=31536000; includeSubDomains",
    ];
    const hashed = ["/assets/*", "  Cache-Control: public, max-age=31536000, immutable"];
    writeFileSync("dist/_headers", [...everywhere, "", ...hashed, ""].join("\n"));
  },
});

const attr = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

const pageFiles = (): Plugin => ({
  name: "page-files",
  apply: "build",
  closeBundle() {
    const index = readFileSync("dist/index.html", "utf8");
    const pages = Object.keys(PAGE_PATHS) as LinkPage[];
    for (const page of pages) {
      if (page === "home") continue;
      const { title, description } = PAGE_META[page];
      const url = `${SITE}/${PAGE_PATHS[page]}`;
      const html = index
        .replace(/<title>[^<]*<\/title>/, `<title>${attr(title)}</title>`)
        .replace(/(<meta name="description" content=")[^"]*/, `$1${attr(description)}`)
        .replace(/(<meta property="og:title" content=")[^"]*/, `$1${attr(title)}`)
        .replace(/(<meta property="og:description" content=")[^"]*/, `$1${attr(description)}`)
        .replace(/(<meta property="og:url" content=")[^"]*/, `$1${url}`)
        .replace(/(<link rel="canonical" href=")[^"]*/, `$1${url}`);
      writeFileSync(`dist/${PAGE_PATHS[page]}.html`, html);
    }
    const today = new Date().toISOString().slice(0, 10);
    const urls = pages.map((page) => `  <url><loc>${SITE}/${PAGE_PATHS[page]}</loc><lastmod>${today}</lastmod></url>`);
    writeFileSync("dist/sitemap.xml", `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join("\n")}
</urlset>
`);
  },
});

export default defineConfig({
  base: "/",
  plugins: [preact(), preloadFonts(), uniqueAssetNames(), securityHeaders(), pageFiles()],
  worker: { format: "es" },
  build: {
    target: "es2022",
    outDir: "dist",
    assetsInlineLimit: 0, // keep .wasm files as separately cached assets
  },
  test: { environment: "node", include: ["test/**/*.test.ts"] },
});
