"""Tests for the provider-agnostic web search signal and its fact rendering."""

import unittest
from unittest.mock import MagicMock, patch

from apis import web_search_api as ws
from apis.signal_contract import STATUS_NO_KEY
from core.signal_facts import format_signal_facts


class TestProviderSelection(unittest.TestCase):
    def test_no_key_is_inactive(self):
        with patch.dict(
            "os.environ",
            {"TAVILY_API_KEY": "", "BRAVE_SEARCH_API_KEY": "", "BRAVE_API_KEY": ""},
            clear=False,
        ):
            sig = ws.get_web_search_signal("anything")
        self.assertFalse(sig["active"])
        self.assertEqual(sig["status"], STATUS_NO_KEY)

    def test_tavily_preferred_over_brave(self):
        with patch.dict(
            "os.environ", {"TAVILY_API_KEY": "tk", "BRAVE_SEARCH_API_KEY": "bk"}, clear=False
        ):
            self.assertEqual(ws._active_provider(), "tavily")

    def test_brave_when_only_brave(self):
        with patch.dict(
            "os.environ", {"TAVILY_API_KEY": "", "BRAVE_SEARCH_API_KEY": "bk"}, clear=False
        ):
            self.assertEqual(ws._active_provider(), "brave")


class TestTavilyFetch(unittest.TestCase):
    @patch("apis.web_search_api.get_cached", return_value=None)
    @patch("apis.web_search_api.set_cache")
    @patch("apis.web_search_api.requests.post")
    def test_tavily_active_signal(self, mock_post, _set, _get):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "answer": "Islam Makhachev is the current lightweight champion.",
                "results": [
                    {"title": "UFC results", "content": "Makhachev defended the belt.", "url": "u"},
                    {"title": "Rankings", "content": "Updated divisional rankings.", "url": "u2"},
                ],
            },
        )
        with patch.dict("os.environ", {"TAVILY_API_KEY": "tk", "BRAVE_SEARCH_API_KEY": ""}):
            sig = ws.get_web_search_signal("UFC lightweight champion 2026")
        self.assertTrue(sig["active"])
        self.assertEqual(sig["data"]["provider"], "tavily")
        self.assertEqual(len(sig["data"]["results"]), 2)
        self.assertIn("Makhachev", sig["data"]["answer"])

    @patch("apis.web_search_api.get_cached", return_value=None)
    @patch("apis.web_search_api.set_cache")
    @patch("apis.web_search_api.requests.post")
    def test_tavily_quota_error_inactive(self, mock_post, _set, _get):
        mock_post.return_value = MagicMock(status_code=402, text="payment required")
        with patch.dict("os.environ", {"TAVILY_API_KEY": "tk", "BRAVE_SEARCH_API_KEY": ""}):
            sig = ws.get_web_search_signal("topic")
        self.assertFalse(sig["active"])
        self.assertEqual(sig["status"], "quota_exceeded")


class TestBraveFetch(unittest.TestCase):
    @patch("apis.web_search_api.get_cached", return_value=None)
    @patch("apis.web_search_api.set_cache")
    @patch("apis.web_search_api.requests.get")
    def test_brave_active_signal(self, mock_get, _set, _get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "web": {
                    "results": [
                        {"title": "Game patch", "description": "New season launched.", "url": "u"},
                    ]
                }
            },
        )
        with patch.dict("os.environ", {"TAVILY_API_KEY": "", "BRAVE_SEARCH_API_KEY": "bk"}):
            sig = ws.get_web_search_signal("Marvel Rivals new season")
        self.assertTrue(sig["active"])
        self.assertEqual(sig["data"]["provider"], "brave")
        self.assertEqual(sig["data"]["results"][0]["title"], "Game patch")


class TestWebSearchFactRendering(unittest.TestCase):
    def test_renders_as_verified_block(self):
        signals = {
            "web_search": {
                "connected": True,
                "active": True,
                "data": {
                    "provider": "tavily",
                    "answer": "Current champ is X.",
                    "results": [{"title": "Result A", "snippet": "Detail A", "url": "u"}],
                },
            }
        }
        facts = format_signal_facts(signals)
        self.assertIn("Live web search (tavily)", facts)
        self.assertIn("Current champ is X.", facts)
        self.assertIn("Result A", facts)


if __name__ == "__main__":
    unittest.main()
