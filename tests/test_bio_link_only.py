"""D2: a bio that is only the "Read more on Last.fm" link becomes an
empty string; a real bio ending with that link text is unchanged."""

import tempfile
import unittest

from helpers import make_client

LINK = '<a href="https://www.last.fm/music/Riley!">Read more on Last.fm</a>'
REAL = "Riley! is a band from Ohio &amp; beyond."


def info_with_bio(summary):
    return lambda params: {"artist": {"name": "Riley!", "bio": {"summary": summary}}}


class TestBioLinkOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def bio(self, summary):
        client = make_client(self.tmp.name, info_with_bio(summary))
        return client.artist_info(summary)["bio_summary"]

    def test_link_only_bio_becomes_empty_string(self):
        for summary in (f" {LINK}", LINK, f"\n  {LINK}\n", f"<br> {LINK} "):
            with self.subTest(summary=summary):
                self.assertEqual(self.bio(summary), "")

    def test_real_bio_ending_with_the_link_text_is_unchanged(self):
        self.assertEqual(
            self.bio(f"{REAL} {LINK}"),
            "Riley! is a band from Ohio & beyond. Read more on Last.fm")

    def test_bio_without_the_link_is_unchanged(self):
        self.assertEqual(self.bio(REAL), "Riley! is a band from Ohio & beyond.")

    def test_missing_bio_stays_empty(self):
        self.assertEqual(self.bio(""), "")


if __name__ == "__main__":
    unittest.main()
