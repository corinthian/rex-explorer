"""Last.fm API client with file-based caching and rate limiting."""

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
CACHE_TTL = 7 * 24 * 3600  # 7 days
MIN_REQUEST_INTERVAL = 0.2  # 200ms = ~5 req/sec


class LastFMError(Exception):
    pass


class LastFM:
    def __init__(self, api_key: str, cache_dir: Path = None):
        self.api_key = api_key
        self.cache_dir = cache_dir or Path.home() / ".cache" / "rex"
        self._last_request = 0.0

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

    def cache_stats(self) -> dict:
        if not self.cache_dir.exists():
            return {"files": 0, "bytes": 0}
        files = list(self.cache_dir.rglob("*.json"))
        total = sum(f.stat().st_size for f in files)
        return {"files": len(files), "bytes": total}

    def cache_clear(self) -> int:
        if not self.cache_dir.exists():
            return 0
        files = list(self.cache_dir.rglob("*.json"))
        for f in files:
            f.unlink()
        return len(files)

    # --------------------------------------------------------------- http

    def _request(self, method: str, params: dict) -> dict:
        params = {**params, "method": method, "api_key": self.api_key, "format": "json"}
        cache_path = self._cache_path(method, {k: v for k, v in params.items()
                                                if k not in ("api_key", "format")})
        cached = self._cache_get(cache_path)
        if cached is not None:
            return cached

        # rate limit
        elapsed = time.time() - self._last_request
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "rex-musicrec/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                data = json.loads(body)
            except Exception:
                raise LastFMError(f"HTTP {e.code}: {body[:200]}")
        finally:
            self._last_request = time.time()

        if "error" in data:
            # error 6 = artist/track not found — not fatal
            if data["error"] == 6:
                return {}
            raise LastFMError(f"Last.fm error {data['error']}: {data.get('message', '')}")

        self._cache_put(cache_path, data)
        return data

    # ------------------------------------------------------------- methods

    def similar_artists(self, artist: str, limit: int = 100) -> list[dict]:
        """Returns list of {name, match} sorted by match desc."""
        data = self._request("artist.getSimilar", {
            "artist": artist, "limit": limit, "autocorrect": 1
        })
        artists = data.get("similarartists", {}).get("artist", [])
        return [{"name": a["name"], "match": float(a["match"])} for a in artists]

    def artist_top_tracks(self, artist: str, limit: int = 10) -> list[str]:
        """Returns list of track names."""
        data = self._request("artist.getTopTracks", {
            "artist": artist, "limit": limit, "autocorrect": 1
        })
        tracks = data.get("toptracks", {}).get("track", [])
        return [t["name"] for t in tracks]

    def artist_tags(self, artist: str) -> list[dict]:
        """Returns list of {name, count} for top tags."""
        data = self._request("artist.getTopTags", {
            "artist": artist, "autocorrect": 1
        })
        tags = data.get("toptags", {}).get("tag", [])
        return [{"name": t["name"].lower(), "count": int(t["count"])} for t in tags]

    def track_similar(self, artist: str, track: str, limit: int = 50) -> list[dict]:
        """Returns list of {name, artist, match}."""
        data = self._request("track.getSimilar", {
            "artist": artist, "track": track, "limit": limit, "autocorrect": 1
        })
        tracks = data.get("similartracks", {}).get("track", [])
        return [
            {"name": t["name"], "artist": t["artist"]["name"], "match": float(t["match"])}
            for t in tracks
        ]

    def tag_top_artists(self, tag: str, limit: int = 50) -> list[str]:
        """Returns list of artist names."""
        data = self._request("tag.getTopArtists", {"tag": tag, "limit": limit})
        artists = data.get("topartists", {}).get("artist", [])
        return [a["name"] for a in artists]

    def user_top_artists(self, username: str, period: str = "overall",
                         limit: int = 200) -> list[dict]:
        """Returns list of {name, playcount} for a Last.fm user."""
        data = self._request("user.getTopArtists", {
            "user": username, "period": period, "limit": limit
        })
        artists = data.get("topartists", {}).get("artist", [])
        return [{"name": a["name"], "playcount": int(a["playcount"])} for a in artists]

    def user_top_tracks(self, username: str, period: str = "overall",
                        limit: int = 100) -> list[dict]:
        """Returns list of {name, artist, playcount}."""
        data = self._request("user.getTopTracks", {
            "user": username, "period": period, "limit": limit
        })
        tracks = data.get("toptracks", {}).get("track", [])
        return [
            {"name": t["name"], "artist": t["artist"]["name"],
             "playcount": int(t["playcount"])}
            for t in tracks
        ]

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
