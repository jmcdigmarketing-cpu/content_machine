import unittest
from unittest.mock import patch

from core.research_brief import BRIEF_VERSION, build_research_brief


class TestResearchBrief(unittest.TestCase):
    @patch("core.research_brief._USE_LLM", False)
    @patch("analytics.competitor_context.get_competitor_prompt_block", return_value="")
    @patch("apis.stats_context_api.gather_stats_context", return_value={"lines": []})
    @patch("core.research_brief.fetch_rss_context")
    @patch("core.research_brief.get_cached", return_value=None)
    @patch("core.research_brief.set_cache")
    def test_fallback_brief(self, _set, _get, mock_rss, _stats, _comp):
        mock_rss.return_value = {"headlines": [{"title": "Test headline", "source": "IGN"}]}
        signals = {
            "news": {
                "connected": True,
                "active": True,
                "data": {"headlines": [{"title": "Fighter A vs B"}]},
            }
        }
        brief = build_research_brief("UFC 250 preview", signals, channel_id="tapin")
        self.assertEqual(brief.version, BRIEF_VERSION)
        self.assertIn("UFC 250", brief.narrative)
        block = brief.to_prompt_block()
        self.assertIn("RESEARCH BRIEF", block)


if __name__ == "__main__":
    unittest.main()
