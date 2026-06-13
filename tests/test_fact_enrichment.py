import unittest
from unittest.mock import patch

from core.fact_enrichment import _fact_line_count, _search_query, enrich_facts


class TestFactEnrichment(unittest.TestCase):
    def test_search_query_uses_anchor(self):
        self.assertEqual(
            _search_query(
                "Marvel Rivals Update: Game-Changing Patch",
                "Marvel rivals update",
            ),
            "Marvel Rivals",
        )

    def test_fact_line_count(self):
        facts = "- RAWG: Marvel Rivals\n- YouTube: Cyclops trailer"
        self.assertEqual(_fact_line_count(facts), 2)

    @patch("core.fact_enrichment._fetch_rawg_lines", return_value=["Marvel Rivals — released 2024"])
    @patch("core.fact_enrichment._fetch_news_lines", return_value=[])
    @patch("core.fact_enrichment._fetch_youtube_lines", return_value=["- YouTube: Cyclops patch"])
    @patch("core.fact_enrichment._fetch_rss_lines", return_value=[])
    @patch("core.fact_enrichment._llm_extract_facts", return_value=[])
    def test_enrich_adds_api_lines_when_base_thin(self, *_mocks):
        signals = {
            "blog_rss": {
                "connected": True,
                "active": False,
                "data": {},
            }
        }
        out = enrich_facts(
            "Marvel Rivals patch",
            signals,
            channel_id="tapin",
            seed_topic="Marvel rivals update",
        )
        self.assertIn("Game database", out)
        self.assertIn("YouTube", out)


if __name__ == "__main__":
    unittest.main()
