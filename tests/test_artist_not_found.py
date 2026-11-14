"""D1: an artist Last.fm does not know answers 404 from /api/artist,
fresh and from the 24 hour cache, with no warning and no 500."""

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from helpers import make_client, request, running_server, server

from lastfm import ArtistNotFound, LastFMError

NOT_FOUND = {"error": "Artist not found on Last.fm."}
MISSING = "Nobody At All"
SIMILAR = [{"name": "Thom Yorke", "match": "0.9"}, {"name": "Atoms for Peace", "match": "0.8"}]


def responder(params):
    """Radiohead exists, with one similar artist that links back; every
    other artist is unknown to Last.fm."""
    known = params.get("artist", "").strip().lower() == "radiohead"
    method = params["method"]
    if method == "artist.search":
        matches = [{"name": "Radiohead", "listeners": "5000"}] if known else []
        return {"results": {"artistmatches": {"artist": matches}}}
    if not known:
        return {"error": 6, "message": "The artist you supplied could not be found"}
    if method == "artist.getInfo":
        return {"artist": {
            "name": "Radiohead",
            "stats": {"listeners": "5000"},
            "tags": {"tag": [{"name": "Rock"}]},
            "bio": {"summary": "An English band."},
            "url": "https://www.last.fm/music/Radiohead",
        }}
    return {"similarartists": {"artist": SIMILAR}}


class NotFoundTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = make_client(self.tmp.name, responder)
        ctx = running_server(self.client)
        self.port = ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        server._no_chain_cache.clear()
        self.addCleanup(server._no_chain_cache.clear)

    def get(self, path):
        status, headers, body = request(self.port, "GET", path)
        return status, headers, json.loads(body)

    def get_quiet(self, path):
        """GET that fails if anything at WARNING or above is logged."""
        with self.assertNoLogs(level=logging.WARNING):
            return self.get(path)


class TestArtistNotFound(NotFoundTestCase):
    def test_fresh_not_found_returns_404_json(self):
        status, headers, body = self.get_quiet(f"/api/artist?name={quote(MISSING)}")
        self.assertEqual(status, 404)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(body, NOT_FOUND)
        self.assertEqual(len(self.client.calls), 1)

    def test_cached_not_found_returns_404_json(self):
        self.get(f"/api/artist?name={quote(MISSING)}")
        entries = list(Path(self.tmp.name).glob("artist.getInfo/*.json"))
        self.assertEqual(len(entries), 1)
        self.assertEqual(json.loads(entries[0].read_text())["data"], {})
        status, _, body = self.get_quiet(f"/api/artist?name={quote(MISSING.upper())}")
        self.assertEqual(status, 404)
        self.assertEqual(body, NOT_FOUND)
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(self.client.stats["cache_hit"], 1)

    def test_normal_artist_still_returns_200(self):
        status, _, body = self.get_quiet("/api/artist?name=Radiohead")
        self.assertEqual(status, 200)
        self.assertEqual(body, {
            "name": "Radiohead",
            "listeners": 5000,
            "tags": ["rock"],
            "bio_summary": "An English band.",
            "url": "https://www.last.fm/music/Radiohead",
        })

    def test_client_raises_artist_not_found_fresh_and_cached(self):
        for _ in range(2):
            with self.assertRaises(ArtistNotFound):
                self.client.artist_info(MISSING)
        self.assertEqual(len(self.client.calls), 1)

    def test_other_upstream_errors_still_answer_500_with_a_warning(self):
        client = make_client(self.tmp.name + "/other",
                             lambda p: {"error": 29, "message": "Rate limit"})
        with patch.object(server, "get_client", lambda: client):
            with self.assertLogs(level=logging.WARNING):
                status, _, body = self.get("/api/artist?name=Radiohead")
        self.assertEqual(status, 500)
        self.assertEqual(body, {"error": "Last.fm error 29"})


class TestOtherEndpointsUnchanged(NotFoundTestCase):
    def test_similar_for_missing_artist_is_200_empty_list(self):
        for _ in range(2):
            status, _, body = self.get_quiet(
                f"/api/similar?artist={quote(MISSING)}&limit=5")
            self.assertEqual(status, 200)
            self.assertEqual(body, [])
        self.assertEqual(len(self.client.calls), 1)

    def test_similar_client_call_does_not_raise(self):
        try:
            self.assertEqual(self.client.similar_artists(MISSING, limit=5), [])
        except LastFMError:
            self.fail("similar_artists raised for a missing artist")

    def test_search_with_no_matches_is_200_empty_list(self):
        status, _, body = self.get_quiet(f"/api/search?q={quote(MISSING)}")
        self.assertEqual(status, 200)
        self.assertEqual(body, [])

    def test_chain_with_missing_artist_is_404_no_path(self):
        status, _, body = self.get_quiet(
            f"/api/chain?from=Radiohead&to={quote(MISSING)}")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": server.NO_PATH_MSG})


if __name__ == "__main__":
    unittest.main()
