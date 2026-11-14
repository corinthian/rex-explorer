"""B3: spelling variants, small limits and missing artists share one
Last.fm call; not-found entries live 24 hours, normal entries 7 days."""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import make_client

from lastfm import LastFMError

HOUR = 3600
DAY = 24 * HOUR


def similar_payload(params):
    return {"similarartists": {"artist": [
        {"name": f"Artist {i}", "match": str(1 - i / 100)} for i in range(50)
    ]}}


def not_found(params):
    return {"error": 6, "message": "The artist you supplied could not be found"}


def age_cache(cache_dir, seconds):
    for path in Path(cache_dir).glob("*/*.json"):
        entry = json.loads(path.read_text())
        entry["fetched"] -= seconds
        path.write_text(json.dumps(entry))


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)


class TestSharedCalls(CacheTestCase):
    def test_case_variants_make_one_network_call(self):
        client = make_client(self.tmp.name, similar_payload)
        results = [client.similar_artists(name, limit=5)
                   for name in ("Radiohead", "radiohead", "RADIOHEAD", "  Radiohead ")]
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.stats["network"], 1)
        self.assertTrue(all(r == results[0] for r in results))

    def test_upstream_request_keeps_original_spelling(self):
        client = make_client(self.tmp.name, similar_payload)
        client.similar_artists("RADIOHEAD", limit=5)
        self.assertEqual(client.calls[0]["artist"], "RADIOHEAD")

    def test_case_variants_share_search_and_info_calls(self):
        client = make_client(self.tmp.name, lambda p: {
            "results": {"artistmatches": {"artist": [{"name": "Radiohead", "listeners": "5"}]}},
            "artist": {"name": "Radiohead"},
        })
        for name in ("Radiohead", "radiohead", "RADIOHEAD"):
            client.artist_search(name, limit=30)
            client.artist_info(name)
        self.assertEqual(len(client.calls), 2)

    def test_limits_5_and_50_share_one_call(self):
        client = make_client(self.tmp.name, similar_payload)
        five = client.similar_artists("Radiohead", limit=5)
        fifty = client.similar_artists("Radiohead", limit=50)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["limit"], 50)
        self.assertEqual(len(five), 5)
        self.assertEqual(len(fifty), 50)
        self.assertEqual(five, fifty[:5])

    def test_limit_over_50_is_requested_as_asked(self):
        client = make_client(self.tmp.name, similar_payload)
        client.similar_artists("Radiohead", limit=100)
        self.assertEqual(client.calls[0]["limit"], 100)

    def test_missing_artist_twice_makes_one_call(self):
        client = make_client(self.tmp.name, not_found)
        self.assertEqual(client.similar_artists("Nobody At All", limit=5), [])
        self.assertEqual(client.similar_artists("nobody at all", limit=50), [])
        self.assertEqual(len(client.calls), 1)

    def test_other_errors_are_never_cached(self):
        client = make_client(self.tmp.name, lambda p: {"error": 29, "message": "Rate limit"})
        for _ in range(2):
            with self.assertLogs(level="WARNING"):
                with self.assertRaises(LastFMError):
                    client.similar_artists("Radiohead", limit=5)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(list(Path(self.tmp.name).glob("*/*")), [])


class TestTtl(CacheTestCase):
    def test_not_found_entry_expires_after_24_hours(self):
        client = make_client(self.tmp.name, not_found)
        client.similar_artists("Nobody At All", limit=5)
        age_cache(self.tmp.name, 23 * HOUR)
        client.similar_artists("Nobody At All", limit=5)
        self.assertEqual(len(client.calls), 1)
        age_cache(self.tmp.name, 2 * HOUR)
        client.similar_artists("Nobody At All", limit=5)
        self.assertEqual(len(client.calls), 2)

    def test_normal_entry_keeps_7_days(self):
        client = make_client(self.tmp.name, similar_payload)
        client.similar_artists("Radiohead", limit=5)
        age_cache(self.tmp.name, 6 * DAY + 23 * HOUR)
        client.similar_artists("Radiohead", limit=5)
        self.assertEqual(len(client.calls), 1)
        age_cache(self.tmp.name, 2 * HOUR)
        client.similar_artists("Radiohead", limit=5)
        self.assertEqual(len(client.calls), 2)


if __name__ == "__main__":
    unittest.main()
