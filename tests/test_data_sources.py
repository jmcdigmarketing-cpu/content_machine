import unittest

from config.data_sources import domain_rss_feeds, rss_feeds_for_topic


class TestDataSources(unittest.TestCase):
    def test_nba_domain_feeds(self):
        feeds = domain_rss_feeds("nba")
        urls = [f["url"] for f in feeds]
        self.assertTrue(any("espn" in u for u in urls))

    def test_topic_merges_channel_and_domain(self):
        feeds = rss_feeds_for_topic("NBA Finals Knicks", "tapin")
        self.assertGreater(len(feeds), 3)


if __name__ == "__main__":
    unittest.main()
