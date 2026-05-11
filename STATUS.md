# Bug-fix status

Tracks findings from the 2026-05-06 code review.

## Completed

- [x] **Path traversal in `_serve_static`** — resolve incoming path and require `is_relative_to(STATIC_DIR)` before serving. (`server.py`, commit `20baa40`)
- [x] **Wildcard CORS** — dropped `Access-Control-Allow-Origin: *` from `_json`. SPA is same-origin; the wildcard widened DNS-rebinding surface. (`server.py`, commit `20baa40`)
- [x] **`_image_cache` race** — per-name `Future` map guarded by a lock; concurrent `/api/image` callers reuse the in-flight result. (`server.py`, commit `1d349d9`)
- [x] **`setInterval` leak in `showDetail`** — module-level handle, cleared on detail-close, Escape-close, and at the top of every `showDetail`. Poll callback also bails when panel hidden or name changed. (`static/app.js`, commit `957517b`)
- [x] **`_cache_put` non-atomic** — write to `<path>.tmp` then `os.replace`; partial writes never become visible. (`lastfm.py`, commit `f9b795f`)
- [x] **Wikipedia `originalimage` bandwidth** — drop the originalimage fallback; REST summary `thumbnail` (~320px) is enough for both node portraits and the detail hero. (`server.py`, commit `60abc71`)

## Pending — high priority

(none)

## Completed — medium priority

- [x] **`stats` counters unlocked** — dedicated `_stats_lock` + `_bump` helper around every increment. (`lastfm.py`, commit `e44b56a`)
- [x] **Bio HTML strip too narrow** — strip every tag, decode entities via `html.unescape`, then collapse whitespace. (`lastfm.py`, commit `e44b56a`)
- [x] **`_no_chain_cache` unbounded growth** — `_no_chain_record` / `_no_chain_check` helpers with TTL sweep + LRU cap (1000 entries). (`server.py`, commit `3b73903`)
- [x] **`_load_api_key` swallows JSON errors** — `logging.exception` before falling back to the "no key found" RuntimeError. (`server.py`, commit `3b73903`)
- [x] **`addLink` O(n) scan per insertion** — mirror `links` with a `linkKeys` Set; `collapseNode` removes from both `linkKeys` and `chainLinkKeys` when pruning. (`static/app.js`, commit `2fcf229`)
- [x] **`addChainTo` no abort/version guard** — `addChainVersion` token plus captured root snapshot; bail post-await on mismatch. (`static/app.js`, commit `2fcf229`)

## Completed — low priority / nitpicks

- [x] **`import math` hoisted** to module top in `server.py`. (commit `d1eab15`)
- [x] **`float(a["match"])` brittle** — guarded via `float(a.get("match") or 0)`. (`lastfm.py`, commit `d1eab15`)
- [x] **`pathfind.integrate` shared-dict comment** — added a note explaining the function runs single-threaded after the futures resolve. (`pathfind.py`, commit `d1eab15`)
- [x] **`imageCache.delete` on collapse** — `collapseNode` no longer evicts portraits; re-expansion reuses the cached image. (`static/app.js`, commit `d1eab15`)

- [x] **`app.js` modular split** — 1100-line monolith carved into 8 ES modules (utils, state, graph, bg-graph, detail, chain, search, app entry). Behavior preserved. (commit `de45948`)

## Post-review improvements

- [x] **Purge defunct recommender references** — old `_load_api_key` error told users to "run 'python3 -m rex setup' in the recommender project", a project that no longer exists. New message names the actual config path and the `REX_CONFIG_PATH` override. CLAUDE.md "(shared with the recommender)" note dropped. (`server.py`, `CLAUDE.md`, commit `c0b47d6`)
- [x] **Path overrides for config and cache** — `REX_CONFIG_PATH` and `REX_CACHE_DIR` env vars override the `~/.config/rex/` and `~/.cache/rex/` defaults. Required for the server deploy where both live under `/data/rex-explorer/`; host runs and the in-repo compose still use the defaults. (`server.py`, commit `460c7aa`)
- [x] **Docker packaging for linux/amd64 deploy** — `Dockerfile` (python:3.11-slim), `requirements.txt` pinning `requests<3`, `docker-compose.yml` mounting `~/.config/rex/config.json` read-only and a named `rex-cache` volume. Code is pure Python so no native-extension porting was needed; built with `docker buildx --platform linux/amd64`. Verified running on M-series host via Rosetta. (branch `docker-support`, commit `0860455`)
- [x] **Skip Last.fm calls for short queries** — both search and connect inputs hold fire until the query is ≥ 3 characters. Saves rate-limit budget on the keystrokes that almost never produce useful matches. (`static/search.js`, commit `5ff6197`)
- [x] **Search input shows current root** — `addRootArtist` no longer clears the search input on completion; the input now serves as the persistent current-root display, updated by `handleNodeClick` when the user re-roots. (`static/chain.js`, commit `2ce252d`)
- [x] **Pin closest node within repulsion radius** — the pointer-repulsion force engages at 55 graph units, but pinning was 24, so dense clusters scattered when the pointer approached. Now the closest node within the same 55-unit radius gets pinned; it freezes for the click while peers flow out of the way to disambiguate. (`static/graph.js`, commit `f2d984c`)

## Reverted / failed attempts

- [~] **Stable nodes array for force-graph rebinds** — attempted in `591873a`, reverted in `f9b3148`. Force-graph's Kapsule layer short-circuits on `===` reference equality of `data.nodes`, so newly pushed nodes never bound and the tree could disappear after rapid expansion. The spread was the right answer all along.

## Deferred / won't fix

- **`refreshGraph` allocates fresh arrays on every call** — required by force-graph; passing the same array reference suppresses node binding (see reverted attempt above). Real wins live inside force-graph itself, not in our code.
- **`app.js` further modular split** — current 8-module layout is coherent. No further breakup planned.
