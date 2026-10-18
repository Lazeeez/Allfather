# 0030: Odin is renamed Allfather

## Status

Accepted, 2026-10-18.

## Context

"Odin" names a programming language and many other projects, so the name is hard to search for and easy to confuse. The project's website has always lived at allfather.dev, "Allfather" is Odin's own title in the sagas, and no developer tool uses it.

## Decision

- **The product is Allfather**, "find the code behind any bug report". The website, the README, the GitHub Action and its comments use that name.
- **The code is renamed with it:** the Python package and its command (`odin` → `allfather`), the scripts named after it (`odin_max.py` → `allfather_max.py`, `odin_action.py` → `allfather_action.py`), the operating points (`odin-fast`, `odin-max`, `odin-escalation` → `allfather-fast`, `allfather-max`, `allfather-escalation`, including the sealed holdout's allowed list, which nothing has been evaluated against), environment variables (`ODIN_*` → `ALLFATHER_*`, with the old names still read so existing cluster configurations keep working), test fixtures, and the website's storage keys and offline cache.
- **History keeps the old name.** Decision records 0001 to 0029, every file under `results/`, and the committed data are records of what was done when the project was called Odin; rewriting them would change the record. Commands and module paths in them refer to `odin`, which is now `allfather`.
- **The website is redesigned at the same time:** a modern developer-tool look (neutral palette, one gold accent, sans-serif headings, a simple mark) replaces the gilded Norse style.
- **Infrastructure follows in a separate step:** the Cloudflare Worker, its database and the Modal app keep their internal names until they are moved with their secrets, which only the owner can enter.

## Consequences

- Links to the old GitHub repository keep working after it is renamed (GitHub redirects them), but workflows that use the Action should reference the new name.
- Visitors' cached repositories in the browser are built again once, because the storage keys changed.
