"""B7: parameter validation, JSON 404s, trailing slash, no-path status
and cache pruning."""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from helpers import make_client, request, running_server, server

import lastfm

HOUR = 3600
DAY = 24 * HOUR
NO_PATH = "No path found. These artists may not be connected in Last.fm's similarity graph."
REJECTED = (
    [0x01, 0x1B, 0x7F, 0x80, 0x8D, 0x9F, 0x200E, 0x200F]
    + list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A))
)
ALLOWED = ["Radiohead", "Sigur Rós", "AC/DC", "¡Forward, Russia!",
           "スピッツ", "a b", "a⁥b", "a‍b", "a b"]


def empty_similar(params):
    return {"similarartists": {"artist": []}}


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        (root / "static").mkdir()
        (root / "static" / "index.html").write_text("<p>index</p>")
        patcher = patch.object(server, "STATIC_DIR", root / "static")
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        cls.client = make_client(root / "cache", empty_similar)
        ctx = running_server(cls.client)
        cls.port = ctx.__enter__()
        cls.addClassCleanup(ctx.__exit__, None, None, None)

    def get(self, path):
        status, headers, body = request(self.port, "GET", path)
        return status, headers, body


class TestControlCharacters(ServerTestCase):
    def test_del_c1_and_bidi_controls_are_rejected(self):
        for code in REJECTED:
            with self.subTest(code=hex(code)):
                self.assertIsNone(
                    server._clean_param({"q": f"ab{chr(code)}cd"}, "q"))

    def test_ordinary_names_are_kept(self):
        for value in ALLOWED:
            with self.subTest(value=value):
                self.assertEqual(server._clean_param({"q": value}, "q"), value)

    def test_endpoints_answer_400_missing_for_control_characters(self):
        bad = quote("ab‮cd")
        cases = [
            (f"/api/search?q={bad}", "missing q"),
            (f"/api/artist?name={bad}", "missing name"),
            (f"/api/similar?artist={bad}", "missing artist"),
            (f"/api/image?name=ab%7Fcd", "missing name"),
            (f"/api/chain?from={bad}&to=x", "missing from or to"),
            (f"/api/chain?from=x&to=ab%C2%85cd", "missing from or to"),
        ]
        for path, message in cases:
            with self.subTest(path=path):
                status, _, body = self.get(path)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body), {"error": message})
        self.assertEqual(self.client.calls, [])


class TestTooLong(ServerTestCase):
    def test_over_200_characters_answers_400_param_too_long(self):
        long = "a" * 201
        cases = [
            (f"/api/search?q={long}", "q too long"),
            (f"/api/artist?name={long}", "name too long"),
            (f"/api/similar?artist={long}", "artist too long"),
            (f"/api/image?name={long}", "name too long"),
            (f"/api/chain?from={long}&to=x", "from too long"),
            (f"/api/chain?from=x&to={long}", "to too long"),
        ]
        for path, message in cases:
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 400)
                self.assertEqual(headers["content-type"], "application/json")
                self.assertEqual(json.loads(body), {"error": message})
        self.assertEqual(self.client.calls, [])

    def test_exactly_200_characters_is_accepted(self):
        value = "a" * 200
        self.assertEqual(server._clean_param({"q": value}, "q"), value)
        self.assertEqual(server._clean_param({"q": f"  {value}  "}, "q"), value)

    def test_empty_is_still_missing(self):
        status, _, body = self.get("/api/search?q=")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body), {"error": "missing q"})


class TestNotFound(ServerTestCase):
    def assert_json_404(self, path):
        status, headers, body = self.get(path)
        self.assertEqual(status, 404)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["content-length"], str(len(body)))
        self.assertEqual(json.loads(body), {"error": "not found"})

    def test_404_carries_json_body_and_content_type(self):
        for path in ("/missing.html", "/api/nope", "/../server.py",
                     "/%2e%2e/server.py", "/" + "a" * 300):
            with self.subTest(path=path):
                self.assert_json_404(path)

    def test_trailing_slash_returns_404(self):
        for path in ("/index.html/", "/index.html//", "/vendor/", "/a/"):
            with self.subTest(path=path):
                self.assert_json_404(path)

    def test_root_and_index_still_serve(self):
        for path in ("/", "/index.html"):
            with self.subTest(path=path):
                status, _, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(body, b"<p>index</p>")


