"""B1: /api/chain is bounded by a wall-clock deadline."""

import inspect
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from helpers import make_client, request, running_server, server

import pathfind
from pathfind import ChainTimeout, find_chain

DELAY = 0.05
DEADLINE = 0.3
ONE_BATCH = 1.0  # generous allowance for the batch in flight at expiry


def slow_disjoint(params):
    """Every artist has three fresh neighbours, so the two sides never meet."""
    time.sleep(DELAY)
    artist = params["artist"]
    return {"similarartists": {"artist": [
        {"name": f"{artist}>{i}", "match": "0.5"} for i in range(3)
    ]}}


class TestFindChainDeadline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = make_client(self.tmp.name, slow_disjoint)

    def test_default_budgets_and_deadline(self):
        sig = inspect.signature(find_chain)
        self.assertEqual(sig.parameters["budgets"].default, (60, 120))
        self.assertEqual(sig.parameters["deadline"].default, 40.0)
        self.assertEqual(pathfind.CHAIN_DEADLINE, 40.0)

    def test_timeout_raised_within_deadline_plus_one_batch(self):
        start = time.monotonic()
        with self.assertRaises(ChainTimeout):
            find_chain(self.client, "Alpha", "Omega", deadline=DEADLINE)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, DEADLINE)
        self.assertLess(elapsed, DEADLINE + ONE_BATCH)
        self.assertLess(len(self.client.calls), 2 * (60 + 120))

    def test_expired_deadline_stops_before_any_fetch(self):
        with self.assertRaises(ChainTimeout):
            find_chain(self.client, "Alpha", "Omega", deadline=0)
        self.assertEqual(self.client.calls, [])

    def test_fast_search_still_returns_none_without_timeout(self):
        client = make_client(self.tmp.name + "/fast",
                             lambda p: {"similarartists": {"artist": []}})
        self.assertIsNone(find_chain(client, "Alpha", "Omega", deadline=DEADLINE))


class TestChainHandlerTimeout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = make_client(self.tmp.name, slow_disjoint)
        server._no_chain_cache.clear()
        self.addCleanup(server._no_chain_cache.clear)

    def test_timeout_returns_504_json_without_no_chain_write(self):
        with patch.object(server, "CHAIN_DEADLINE", DEADLINE), \
                running_server(self.client) as port:
            start = time.monotonic()
            status, headers, body = request(port, "GET", "/api/chain?from=Alpha&to=Omega")
            elapsed = time.monotonic() - start
        self.assertEqual(status, 504)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(json.loads(body), {
            "error": "That search took too long. Try a closer pair of artists."
        })
        self.assertLess(elapsed, DEADLINE + ONE_BATCH)
        self.assertEqual(server._no_chain_cache, {})

    def test_chain_slot_released_after_timeout(self):
        with patch.object(server, "CHAIN_DEADLINE", DEADLINE), \
                running_server(self.client) as port:
            for _ in range(3):
                status, _, _ = request(port, "GET", "/api/chain?from=Alpha&to=Omega")
                self.assertEqual(status, 504)
        self.assertTrue(server._chain_slots.acquire(blocking=False))
        self.assertTrue(server._chain_slots.acquire(blocking=False))
        server._chain_slots.release()
        server._chain_slots.release()

    def test_handler_passes_40s_deadline_by_default(self):
        self.assertEqual(server.CHAIN_DEADLINE, 40.0)
        seen = {}

        def fake_find_chain(client, a, b, **kwargs):
            seen.update(kwargs)
            return None

        with patch.object(server, "find_chain", fake_find_chain), \
                running_server(self.client) as port:
            request(port, "GET", "/api/chain?from=Alpha&to=Omega")
        self.assertEqual(seen, {"deadline": 40.0})


if __name__ == "__main__":
    unittest.main()
