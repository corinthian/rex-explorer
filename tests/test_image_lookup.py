"""B6: image misses expire, hits do not, and a non-owner wait is bounded."""

import json
import threading
import time
import unittest
from unittest.mock import patch

from helpers import request, running_server, server

URL = "https://upload.wikimedia.org/x.jpg"


class ImageTestCase(unittest.TestCase):
    def setUp(self):
        server._image_cache.clear()
        server._image_inflight.clear()
        self.addCleanup(server._image_cache.clear)
        self.addCleanup(server._image_inflight.clear)
        self.fetches = []

    def fetcher(self, result):
        def fetch(name):
            self.fetches.append(name)
            return result
        return fetch

    def get(self, port, name="Radiohead"):
        status, _, body = request(port, "GET", f"/api/image?name={name}")
        self.assertEqual(status, 200)
        return json.loads(body)

    def age_entry(self, name, seconds):
        url, stored = server._image_cache[name]
        server._image_cache[name] = (url, stored - seconds)


class TestImageCacheTtl(ImageTestCase):
    def test_none_entry_is_retried_after_one_hour(self):
        with running_server(fetch_image=self.fetcher(None)) as port:
            self.assertEqual(self.get(port), {"url": None})
            self.assertEqual(self.get(port), {"url": None})
            self.assertEqual(len(self.fetches), 1)
            self.age_entry("Radiohead", 3599)
            self.assertEqual(self.get(port), {"url": None})
            self.assertEqual(len(self.fetches), 1)
            self.age_entry("Radiohead", 2)
            self.assertEqual(self.get(port), {"url": None})
            self.assertEqual(len(self.fetches), 2)

    def test_retry_after_ttl_can_find_a_url(self):
        with running_server(fetch_image=self.fetcher(None)) as port:
            self.get(port)
            self.age_entry("Radiohead", 3601)
        with running_server(fetch_image=self.fetcher(URL)) as port:
            self.assertEqual(self.get(port), {"url": URL})

    def test_url_entry_is_never_retried(self):
        with running_server(fetch_image=self.fetcher(URL)) as port:
            self.assertEqual(self.get(port), {"url": URL})
            self.age_entry("Radiohead", 365 * 86400)
            self.assertEqual(self.get(port), {"url": URL})
        self.assertEqual(len(self.fetches), 1)

    def test_default_ttl_and_wait(self):
        self.assertEqual(server._IMAGE_NONE_TTL, 3600)
        self.assertEqual(server._IMAGE_WAIT_TIMEOUT, 35)


class TestNonOwnerWait(ImageTestCase):
    def test_non_owner_times_out_cleanly_without_caching(self):
        started = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def slow_fetch(name):
            self.fetches.append(name)
            started.set()
            release.wait(10)
            return URL

        owner_result = {}

        with patch.object(server, "_IMAGE_WAIT_TIMEOUT", 0.2), \
                patch("socketserver.BaseServer.handle_error") as handle_error, \
                running_server(fetch_image=slow_fetch) as port:
            owner = threading.Thread(
                target=lambda: owner_result.update(self.get(port)))
            owner.start()
            self.assertTrue(started.wait(5))

            start = time.monotonic()
            self.assertEqual(self.get(port), {"url": None})
            elapsed = time.monotonic() - start
            self.assertGreaterEqual(elapsed, 0.2)
            self.assertLess(elapsed, 2.0)
            self.assertNotIn("Radiohead", server._image_cache)
            self.assertIn("Radiohead", server._image_inflight)

            release.set()
            owner.join(5)
            self.assertEqual(owner_result, {"url": URL})
            self.assertEqual(self.get(port), {"url": URL})
        handle_error.assert_not_called()
        self.assertEqual(len(self.fetches), 1)
        self.assertEqual(server._image_inflight, {})

    def test_non_owner_gets_result_when_owner_finishes_in_time(self):
        started = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def slow_fetch(name):
            self.fetches.append(name)
            started.set()
            release.wait(10)
            return URL

        results = []
        with running_server(fetch_image=slow_fetch) as port:
            threads = [threading.Thread(target=lambda: results.append(self.get(port)))
                       for _ in range(2)]
            threads[0].start()
            self.assertTrue(started.wait(5))
            threads[1].start()
            time.sleep(0.1)
            release.set()
            for t in threads:
                t.join(5)
        self.assertEqual(results, [{"url": URL}, {"url": URL}])
        self.assertEqual(len(self.fetches), 1)


if __name__ == "__main__":
    unittest.main()
