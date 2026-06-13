import unittest
from unittest.mock import patch

from apis.scrapers.base import detect_stat_domains, search_query_from_topic
from apis.stats_context_api import gather_stats_context, get_stats_context_signal


class TestStatsContext(unittest.TestCase):
    def test_detect_nba(self):
        self.assertIn("nba", detect_stat_domains("Knicks vs Celtics playoffs 2026"))

    def test_detect_nfl(self):
        self.assertIn("nfl", detect_stat_domains("Myles Garrett Rams trade impact"))

    def test_inactive_generic_topic(self):
        sig = get_stats_context_signal("Marvel Rivals meta tier list")
        self.assertFalse(sig["active"])

    @patch("apis.stats_context_api.scrape_enabled", return_value=True)
    @patch("apis.stats_context_api.fetch_bref_stats")
    @patch("apis.stats_context_api.fetch_espn_stats")
    def test_gather_merges_lines(self, mock_espn, mock_bref, _enabled):
        mock_bref.return_value = {
            "source": "Basketball Reference",
            "lines": ["Nikola Jokic 2025-26 | 29.8 PPG"],
        }
        mock_espn.return_value = {
            "source": "ESPN API",
            "lines": ["Nikola Jokic (DEN) — PPG: 29.8"],
        }
        ctx = gather_stats_context("Jokic MVP race NBA 2026")
        self.assertGreaterEqual(len(ctx.get("lines") or []), 1)

    def test_search_query_trims_year_noise(self):
        q = search_query_from_topic("Why the Knicks beat the Celtics in 2026 playoffs")
        self.assertNotIn("2026", q)


if __name__ == "__main__":
    unittest.main()
