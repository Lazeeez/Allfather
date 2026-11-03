# 0031: Pages get real addresses, so search engines can index them

## Status

Accepted, 2026-10-20.

## Context

The website's pages were hash routes (`allfather.dev/#/benchmarks`), chosen when it was hosted on GitHub Pages, which serves one static file and cannot route paths. Search engines ignore everything after `#`, so to Google the site was one page with one title and one description; the sitemap listed only `/`. The site now runs as a Cloudflare Worker with static assets, which can serve a single-page application at any path.

## Decision

- **Paths, not hashes.** Home `/`, `/search`, `/how-it-works`, `/benchmarks`, `/explore` (with `/explore/<issue>`), `/case-study`, and a new `/privacy`. Navigation uses the History API; a click on a same-site link is handled in the page, so moving between pages still never reloads it.
- **Old links keep working.** A `#/…` address is rewritten to its path before the first render, alongside the older `?repo=` and `#issue=` forms. Links already shared in GitHub issues by the Action, in bookmarks and in the README all land on the right page.
- **Each page has its own head, in the HTML itself.** The build writes one HTML file per page with its title, description, canonical URL and link-preview tags, so crawlers and link previews see them without running JavaScript; the page updates the same tags as you move between pages.
- **A sitemap of every page**, written by the build with the build date, and **structured data** (`WebSite` and `SoftwareApplication`, free, runs in a browser) in the page head.
- **Unknown addresses answer with a "not found" page** marked `noindex`, instead of quietly showing the home page.
- **Absolute asset paths** (`base: "/"`): relative ones broke under nested paths such as `/explore/<issue>`.
- **The Worker serves the application for any path** (`not_found_handling: "single-page-application"`), and the service worker falls back to the cached home page for an offline navigation it has not seen.

## Consequences

- Every page can rank on its own, with a description written for it.
- Deep links are clean and shareable: `allfather.dev/explore/django__django-11019`.
- A missing data file now answers with the application's HTML rather than a 404; the site already checks the content type before using a data file.
- I register the domain in Google Search Console and submit the sitemap myself, since it needs my Google account.
