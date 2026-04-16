"""Rex Explorer — HTTP server wrapping the Last.fm client."""

import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lastfm import LastFM, LastFMError

PORT = 8787
STATIC_DIR = Path(__file__).parent / "static"
CONFIG_PATH = Path.home() / ".config" / "rex" / "config.json"


def _load_api_key() -> str:
    key = os.environ.get("LASTFM_API_KEY")
    if key:
        return key
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            if cfg.get("api_key"):
                return cfg["api_key"]
        except Exception:
            pass
    raise RuntimeError(
        "No Last.fm API key found. Set LASTFM_API_KEY env var or run "
        "'python3 -m rex setup' in the recommender project."
    )


_client: LastFM | None = None
_image_cache: dict = {}  # artist name -> image URL or None


def get_client() -> LastFM:
    global _client
    if _client is None:
        _client = LastFM(_load_api_key())
    return _client


def _fetch_image_url(name: str) -> str | None:
    """Try Wikipedia thumbnail, fall back to iTunes album art."""
    # 1. Wikipedia REST API
    try:
        slug = urllib.parse.quote(name.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": "rex-musicrec/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        thumb = data.get("thumbnail", {}).get("source")
        if thumb:
            # Prefer larger version if available
            original = data.get("originalimage", {}).get("source")
            return original or thumb
    except Exception:
        pass

    # 2. iTunes album art fallback
    try:
        query = urllib.parse.urlencode({"term": name, "entity": "album", "limit": 1})
        url = f"https://itunes.apple.com/search?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "rex-musicrec/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if results:
            art = results[0].get("artworkUrl100", "")
            if art:
                return art.replace("100x100bb", "300x300bb")
    except Exception:
        pass

    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, msg, status=500):
        self._json({"error": msg}, status)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        path = parsed.path

        if path == "/api/search":
            self._handle_search(params)
        elif path == "/api/artist":
            self._handle_artist(params)
        elif path == "/api/similar":
            self._handle_similar(params)
        elif path == "/api/image":
            self._handle_image(params)
        else:
            self._serve_static(path)

    def _handle_search(self, params):
        q = params.get("q", "").strip()
        if not q:
            return self._error("missing q", 400)
        try:
            results = get_client().artist_search(q, limit=10)
            self._json(results)
        except LastFMError as e:
            self._error(str(e))

    def _handle_artist(self, params):
        name = params.get("name", "").strip()
        if not name:
            return self._error("missing name", 400)
        try:
            info = get_client().artist_info(name)
            self._json(info)
        except LastFMError as e:
            self._error(str(e))

    def _handle_similar(self, params):
        artist = params.get("artist", "").strip()
        if not artist:
            return self._error("missing artist", 400)
        try:
            limit = int(params.get("limit", 5))
            results = get_client().similar_artists(artist, limit=limit)
            self._json(results)
        except LastFMError as e:
            self._error(str(e))

    def _handle_image(self, params):
        name = params.get("name", "").strip()
        if not name:
            return self._error("missing name", 400)
        if name in _image_cache:
            return self._json({"url": _image_cache[name]})

        url = _fetch_image_url(name)
        _image_cache[name] = url
        self._json({"url": url})

    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        file_path = STATIC_DIR / path.lstrip("/")
        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    try:
        get_client()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Rex Explorer running at http://localhost:{PORT}")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
