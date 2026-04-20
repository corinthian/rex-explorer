"""Last.fm API client with file-based caching and rate limiting."""

import hashlib
import json
import os
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
CACHE_TTL = 7 * 24 * 3600  # 7 days
MIN_REQUEST_INTERVAL = 0.2  # 200ms = ~5 req/sec; override via REX_LASTFM_INTERVAL_MS


class LastFMError(Exception):
    pass


class LastFM:
    def __init__(self, api_key: str, cache_dir: Path = None):
        self.api_key = api_key
        self.cache_dir = cache_dir or Path.home() / ".cache" / "rex"

        interval_ms = int(os.environ.get("REX_LASTFM_INTERVAL_MS",
                                         int(MIN_REQUEST_INTERVAL * 1000)))
        # Lowering below 200ms may provoke Last.fm rate-limit cooldown (error 29).
        # TOS averages over 5min but enforcement is stricter in practice.
        self._min_interval = interval_ms / 1000.0

        self._last_request = 0.0
        self._request_lock = threading.Lock()

        self._inflight: dict[str, Future] = {}
        self._inflight_lock = threading.Lock()

        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=8)
        self._session.mount("https://", adapter)

        self.stats = {"cache_hit": 0, "dedup_hit": 0, "network": 0}

    # ------------------------------------------------------------------ cache

    def _cache_path(self, method: str, params: dict) -> Path:
        key = method + json.dumps(sorted(params.items()))
        digest = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / method / f"{digest}.json"

    def _cache_get(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data["fetched"] < CACHE_TTL:
                return data["data"]
        except Exception:
            pass
        return None

    def _cache_put(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched": time.time(), "data": data}))

    # --------------------------------------------------------------- http

    def _request(self, method: str, params: dict) -> dict:
        params = {**params, "method": method, "api_key": self.api_key, "format": "json"}
        cache_key_params = {k: v for k, v in params.items()
                            if k not in ("api_key", "format")}
        cache_path = self._cache_path(method, cache_key_params)

        cached = self._cache_get(cache_path)
        if cached is not None:
            self.stats["cache_hit"] += 1
            return cached

        inflight_key = method + json.dumps(sorted(cache_key_params.items()))

        with self._inflight_lock:
            fut = self._inflight.get(inflight_key)
            if fut is None:
                fut = Future()
                self._inflight[inflight_key] = fut
                owner = True
            else:
                owner = False

        if not owner:
            self.stats["dedup_hit"] += 1
            return fut.result()  # blocks; re-raises on failure

        try:
            # Serialize throttle wait; record dispatch time before releasing lock
            with self._request_lock:
                elapsed = time.time() - self._last_request
                if elapsed < self._min_interval:
                    time.sleep(self._min_interval - elapsed)
                self._last_request = time.time()

            resp = self._session.get(
                BASE_URL, params=params,
                headers={"User-Agent": "rex-musicrec/1.0"}, timeout=15
            )
            try:
                data = resp.json()
            except Exception:
                resp.raise_for_status()
                raise LastFMError(f"HTTP {resp.status_code}: non-JSON response")

            if "error" in data:
                if data["error"] == 6:
                    data = {}
                else:
                    raise LastFMError(
                        f"Last.fm error {data['error']}: {data.get('message', '')}"
                    )

            if data:
                self._cache_put(cache_path, data)
            self.stats["network"] += 1
            fut.set_result(data)
            return data
        except Exception as e:
            fut.set_exception(e)
            raise
        finally:
            with self._inflight_lock:
                self._inflight.pop(inflight_key, None)

    # ------------------------------------------------------------- methods

    def similar_artists(self, artist: str, limit: int = 100) -> list[dict]:
        """Returns list of {name, match} sorted by match desc."""
        data = self._request("artist.getSimilar", {
            "artist": artist, "limit": limit, "autocorrect": 1
        })
        artists = data.get("similarartists", {}).get("artist", [])
        return [{"name": a["name"], "match": float(a["match"])} for a in artists]

    def artist_search(self, query: str, limit: int = 10) -> list[dict]:
        """Returns list of {name, listeners} matching query."""
        data = self._request("artist.search", {"artist": query, "limit": limit})
        results = data.get("results", {}).get("artistmatches", {}).get("artist", [])
        return [
            {"name": a["name"], "listeners": int(a.get("listeners", 0))}
            for a in results
        ]

    def artist_info(self, artist: str) -> dict:
        """Returns {name, tags, listeners, bio_summary, url} for an artist."""
        import re
        data = self._request("artist.getInfo", {"artist": artist, "autocorrect": 1})
        info = data.get("artist", {})
        tags = [t["name"].lower() for t in info.get("tags", {}).get("tag", [])]
        bio = info.get("bio", {}).get("summary", "")
        bio = re.sub(r"<a [^>]+>.*?</a>", "", bio).strip()
        return {
            "name": info.get("name", artist),
            "listeners": int(info.get("stats", {}).get("listeners", 0)),
            "tags": tags,
            "bio_summary": bio,
            "url": info.get("url", ""),
        }
