# Rex Explorer — Project Status
**Last updated: 2026-04-20**

## What it is
Visual Last.fm artist similarity explorer. Python HTTP backend + vanilla JS force-directed
graph. Search for an artist, click to expand their similar artists, explore the graph.

## Current state: chain finder complete and merged to main

### Core features (done)
- Force-directed graph via `force-graph@1.43.5`
- Artist search with listener counts in dropdown
- Click node to expand 5 similar artists; click again to collapse
- Artist detail panel (portrait, tags, bio, Last.fm link)
- Node portraits from Wikipedia REST API with `_(band)` / `_(musician)` fallbacks, then iTunes
- Pointer repulsion and node pinning on hover
- Zoom/center controls
- Background animation on landing screen
- 7-day file cache at `~/.cache/rex/`, 200ms rate limit

### Chain finder (complete — merged to main)
Find the path of similar artists connecting two arbitrary artists.

**Algorithm:** bidirectional Dijkstra in `pathfind.py`. Expands from both endpoints
simultaneously (60 API calls per side budget). Edge weight = `1 - match` so the
returned path maximizes musical similarity at every link.

**Endpoint:** `GET /api/chain?from=A&to=B`
Returns `{from, to, hops, path: [{name, match_to_next}], total_score}`
Returns `{"error": "no chain found within bounds"}` (HTTP 404) when no path exists.

**Confirmed working examples:**
- Boards of Canada → Mogwai: 7 hops via Oneohtrix Point Never → Tim Hecker →
  A Silver Mt. Zion → Do Make Say Think → This Will Destroy You → Explosions in the Sky
- Boards of Canada → The The: no chain found (correctly surfaces error in UI)

**Graph rendering:** chain links render amber (`#f0b060`), thicker (4px vs 1.5px).
New chain nodes spawn along the line between the two endpoints. View zooms to fit
after 800ms. No JS console errors.

**UI:**
Persistent amber-bordered "Find connection from [root]…" input sits to the right of
the main search in a single horizontal flex row. Flexible spacer separates it from
the "Clear chain" button at the right edge. Hint and error messages appear below the
row at readable contrast. Clicking any graph node updates both the main search box
and the connect-from placeholder; stale error messages are cleared.

**Bugs fixed this session:**
- `pathfind.py` `ValueError` when Last.fm returns an artist as its own similar artist
  (self-loop in frozenset unpacking). Fixed with self-loop guard in expansion + adjacency builder.
- Clicking a graph node did not update the main search input to reflect the new artist.
- Clicking a graph node did not clear a stale chain error message.

## Known minor issue
`/api/chain` returns HTTP 404 for the "no chain found" case instead of 200. The UI
handles it correctly (shows the error text), but it logs a spurious browser console error.
One-liner fix: change response code to 200 in `_handle_chain` for the error JSON case.

## Running
```
python3 server.py
```
Opens at http://localhost:8787. Requires Last.fm API key in `~/.config/rex/config.json`
or `LASTFM_API_KEY` env var.

## File map
```
server.py       HTTP server — 5 endpoints + static files
lastfm.py       Last.fm client — similar_artists, artist_search, artist_info
pathfind.py     Bidirectional Dijkstra for chain finder
static/
  index.html
  app.js        All graph logic, search, chain, detail panel
  style.css
```
