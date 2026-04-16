# rex-explorer

Interactive artist graph visualization using Last.fm data.

## Running

```
python3 server.py
```

Opens at http://localhost:8787. Requires a Last.fm API key in `~/.config/rex/config.json` (shared with the recommender) or `LASTFM_API_KEY` env var.

## Structure

```
server.py       HTTP server — three API endpoints + static file serving
lastfm.py       Last.fm client (copied from recommender, extended with artist_search + artist_info)
static/
  index.html    Single-page app
  app.js        Graph logic (force-graph, search, expand/collapse)
  style.css     Dark theme
```

## API endpoints

- `GET /api/search?q=<query>` → `[{name, listeners}]`
- `GET /api/artist?name=<name>` → `{name, tags, listeners, bio_summary, url}`
- `GET /api/similar?artist=<name>&limit=5` → `[{name, match}]`

## Notes

- Last.fm deprecated artist images ~2020. Nodes use deterministic colors (HSL from name hash) + initials.
- Cache shared with recommender at `~/.cache/rex/` — 7-day TTL, 200ms rate limit.
- Session-only state — in-memory JS Maps. Nothing persists across browser sessions.
- Click an expanded node to collapse its leaf children.
- `lastfm.py` here diverges from the recommender copy — it has two extra methods. Do not blindly overwrite.
