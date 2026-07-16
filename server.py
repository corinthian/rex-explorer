"""Rex Explorer — HTTP server wrapping the Last.fm client."""

import json
import logging
import math
import mimetypes
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lastfm import LastFM, LastFMError
from pathfind import find_chain

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PORT = 8787
STATIC_DIR = Path(__file__).parent / "static"
CONFIG_PATH = Path(
    os.environ.get("REX_CONFIG_PATH")
    or Path.home() / ".config" / "rex" / "config.json"
)
CACHE_DIR = Path(
    os.environ.get("REX_CACHE_DIR")
    or Path.home() / ".cache" / "rex"
)


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
            logging.exception(
                "failed to read Last.fm config at %s; falling back to "
                "'no key found' error", CONFIG_PATH,
            )
    raise RuntimeError(
        f"No Last.fm API key found. Set LASTFM_API_KEY env var, or "
        f'put {{"api_key": "..."}} at {CONFIG_PATH} '
        f"(override path with REX_CONFIG_PATH)."
    )


_client: LastFM | None = None
_image_cache: dict = {}  # artist name -> image URL or None
_image_cache_lock = threading.Lock()
_image_inflight: dict = {}  # artist name -> Future[str | None]
_IMAGE_CACHE_MAX = 5000  # cap entries; oldest evicted when exceeded
_no_chain_cache: dict = {}  # frozenset({a_lc, b_lc}) -> timestamp
_no_chain_cache_lock = threading.Lock()
_NO_CHAIN_TTL = 86400  # 24 h
_NO_CHAIN_MAX = 1000   # cap entries; oldest evicted when exceeded
_chain_slots = threading.BoundedSemaphore(2)  # cap concurrent /api/chain runs

MAX_PARAM_LENGTH = 200


def _clean_param(params, key):
    value = params.get(key, "").strip()
    if not value or len(value) > MAX_PARAM_LENGTH or any(ord(c) < 32 for c in value):
        return None
    return value


def _no_chain_record(key: frozenset) -> None:
    """Record a no-path result; sweep expired and cap size under a lock."""
    now = time.time()
    with _no_chain_cache_lock:
        # Drop expired entries opportunistically
        expired = [k for k, ts in _no_chain_cache.items()
                   if now - ts >= _NO_CHAIN_TTL]
        for k in expired:
            _no_chain_cache.pop(k, None)
        _no_chain_cache[key] = now
        # Hard cap: evict oldest insertion-order entries until under limit
        while len(_no_chain_cache) > _NO_CHAIN_MAX:
            oldest = next(iter(_no_chain_cache))
            _no_chain_cache.pop(oldest, None)


def _no_chain_check(key: frozenset) -> bool:
    """Return True if a fresh no-path entry exists for this pair."""
    with _no_chain_cache_lock:
        ts = _no_chain_cache.get(key)
        if ts is None:
            return False
        if time.time() - ts >= _NO_CHAIN_TTL:
            _no_chain_cache.pop(key, None)
            return False
        return True


def _rank_search_results(query: str, results: list[dict], top: int = 10) -> list[dict]:
    """Re-rank Last.fm artistmatches: prefer exact/prefix match, then listener count.

    Last.fm's native order weights name-token similarity heavily, surfacing
    obscure Unicode/capitalization variants above legitimate matches. This
    rebalances toward the popular, on-prefix artist while keeping query
    relevance dominant over raw popularity.
    """
    q_lc = query.lower().strip()

    def score(item):
        name = item.get("name", "")
        n_lc = name.lower()
        listeners = max(int(item.get("listeners", 0)), 1)
        if n_lc == q_lc:
            factor = 1.5
        elif n_lc.startswith(q_lc):
            factor = 1.0
        elif q_lc in n_lc:
            factor = 0.6
        else:
            factor = 0.2
        return factor * math.log10(listeners)

    ranked = sorted(results, key=score, reverse=True)
    return ranked[:top]


