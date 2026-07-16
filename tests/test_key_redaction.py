"""Regression test for SEC-01: the Last.fm API key must never leak via
LastFMError messages, warning logs, or a stray logging.exception() call
that would print the unredacted upstream URL from an exception's
__cause__ chain."""

import ast
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from lastfm import LastFM, LastFMError  # noqa: E402

SENTINEL_KEY = "deadbeefcafebabe0123456789abcde"


class TestKeyRedaction(unittest.TestCase):
    def setUp(self):
        self.client = LastFM(SENTINEL_KEY, cache_dir=Path("/tmp/rex-test-cache"))

    def test_transport_exception_redacts_key(self):
        url = f"https://ws.audioscrobbler.com/2.0/?api_key={SENTINEL_KEY}"
        exc = requests.exceptions.ConnectionError(f"Connection failed for url: {url}")
        with patch.object(self.client._session, "get", side_effect=exc):
            with self.assertLogs(level="WARNING") as log_ctx:
                with self.assertRaises(LastFMError) as err_ctx:
                    self.client.artist_search("radiohead")
        self.assertNotIn(SENTINEL_KEY, str(err_ctx.exception))
        for record in log_ctx.output:
            self.assertNotIn(SENTINEL_KEY, record)

    def test_non_json_response_redacts_key(self):
        fake_resp = Mock()
        fake_resp.url = f"https://ws.audioscrobbler.com/2.0/?api_key={SENTINEL_KEY}"
        fake_resp.status_code = 502
        fake_resp.json.side_effect = json.JSONDecodeError("bad", "doc", 0)
        with patch.object(self.client._session, "get", return_value=fake_resp):
            with self.assertLogs(level="WARNING") as log_ctx:
                with self.assertRaises(LastFMError) as err_ctx:
                    self.client.artist_search("radiohead")
        self.assertNotIn(SENTINEL_KEY, str(err_ctx.exception))
        for record in log_ctx.output:
            self.assertNotIn(SENTINEL_KEY, record)


class TestServerLoggingBoundary(unittest.TestCase):
    """server.py must never call logging.exception() outside _load_api_key:
    the __cause__ chain of a LastFMError still holds the unredacted upstream
    URL, and logging.exception() prints the full chained traceback."""

    def test_no_stray_logging_exception(self):
        server_path = Path(__file__).parent.parent / "server.py"
        tree = ast.parse(server_path.read_text(), filename=str(server_path))

        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for call in ast.walk(node):
                if (isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "exception"
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "logging"
                        and node.name != "_load_api_key"):
                    offenders.append((node.name, call.lineno))

        self.assertEqual(
            offenders, [],
            f"logging.exception() found outside _load_api_key: {offenders}"
        )


if __name__ == "__main__":
    unittest.main()
