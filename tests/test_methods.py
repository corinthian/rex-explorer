"""B5: HEAD mirrors GET without a body, other methods get 405, and every
request is logged exactly once."""

import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import make_client, raw_request, request, running_server, server

INDEX = "<p>index</p>"


def head_fields(head):
    lines = head.split("\r\n")
    fields = {}
    for line in lines[1:]:
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    return int(lines[0].split()[1]), fields


class MethodsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        (root / "static").mkdir()
        (root / "static" / "index.html").write_text(INDEX)
        patcher = patch.object(server, "STATIC_DIR", root / "static")
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        cls.client = make_client(root / "cache", lambda p: {
            "results": {"artistmatches": {"artist": [
                {"name": "Radiohead", "listeners": "100"}]}}})
        ctx = running_server(cls.client)
        cls.port = ctx.__enter__()
        cls.addClassCleanup(ctx.__exit__, None, None, None)


class TestHead(MethodsTestCase):
    def assert_head_mirrors_get(self, path, expected_status):
        get_head, get_body = raw_request(self.port, "GET", path)
        head_head, head_body = raw_request(self.port, "HEAD", path)
        get_status, get_fields = head_fields(get_head)
        head_status, head_fields_ = head_fields(head_head)
        self.assertEqual(get_status, expected_status)
        self.assertEqual(head_status, expected_status)
        self.assertEqual(head_body, b"")
        self.assertTrue(get_body)
        self.assertEqual(head_fields_["content-length"], str(len(get_body)))
        self.assertEqual(head_fields_["content-length"], get_fields["content-length"])
        self.assertEqual(head_fields_["content-type"], get_fields["content-type"])

    def test_head_root_is_200_with_no_body(self):
        self.assert_head_mirrors_get("/", 200)

    def test_head_api_search_without_q_is_400_with_no_body(self):
        self.assert_head_mirrors_get("/api/search", 400)

    def test_head_api_search_with_q_is_200_with_no_body(self):
        self.assert_head_mirrors_get("/api/search?q=radiohead", 200)

    def test_head_favicon_is_200_with_no_body(self):
        self.assert_head_mirrors_get("/favicon.ico", 200)


class TestOtherMethods(MethodsTestCase):
    def test_write_methods_return_405_json_with_allow(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            for path in ("/", "/api/search?q=radiohead"):
                with self.subTest(method=method, path=path):
                    status, headers, body = request(self.port, method, path)
                    self.assertEqual(status, 405)
                    self.assertEqual(headers["allow"], "GET, HEAD")
                    self.assertEqual(headers["content-type"], "application/json")
                    self.assertEqual(json.loads(body), {"error": "method not allowed"})


class TestLoggedOnce(MethodsTestCase):
    def request_lines(self, send):
        with self.assertLogs(level="INFO") as logs:
            send()
        return [r.getMessage() for r in logs.records
                if r.getMessage().startswith("request ")]

    def test_each_request_logs_exactly_one_line(self):
        cases = [
            ("GET", "/", "request GET /"),
            ("HEAD", "/", "request HEAD /"),
            ("GET", "/missing.html", "request GET /missing.html"),
            ("GET", "/api/search", "request GET /api/search"),
            ("HEAD", "/api/search?q=radiohead", "request HEAD /api/search"),
            ("POST", "/api/search?q=radiohead", "request POST /api/search"),
            ("OPTIONS", "/", "request OPTIONS /"),
            ("FOO", "/", "request FOO /"),
            ("FOO", "/api/search?q=radiohead", "request FOO /api/search"),
        ]
        for method, path, expected in cases:
            with self.subTest(method=method, path=path):
                lines = self.request_lines(
                    lambda: request(self.port, method, path))
                self.assertEqual(lines, [expected])

    def test_unknown_method_is_answered_not_dropped(self):
        status, _, _ = request(self.port, "FOO", "/")
        self.assertEqual(status, 501)

    def test_unparseable_request_line_logs_once_and_is_answered(self):
        def send():
            with socket.create_connection(("127.0.0.1", self.port), timeout=10) as sock:
                sock.sendall(b"GET /api/search?q=radiohead HTTP/9.9.9\r\n\r\n")
                data = b""
                while chunk := sock.recv(65536):
                    data += chunk
            self.assertIn(b" 400 ", data.split(b"\r\n", 1)[0])

        with patch("socketserver.BaseServer.handle_error") as handle_error:
            lines = self.request_lines(send)
        handle_error.assert_not_called()
        self.assertEqual(lines, ["request - "])


if __name__ == "__main__":
    unittest.main()
