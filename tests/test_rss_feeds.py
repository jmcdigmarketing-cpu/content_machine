"""RSS parsing — publish-date extraction (feeds best_bet freshness/recency)."""

import unittest

from apis.rss_feeds import _parse_feed_xml


class TestParseFeedXml(unittest.TestCase):
    def test_extracts_pubdate_rss(self):
        xml = (
            "<rss><channel>"
            "<item><title>Hello</title><link>http://x</link>"
            "<pubDate>Tue, 08 Jul 2026 14:03:00 GMT</pubDate></item>"
            "</channel></rss>"
        )
        items = _parse_feed_xml(xml)
        self.assertEqual(items[0]["title"], "Hello")
        self.assertEqual(items[0]["published"], "Tue, 08 Jul 2026 14:03:00 GMT")

    def test_extracts_published_atom(self):
        xml = (
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><title>Atom item</title><link href="http://y"/>'
            "<published>2026-07-08T14:03:00Z</published></entry>"
            "</feed>"
        )
        items = _parse_feed_xml(xml)
        self.assertEqual(items[0]["title"], "Atom item")
        self.assertEqual(items[0]["published"], "2026-07-08T14:03:00Z")

    def test_missing_date_is_empty_string(self):
        xml = "<rss><channel><item><title>No date</title></item></channel></rss>"
        items = _parse_feed_xml(xml)
        self.assertEqual(items[0]["published"], "")


if __name__ == "__main__":
    unittest.main()
