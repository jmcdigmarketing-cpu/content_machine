"""Competitor-channel health — fake RSS/snapshot, no live HTTP."""

from __future__ import annotations

import unittest

from core.competitor_health import inspect_competitors, render_report, warning_lines

_GOOD_ID = "UCBJycsmduvYEL83R_U4JriQ"
_BAD_ID = "UCq-Fj5jknLsUf-MWSik4vhQ"


class TestCompetitorHealth(unittest.TestCase):
    def test_empty_rss_is_dead(self):
        channels = [{"id": _BAD_ID, "label": "Pat McAfee", "note": "unverified UC id"}]
        report = inspect_competitors(
            "tapin",
            channels=channels,
            fetch=lambda _cid: [],
        )
        self.assertFalse(report.ok)
        self.assertIn("empty", report.checks[0].detail)
        self.assertIn("unverified", report.checks[0].detail)
        blob = render_report(report)
        self.assertIn("FAIL", blob)

    def test_rss_with_videos_passes(self):
        channels = [{"id": _GOOD_ID, "label": "MKBHD"}]
        report = inspect_competitors(
            "tapin",
            channels=channels,
            fetch=lambda _cid: [{"title": "x", "video_id": "aaaaaaaaaaa"}],
        )
        self.assertTrue(report.ok)

    def test_malformed_id(self):
        report = inspect_competitors(
            "tapin",
            channels=[{"id": "not-a-uc", "label": "x"}],
            fetch=lambda _cid: [{"title": "x"}],
        )
        self.assertFalse(report.ok)
        self.assertIn("UC", report.checks[0].detail)

    def test_snapshot_empty_flags_without_fetch(self):
        channels = [{"id": _BAD_ID, "label": "Pat"}]
        snap = {
            "competitors": [{"youtube_channel_id": _BAD_ID, "label": "Pat", "recent_videos": []}]
        }
        report = inspect_competitors("tapin", channels=channels, snapshot=snap)
        self.assertFalse(report.ok)
        self.assertTrue(warning_lines(report))

    def test_missing_snapshot_ok_skips(self):
        channels = [{"id": _GOOD_ID, "label": "MKBHD"}]
        report = inspect_competitors(
            "tapin",
            channels=channels,
            snapshot={},
            missing_snapshot_ok=True,
        )
        self.assertEqual(report.checks, [])

    def test_ops_command_registered(self):
        from scripts import ops

        self.assertIn("competitor-health", ops.COMMANDS)

    def test_config_note_on_mcafee_id(self):
        from config.competitors import get_competitor_channels

        get_competitor_channels.cache_clear()
        rows = get_competitor_channels("tapin")
        mcafee = next(r for r in rows if "McAfee" in r.get("label", ""))
        self.assertIn("unverified", mcafee.get("note", ""))


if __name__ == "__main__":
    unittest.main()
