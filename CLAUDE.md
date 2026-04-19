# rex-explorer

Interactive artist graph visualization using Last.fm data.

## Running

```
python3 server.py
```

Opens at http://localhost:8787. Requires a Last.fm API key in `~/.config/rex/config.json` (shared with the recommender) or `LASTFM_API_KEY` env var.

## Structure

```
server.py       ThreadingHTTPServer — four API endpoints + static file serving
lastfm.py       Last.fm client — similar_artists, artist_search, artist_info; file-based cache
static/
  index.html    Single-page app
  app.js        Graph logic (force-graph, search, expand/collapse, controls)
  style.css     Dark theme
```

## API endpoints

- `GET /api/search?q=<query>` → `[{name, listeners}]`
- `GET /api/artist?name=<name>` → `{name, tags, listeners, bio_summary, url}`
- `GET /api/similar?artist=<name>&limit=5` → `[{name, match}]`
- `GET /api/image?name=<name>` → `{url}` — Wikipedia thumbnail (tries plain, _(band), _(musician)), falls back to iTunes album art

## UI features

- **Search panel** (top-left): debounced artist search with listener counts in dropdown
- **Graph**: force-directed canvas via `force-graph@1.43.5`. Nodes show artist portrait (or colored initials while loading). Click to expand (shows 5 similar artists), click again to collapse leaf children.
- **Pointer repulsion**: nodes gently part as pointer approaches (radius 55px, strength 0.7). Node under pointer freezes (`fx`/`fy`) so it can be clicked.
- **Detail panel** (bottom-left, 600px wide): hero image + name/listeners always visible; tags row always visible; bio + Last.fm link slide up on hover (max-height transition). Close button top-right. Center-on-artist button (52×26px, 2:1) in hero next to name.
- **Controls** (bottom-right): zoom in (+), zoom out (−), center on root artist (⌖). All have styled tooltips.

## Key implementation notes

- Last.fm deprecated artist images ~2020. Node portraits come from Wikipedia REST API with `_(band)`/`_(musician)` disambiguation fallbacks, then iTunes album art. Nodes fall back to HSL color + initials if no image resolves.
- Tooltips inside `overflow:hidden` containers (detail panel hero) use a JS floating `div` appended to `<body>`. CSS `::after` tooltips are used for buttons outside those containers.
- Cache at `~/.cache/rex/` — 7-day TTL, 200ms rate limit. Image URLs cached in-memory per session only.
- Session-only graph state — in-memory JS Maps. Nothing persists across browser sessions.
- Root node name tracked in `rootNodeName` for the center-on-root control.
- Node charge force: -350. Link distance: 120px.
