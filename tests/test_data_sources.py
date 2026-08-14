import unittest

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


if __name__ == "__main__":
    unittest.main()
