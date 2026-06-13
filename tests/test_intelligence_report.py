import unittest
from unittest.mock import patch

from core.intelligence_report import (
    IntelligenceReport,
    build_intelligence_report,
    intelligence_mode_enabled,
    production_tail_enabled,
    to_markdown,
)
from core.pipeline import DiscoveryResult
from core.research_brief import ResearchBrief


class TestIntelligenceReport(unittest.TestCase):
    def _fake_discovery(self) -> DiscoveryResult:
        signals = {
            "youtube": {
                "connected": True,
                "active": True,
                "score": 72,
                "status": "ok",
            },
            "blog_rss": {
                "connected": True,
                "active": False,
                "score": 0,
                "status": "inactive",
            },
        }
        return DiscoveryResult(
            input_topic="GTA VI multiplayer",
            base_signals=signals,
            evaluated=[
                ("GTA VI multiplayer features", 68.5, signals),
                ("Hidden gems in GTA VI online", 61.2, signals),
            ],
            timings={"signals_and_variants": 1.2, "variant_scoring": 0.4},
            channel_id="tapin",
        )

    def test_build_report_structure(self):
        discovery = self._fake_discovery()
        brief = ResearchBrief(
            topic="GTA VI multiplayer features",
            narrative="Players want concrete multiplayer details.",
            audience_sentiment="Excited but skeptical",
            controversy_score=0.35,
            debate_angles=["Co-op vs competitive"],
            supporting_evidence=["Rockstar delayed launch"],
        )
        with (
            patch(
                "core.intelligence_report.build_research_brief",
                return_value=brief,
            ),
            patch(
                "analytics.competitor_context.list_recent_competitor_titles",
                return_value=[{"channel": "CompA", "title": "GTA VI leak roundup"}],
            ),
            patch(
                "analytics.competitor_context.snapshot_age_hours",
                return_value=6.0,
            ),
            patch(
                "core.intelligence_report.record_topic_snapshot",
            ),
            patch(
                "core.intelligence_report.build_accuracy_report",
                return_value={"status": "volume_gated", "summary": "n=0"},
            ),
        ):
            report = build_intelligence_report(discovery, variant_index=0)

        self.assertEqual(report.input_topic, "GTA VI multiplayer")
        self.assertEqual(report.selected_variant, "GTA VI multiplayer features")
        self.assertAlmostEqual(report.composite_score, 68.5)
        self.assertIn("youtube", report.signal_health)
        self.assertEqual(len(report.variants), 2)
        self.assertTrue(report.variants[0]["selected"])
        self.assertIn("confidence", report.corroboration)
        self.assertIn("phase", report.trajectory)
        self.assertIn("window_status", report.opportunity_window)

    def test_markdown_contains_sections(self):
        report = IntelligenceReport(
            generated_at="2026-06-04T12:00:00+00:00",
            channel_id="tapin",
            channel_name="TapIn Media",
            input_topic="UFC 250",
            selected_variant="Topuria vs Gaethje preview",
            composite_score=74.2,
            domain="ufc",
            variants=[{"variant": "Topuria vs Gaethje preview", "score": 74.2, "selected": True}],
            research_brief={
                "narrative": "Title fight stakes are clear.",
                "audience_sentiment": "Hyped",
                "controversy_score": 0.6,
                "debate_angles": ["Who has the edge?"],
            },
            signal_breakdown={"youtube": 0.22, "ufc_context": 0.18},
        )
        md = to_markdown(report)
        self.assertIn("# Content Intelligence Report", md)
        self.assertIn("Executive summary", md)
        self.assertIn("Signal rationale", md)
        self.assertIn("Topuria vs Gaethje preview", md)

    def test_mode_flags(self):
        with patch.dict("os.environ", {"CONTENT_MODE": "intelligence"}, clear=False):
            self.assertTrue(intelligence_mode_enabled())
            self.assertFalse(production_tail_enabled())
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(intelligence_mode_enabled())


if __name__ == "__main__":
    unittest.main()
