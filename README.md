# rex-explorer

### → [Try it live at rex.rlarsen.tech](https://rex.rlarsen.tech)

Visual Last.fm artist similarity explorer. Search an artist, expand the node, and the graph grows outward through related artists. A force-directed canvas, real portraits where they exist, and a chain finder that connects any two artists through their shortest similarity path.

## What it does

- **Search** any artist by name; results re-ranked by match quality × log10(listeners) so the obvious answer wins.
- **Expand** a node to fan out 5 most-similar artists; click again to collapse the leaves.
- **Connect** two artists — bidirectional Dijkstra over the similarity graph finds a path.
- **Detail panel** shows portrait, tags, listener count, bio, and a Last.fm link.
- **Pointer-aware physics**: nodes part as your cursor approaches; the node under it freezes for clicking.

## Quick start

### Docker (recommended)

```sh
export LASTFM_API_KEY=your_key_here
docker compose up -d
```

Open <http://localhost:8787>.

### Local Python

```sh
pip install -r requirements.txt
export LASTFM_API_KEY=your_key_here
python3 server.py
```

### API key

Get one at <https://www.last.fm/api/account/create>. Provide it via either:

- `LASTFM_API_KEY` env var, or
- `~/.config/rex/config.json` → `{"api_key": "..."}`

`REX_CONFIG_PATH` and `REX_CACHE_DIR` override the defaults.

## API

- `GET /api/search?q=<query>` → `[{name, listeners}]`
- `GET /api/artist?name=<name>` → `{name, tags, listeners, bio_summary, url}`
- `GET /api/similar?artist=<name>&limit=5` → `[{name, match}]`
- `GET /api/chain?from=<a>&to=<b>` → similarity path between two artists
- `GET /api/image?name=<name>` → `{url}` — Wikipedia thumbnail with `_(band)`/`_(musician)` fallbacks, then iTunes album art

Cache lives at `~/.cache/rex/` with a 7-day TTL and a 200ms rate limit on Last.fm calls.

## Stack

- **Backend**: Python 3 stdlib `ThreadingHTTPServer`, `requests` for Last.fm.
- **Frontend**: vanilla JS, no build step. Force-directed graph via [`force-graph@1.43.5`](https://github.com/vasturiano/force-graph).
- **Deploy**: Docker, Nginx reverse proxy, Let's Encrypt.

## Notes

- Last.fm deprecated artist images around 2020. Portraits resolve through Wikipedia and iTunes; nodes fall back to colored initials when nothing matches.
- Session-only state in browser memory. Nothing persists across reloads.
- Keyboard shortcuts: `/` focus search, `Esc` close detail, `+`/`-` zoom, `0` recenter on root.

## License

MIT.
