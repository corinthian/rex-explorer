"""B4: validators and Cache-Control on static files."""

import os
import socket
import tempfile
import unittest
from email.utils import formatdate
from pathlib import Path
from unittest.mock import patch

from helpers import raw_request, request, running_server, server

MTIME = 1_700_000_000
APP_PATHS = ("/", "/index.html", "/app.js", "/style.css", "/favicon.svg")
VENDOR_PATH = "/vendor/force-graph.min.js"


class TestStaticCaching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        (root / "vendor").mkdir()
        for rel in ("index.html", "app.js", "style.css", "favicon.svg",
                    "vendor/force-graph.min.js"):
            (root / rel).write_text(f"content of {rel}")
            os.utime(root / rel, (MTIME, MTIME))
        patcher = patch.object(server, "STATIC_DIR", root)
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        ctx = running_server()
        cls.port = ctx.__enter__()
        cls.addClassCleanup(ctx.__exit__, None, None, None)

    def get(self, path, headers=None):
        return request(self.port, "GET", path, headers)

    def test_app_files_send_validators_and_no_cache(self):
        for path in APP_PATHS:
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["cache-control"], "no-cache")
                self.assertEqual(headers["last-modified"], formatdate(MTIME, usegmt=True))
                self.assertRegex(headers["etag"], r'^"[0-9a-f]+-[0-9a-f]+"$')
                self.assertTrue(body)

    def test_vendor_files_send_validators_and_long_max_age(self):
        status, headers, body = self.get(VENDOR_PATH)
        self.assertEqual(status, 200)
        self.assertEqual(headers["cache-control"], "public, max-age=2592000")
        self.assertEqual(headers["last-modified"], formatdate(MTIME, usegmt=True))
        self.assertRegex(headers["etag"], r'^"[0-9a-f]+-[0-9a-f]+"$')
        self.assertEqual(body, b"content of vendor/force-graph.min.js")

    def test_matching_if_none_match_returns_304_with_empty_body(self):
        for path in ("/", "/app.js", VENDOR_PATH):
            with self.subTest(path=path):
                _, first, _ = self.get(path)
                status, headers, body = self.get(path, {"If-None-Match": first["etag"]})
                self.assertEqual(status, 304)
                self.assertEqual(body, b"")
                self.assertEqual(headers["etag"], first["etag"])
                self.assertEqual(headers["cache-control"], first["cache-control"])

    def test_304_puts_no_body_on_the_wire(self):
        _, first, _ = self.get("/app.js")
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as sock:
            sock.sendall(f"GET /app.js HTTP/1.1\r\nHost: test\r\n"
                         f"If-None-Match: {first['etag']}\r\n"
                         f"Connection: close\r\n\r\n".encode())
            data = b""
            while chunk := sock.recv(65536):
                data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        self.assertTrue(head.startswith(b"HTTP/1.0 304"))
        self.assertEqual(body, b"")

    def test_weak_and_listed_if_none_match_return_304(self):
        _, first, _ = self.get("/app.js")
        for value in (f"W/{first['etag']}", f'"other", {first["etag"]}', "*"):
            with self.subTest(value=value):
                status, _, body = self.get("/app.js", {"If-None-Match": value})
                self.assertEqual(status, 304)
                self.assertEqual(body, b"")

    def test_stale_if_none_match_returns_200(self):
        status, _, body = self.get("/app.js", {"If-None-Match": '"stale"'})
        self.assertEqual(status, 200)
        self.assertEqual(body, b"content of app.js")

    def test_if_modified_since(self):
        current = {"If-Modified-Since": formatdate(MTIME, usegmt=True)}
        older = {"If-Modified-Since": formatdate(MTIME - 60, usegmt=True)}
        status, _, body = self.get("/app.js", current)
        self.assertEqual((status, body), (304, b""))
        status, _, body = self.get("/app.js", older)
        self.assertEqual((status, body), (200, b"content of app.js"))
        status, _, _ = self.get("/app.js", {"If-Modified-Since": "not a date"})
        self.assertEqual(status, 200)

    def test_if_none_match_wins_over_if_modified_since(self):
        status, _, _ = self.get("/app.js", {
            "If-None-Match": '"stale"',
            "If-Modified-Since": formatdate(MTIME, usegmt=True),
        })
        self.assertEqual(status, 200)

    def test_get_without_validators_is_unchanged(self):
        head, body = raw_request(self.port, "GET", "/app.js")
        self.assertTrue(head.startswith("HTTP/1.0 200"))
        self.assertEqual(body, b"content of app.js")


if __name__ == "__main__":
    unittest.main()
