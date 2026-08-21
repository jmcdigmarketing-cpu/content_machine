import unittest
from unittest.mock import patch

from apis.wikipedia_pageviews_api import get_wikipedia_pageviews_signal


class TestWikipediaPageviews(unittest.TestCase):
    def test_disabled(self):
        with patch("apis.wikipedia_pageviews_api._WIKI_ENABLED", False):
            sig = get_wikipedia_pageviews_signal("Marvel Rivals")
        self.assertFalse(sig["connected"])

    @patch("apis.wikipedia_pageviews_api.get_cached", return_value=None)
    @patch("apis.wikipedia_pageviews_api.set_cache")
    @patch("apis.wikipedia_pageviews_api._fetch_pageviews")
    def test_spike_active(self, mock_fetch, _set_cache, _cached):
        mock_fetch.return_value = {
            "article": "Marvel_Rivals",
            "views": [100, 120, 130, 400, 500, 600, 620, 640],
        }
        sig = get_wikipedia_pageviews_signal("Marvel Rivals")
        self.assertTrue(sig["connected"])
        self.assertTrue(sig["active"])
        self.assertGreater(sig["score"], 20)

    @patch("apis.wikipedia_pageviews_api.get_cached", return_value=None)
    @patch("apis.wikipedia_pageviews_api.set_cache")
    @patch("apis.wikipedia_pageviews_api._fetch_pageviews", return_value=None)
    def test_no_article_match(self, _fetch, _set_cache, _cached):
        sig = get_wikipedia_pageviews_signal("xyznonexistent123")
        self.assertTrue(sig["connected"])
        self.assertFalse(sig["active"])
        _set_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main()