class TestNoPath(ServerTestCase):
    def setUp(self):
        server._no_chain_cache.clear()
        self.addCleanup(server._no_chain_cache.clear)

    def test_no_path_returns_404_fresh_and_from_the_no_chain_cache(self):
        path = "/api/chain?from=Alpha&to=Omega"
        calls_before = len(self.client.calls)
        fresh = self.get(path)
        calls_after_fresh = len(self.client.calls)
        self.assertGreater(calls_after_fresh, calls_before)
        self.assertEqual(len(server._no_chain_cache), 1)
        cached = self.get(path)
        self.assertEqual(len(self.client.calls), calls_after_fresh)
        for status, headers, body in (fresh, cached):
            self.assertEqual(status, 404)
            self.assertEqual(headers["content-type"], "application/json")
            self.assertEqual(json.loads(body), {"error": NO_PATH})

    def test_message_has_no_em_dash(self):
        self.assertEqual(server.NO_PATH_MSG, NO_PATH)
        self.assertNotIn("—", server.NO_PATH_MSG)
        self.assertNotIn("— these artists",
                         Path(server.__file__).read_text(encoding="utf-8"))


class TestCachePruning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        self.client = make_client(self.cache, empty_similar)

    def entry(self, name, age, data, method="artist.getSimilar"):
        path = self.cache / method / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched": time.time() - age, "data": data}))
        return path

    def raw(self, name, age, text="{not json"):
        path = self.cache / "artist.getInfo" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def test_prune_deletes_expired_and_keeps_files_younger_than_their_ttl(self):
        keep = [
            self.entry("fresh.json", 0, {"x": 1}),
            self.entry("young.json", 7 * DAY - HOUR, {"x": 1}),
            self.entry("young-missing.json", 23 * HOUR, {}),
            self.raw("young-corrupt.json", 6 * DAY),
            self.raw("inflight.json.tmp", 0),
        ]
        drop = [
            self.entry("old.json", 7 * DAY + HOUR, {"x": 1}),
            self.entry("old-missing.json", 25 * HOUR, {}),
            self.entry("old-search.json", 30 * DAY, {"x": 1}, method="artist.search"),
            self.raw("old-corrupt.json", 8 * DAY),
            self.raw("stale.json.tmp", 8 * DAY),
        ]
        self.assertEqual(self.client.prune_cache(), len(drop))
        for path in keep:
            self.assertTrue(path.exists(), path.name)
        for path in drop:
            self.assertFalse(path.exists(), path.name)
        self.assertEqual(self.client.prune_cache(), 0)

    def test_prune_ttls_match_the_read_path(self):
        self.assertEqual(lastfm.CACHE_TTL, 7 * DAY)
        self.assertEqual(lastfm.NOT_FOUND_TTL, DAY)

    def test_prune_never_raises(self):
        missing = make_client(self.cache / "does-not-exist", empty_similar)
        self.assertEqual(missing.prune_cache(), 0)
        old = self.entry("old.json", 8 * DAY, {"x": 1})
        (self.cache / "artist.getSimilar" / "dir.json").mkdir()
        with patch.object(Path, "unlink", side_effect=PermissionError(13, "denied")):
            self.assertEqual(self.client.prune_cache(), 0)
        self.assertTrue(old.exists())
        with patch.object(Path, "glob", side_effect=OSError(5, "io")), \
                self.assertLogs(level="WARNING"):
            self.assertEqual(self.client.prune_cache(), 0)

    def test_pruner_thread_is_daemon_runs_at_start_and_on_the_interval(self):
        first = self.entry("old.json", 8 * DAY, {"x": 1})
        stop = threading.Event()
        thread = server.start_cache_pruner(self.client, interval=0.05, stop=stop)
        self.addCleanup(thread.join, 5)
        self.addCleanup(stop.set)
        self.assertTrue(thread.daemon)

        def gone(path):
            deadline = time.monotonic() + 5
            while path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            return not path.exists()

        self.assertTrue(gone(first))
        second = self.entry("old-2.json", 8 * DAY, {"x": 1})
        young = self.entry("young.json", HOUR, {"x": 1})
        self.assertTrue(gone(second))
        self.assertTrue(young.exists())
        self.assertTrue(thread.is_alive())

    def test_pruner_loop_survives_a_raising_prune(self):
        calls = []

        class Boom:
            def prune_cache(self):
                calls.append(1)
                raise RuntimeError("boom")

        stop = threading.Event()
        with self.assertLogs(level="WARNING"):
            thread = server.start_cache_pruner(Boom(), interval=0.02, stop=stop)
            deadline = time.monotonic() + 5
            while len(calls) < 3 and time.monotonic() < deadline:
                time.sleep(0.01)
            alive = thread.is_alive()
            stop.set()
            thread.join(5)
        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(alive)
        self.assertFalse(thread.is_alive())

    def test_default_interval_is_24_hours(self):
        self.assertEqual(server._PRUNE_INTERVAL, 24 * HOUR)


if __name__ == "__main__":
    unittest.main()
