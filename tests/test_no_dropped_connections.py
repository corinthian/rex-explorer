"""B2: no request may end in a traceback and a dropped connection."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import request, running_server, server

SECRET = "secretquery"


class TestStaticOSError(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        (Path(self.tmp.name) / "index.html").write_text("<p>hi</p>")
        patcher = patch.object(server, "STATIC_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_300_character_path_returns_404(self):
        with running_server() as port:
            status, _, _ = request(port, "GET", "/" + "a" * 300)
        self.assertEqual(status, 404)

    def test_is_file_oserror_returns_404(self):
        with patch.object(Path, "is_file", side_effect=OSError(63, "File name too long")), \
                running_server() as port:
            status, _, _ = request(port, "GET", "/index.html")
        self.assertEqual(status, 404)

    def test_read_bytes_oserror_returns_404(self):
        with patch.object(Path, "read_bytes", side_effect=PermissionError(13, "denied")), \
                running_server() as port:
            status, _, _ = request(port, "GET", "/index.html")
        self.assertEqual(status, 404)


class TestTopLevelHandler(unittest.TestCase):
    def _boom(self, exc):
        def handler(self_, params):
            raise exc
        return handler

    def test_keyerror_returns_json_500_and_logs_no_query(self):
        with patch.object(server.Handler, "_handle_search", self._boom(KeyError(SECRET))), \
                self.assertLogs(level="INFO") as logs, \
                running_server() as port:
            status, headers, body = request(port, "GET", f"/api/search?q={SECRET}")
        self.assertEqual(status, 500)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(json.loads(body), {"error": "internal error"})
        errors = [line for line in logs.output if line.startswith("ERROR")]
        self.assertEqual(len(errors), 1)
        self.assertIn("KeyError", errors[0])
        self.assertIn("/api/search", errors[0])
        for line in logs.output:
            self.assertNotIn(SECRET, line)
            self.assertNotIn("?", line)

    def test_broken_client_socket_does_not_raise_again(self):
        with patch.object(server.Handler, "_handle_search", self._boom(BrokenPipeError())), \
                patch("socketserver.BaseServer.handle_error") as handle_error, \
                running_server() as port:
            try:
                request(port, "GET", "/api/search?q=x")
            except Exception:
                pass
        handle_error.assert_not_called()

    def test_too_long_param_with_broken_socket_does_not_raise_again(self):
        def broken_json(self_, data, status=200, headers=None):
            raise BrokenPipeError()

        with patch.object(server.Handler, "_json", broken_json), \
                patch("socketserver.BaseServer.handle_error") as handle_error, \
                running_server() as port:
            try:
                request(port, "GET", "/api/search?q=" + "a" * 201)
            except Exception:
                pass
        handle_error.assert_not_called()

    def test_failed_500_write_does_not_raise_again(self):
        def broken_json(self_, data, status=200):
            raise BrokenPipeError()

        with patch.object(server.Handler, "_handle_search", self._boom(KeyError("x"))), \
                patch.object(server.Handler, "_json", broken_json), \
                patch("socketserver.BaseServer.handle_error") as handle_error, \
                self.assertLogs(level="ERROR"), \
                running_server() as port:
            try:
                request(port, "GET", "/api/search?q=x")
            except Exception:
                pass
        handle_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
