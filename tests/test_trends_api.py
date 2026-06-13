import unittest
from unittest.mock import patch

from apis.trends_api import get_trend_score


class TestTrendsApi(unittest.TestCase):
    @patch.dict("os.environ", {"TRENDS_PROVIDER_ORDER": "wikipedia"}, clear=False)
    @patch("apis.trends_api._trends_from_wikipedia")
    def test_wikipedia_fallback_provider(self, mock_wiki):
        mock_wiki.return_value = {
            "connected": True,
            "active": True,
            "score": 42,
            "status": "ok",
            "data": {},
        }
        result = get_trend_score("Knicks NBA finals")
        self.assertTrue(result["active"])
        self.assertEqual((result.get("data") or {}).get("provider"), "wikipedia")

    @patch.dict("os.environ", {"TRENDS_PROVIDER_ORDER": "serpapi,wikipedia"}, clear=False)
    @patch("apis.trends_api._trends_from_serpapi")
    @patch("apis.trends_api._trends_from_wikipedia")
    def test_serpapi_preferred_over_wikipedia(self, mock_wiki, mock_serp):
        mock_serp.return_value = {
            "connected": True,
            "active": True,
            "score": 55,
            "status": "ok",
            "data": {},
        }
        mock_wiki.return_value = {
            "connected": True,
            "active": True,
            "score": 30,
            "status": "ok",
            "data": {},
        }
        result = get_trend_score("GTA VI")
        self.assertEqual((result.get("data") or {}).get("provider"), "serpapi")
        mock_wiki.assert_not_called()


if __name__ == "__main__":
    unittest.main()
