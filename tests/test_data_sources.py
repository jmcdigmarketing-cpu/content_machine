import json
import unittest
from pathlib import Path

from config.data_sources import _feed_matches_domain, domain_rss_feeds, rss_feeds_for_topic


class TestDataSources(unittest.TestCase):
    def test_nba_domain_feeds(self):
        # Asserts the contract (the domain resolves to usable feeds), not a vendor.
        # This previously pinned "espn", which kept passing after ESPN's RSS went dead
        # (202 with an empty body) — a green test over a source returning nothing.
        # Liveness is `ops feeds` / tests/test_feed_health.py; this is shape only.
        feeds = domain_rss_feeds("nba")
        self.assertGreaterEqual(len(feeds), 2)
        for feed in feeds:
            self.assertTrue(feed.get("url", "").startswith("http"))
            self.assertTrue(feed.get("name"))

    def test_topic_merges_channel_and_domain(self):
        feeds = rss_feeds_for_topic("NBA Finals Knicks", "tapin")
        self.assertGreater(len(feeds), 3)


class TestFeedMatchesDomain(unittest.TestCase):
    def test_untagged_feed_is_universal(self):
        self.assertTrue(_feed_matches_domain({"name": "X", "url": "u"}, "gaming"))

    def test_tagged_feed_matches_only_its_domains(self):
        feed = {"name": "X", "url": "u", "domains": ["gaming"]}
        self.assertTrue(_feed_matches_domain(feed, "gaming"))
        self.assertFalse(_feed_matches_domain(feed, "ufc"))

    def test_ufc_mma_equivalence(self):
        mma_feed = {"name": "X", "url": "u", "domains": ["mma"]}
        self.assertTrue(_feed_matches_domain(mma_feed, "ufc"))


class TestRssDomainRouting(unittest.TestCase):
    def test_gaming_topic_excludes_sports_and_mma_feeds(self):
        names = {f["name"] for f in rss_feeds_for_topic("Marvel Rivals new update", "tapin")}
        self.assertNotIn("BBC Sport", names)  # the soccer bleed from the runs
        self.assertNotIn("MMA Fighting", names)
        self.assertIn("IGN", names)

    def test_ufc_topic_excludes_gaming_feeds(self):
        names = {f["name"] for f in rss_feeds_for_topic("UFC 320 Topuria title defense", "tapin")}
        self.assertNotIn("IGN", names)
        self.assertIn("MMA Fighting", names)


class TestShippedRssNoSherdog(unittest.TestCase):
    """Sherdog's RSS 403s; doctor FAILs feeds. Dropped from shipped config, not a key."""

    def test_data_sources_and_tapin_seo_have_no_sherdog_url(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ("config/data_sources.json", "config/seo/tapin.json"):
            blob = json.loads((root / rel).read_text(encoding="utf-8"))
            for url in _json_urls(blob):
                self.assertNotIn(
                    "sherdog.com",
                    url.lower(),
                    f"{rel} still points at Sherdog: {url}",
                )


def _json_urls(obj: object) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        url = obj.get("url")
        if isinstance(url, str):
            found.append(url)
        for val in obj.values():
            found.extend(_json_urls(val))
    elif isinstance(obj, list):
        for val in obj:
            found.extend(_json_urls(val))
    return found


if __name__ == "__main__":
    unittest.main()
