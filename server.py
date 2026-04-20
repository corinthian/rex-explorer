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
from pathfind import find_chain

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


def _wikipedia_thumbnail(slug: str) -> str | None:
    """Fetch Wikipedia page summary and return image URL, or None."""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
        req = urllib.request.Request(url, headers={"User-Agent": "rex-musicrec/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode())
        # Skip disambiguation pages — they have no useful image
        if data.get("type") == "disambiguation":
            return None
        thumb = data.get("thumbnail", {}).get("source")
        if not thumb:
            return None
        original = data.get("originalimage", {}).get("source")
        return original or thumb
    except Exception:
        return None


def _fetch_image_url(name: str) -> str | None:
    """Try Wikipedia (with band/musician fallbacks), then iTunes album art."""
    # 1. Wikipedia — try plain name, then _(band), then _(musician)
    slug_base = name.replace(" ", "_")
    for slug in (slug_base, f"{slug_base}_(band)", f"{slug_base}_(musician)"):
        url = _wikipedia_thumbnail(slug)
        if url:
            return url

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

        if path == "/favicon.ico":
            self._serve_favicon()
        elif path == "/api/search":
            self._handle_search(params)
        elif path == "/api/artist":
            self._handle_artist(params)
        elif path == "/api/similar":
            self._handle_similar(params)
        elif path == "/api/image":
            self._handle_image(params)
        elif path == "/api/chain":
            self._handle_chain(params)
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

    def _handle_chain(self, params):
        a = params.get("from", "").strip()
        b = params.get("to", "").strip()
        if not a or not b:
            return self._error("missing from or to", 400)
        try:
            result = find_chain(get_client(), a, b)
            if result is None:
                return self._error("no chain found within bounds", 404)
            self._json(result)
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

    def _serve_favicon(self):
        # Minimal 1x1 transparent ICO — 70 bytes, no dependencies
        # ICONDIR(6) + ICONDIRENTRY(16) + BITMAPINFOHEADER(40) + pixel(4) + AND mask(4)
        ICO = (
            b'\x00\x00'          # reserved
            b'\x01\x00'          # type: ICO
            b'\x01\x00'          # 1 image
            # ICONDIRENTRY
            b'\x01'              # width 1
            b'\x01'              # height 1
            b'\x00'              # color count
            b'\x00'              # reserved
            b'\x01\x00'          # planes
            b'\x20\x00'          # bit count: 32
            b'\x30\x00\x00\x00'  # size of image data: 48 bytes
            b'\x16\x00\x00\x00'  # offset to image data: 22
            # BITMAPINFOHEADER (40 bytes)
            b'\x28\x00\x00\x00'  # header size
            b'\x01\x00\x00\x00'  # width
            b'\x02\x00\x00\x00'  # height (2x for XOR+AND)
            b'\x01\x00'          # planes
            b'\x20\x00'          # bit count: 32
            b'\x00\x00\x00\x00'  # compression: none
            b'\x00\x00\x00\x00'  # image size
            b'\x00\x00\x00\x00'  # x pixels/meter
            b'\x00\x00\x00\x00'  # y pixels/meter
            b'\x00\x00\x00\x00'  # colors used
            b'\x00\x00\x00\x00'  # colors important
            # XOR pixel: 1 pixel, 32-bit BGRA fully transparent
            b'\x00\x00\x00\x00'
            # AND mask: 4 bytes (1 row, padded to DWORD) — 1 = transparent
            b'\x00\x00\x00\x00'
        )
        self.send_response(200)
        self.send_header("Content-Type", "image/x-icon")
        self.send_header("Content-Length", len(ICO))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(ICO)

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