def get_client() -> LastFM:
    global _client
    if _client is None:
        _client = LastFM(_load_api_key(), cache_dir=CACHE_DIR)
    return _client


def _wikipedia_thumbnail(slug: str) -> str | None:
    """Fetch Wikipedia page summary and return image URL, or None.

    Returns the REST summary `thumbnail` (capped ~320px) rather than
    `originalimage`, which can be multi-MB. Node portraits and the
    detail-panel hero both render under 600px; the original source
    wastes bandwidth and stalls first paint.
    """
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
        return data.get("thumbnail", {}).get("source") or None
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
    timeout = 30

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
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
        q = _clean_param(params, "q")
        if not q:
            return self._error("missing q", 400)
        try:
            raw = get_client().artist_search(q, limit=30)
            self._json(_rank_search_results(q, raw, top=10))
        # %s only; the __cause__ chain holds the unredacted upstream URL
        except LastFMError as e:
            logging.warning("lastfm: %s", e)
            self._error(str(e))

    def _handle_artist(self, params):
        name = _clean_param(params, "name")
        if not name:
            return self._error("missing name", 400)
        try:
            info = get_client().artist_info(name)
            self._json(info)
        # %s only; the __cause__ chain holds the unredacted upstream URL
        except LastFMError as e:
            logging.warning("lastfm: %s", e)
            self._error(str(e))

    def _handle_similar(self, params):
        artist = _clean_param(params, "artist")
        if not artist:
            return self._error("missing artist", 400)
        try:
            limit = int(params.get("limit", 5))
        except ValueError:
            return self._error("invalid limit", 400)
        limit = max(1, min(limit, 50))
        try:
            results = get_client().similar_artists(artist, limit=limit)
            self._json(results)
        # %s only; the __cause__ chain holds the unredacted upstream URL
        except LastFMError as e:
            logging.warning("lastfm: %s", e)
            self._error(str(e))

    def _handle_chain(self, params):
        a = _clean_param(params, "from")
        b = _clean_param(params, "to")
        if not a or not b:
            return self._error("missing from or to", 400)
        cache_key = frozenset((a.lower(), b.lower()))
        if _no_chain_check(cache_key):
            return self._json({"error": "No path found — these artists may not be connected in Last.fm's similarity graph."})
        if not _chain_slots.acquire(blocking=False):
            return self._error("busy, try again shortly", 503)
        try:
            result = find_chain(get_client(), a, b)
            if result is None:
                _no_chain_record(cache_key)
                return self._json({"error": "No path found — these artists may not be connected in Last.fm's similarity graph."})
            self._json(result)
        # %s only; the __cause__ chain holds the unredacted upstream URL
        except LastFMError as e:
            logging.warning("lastfm: %s", e)
            self._error(str(e))
        finally:
            _chain_slots.release()

    def _handle_image(self, params):
        name = _clean_param(params, "name")
        if not name:
            return self._error("missing name", 400)

        with _image_cache_lock:
            if name in _image_cache:
                return self._json({"url": _image_cache[name]})
            fut = _image_inflight.get(name)
            if fut is None:
                fut = Future()
                _image_inflight[name] = fut
                owner = True
            else:
                owner = False

        if owner:
            try:
                url = _fetch_image_url(name)
            except Exception as e:
                with _image_cache_lock:
                    _image_inflight.pop(name, None)
                fut.set_exception(e)
                raise
            with _image_cache_lock:
                _image_cache[name] = url
                _image_inflight.pop(name, None)
                while len(_image_cache) > _IMAGE_CACHE_MAX:
                    oldest = next(iter(_image_cache))
                    _image_cache.pop(oldest, None)
            fut.set_result(url)
        else:
            url = fut.result()
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
        static_root = STATIC_DIR.resolve()
        try:
            file_path = (STATIC_DIR / path.lstrip("/")).resolve()
        except (OSError, RuntimeError):
            self.send_response(404)
            self.end_headers()
            return
        if not file_path.is_relative_to(static_root) or not file_path.is_file():
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
