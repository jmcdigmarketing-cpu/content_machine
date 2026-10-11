"""#1063, measured before building: the competitor watch has nothing to watch.

On 2026-10-10 `data/competitors_tapin.json` held one competitor - a tech reviewer, not a gaming
or sports channel - and its eight videos carried a title and a date, no view count (the RSS
sync does not return one). An outlier is a video ahead of its channel's median views; with no
views and one channel there is none to find. The health report said "OK". It now says what
the watch is missing, so the item is blocked on the list, not on code.
"""

from __future__ import annotations

import unittest


def _snapshot(n_competitors, with_views):
    video = {"video_id": "a", "title": "t", "published_at": "2026-10-08T21:00:40Z"}
    if with_views:
        video["views"] = 1000
    return {
        "competitors": [
            {"youtube_channel_id": f"UC{i}", "label": f"c{i}", "recent_videos": [dict(video)]}
            for i in range(n_competitors)
        ]
    }


class WatchCoverageTests(unittest.TestCase):
    def _lines(self, snapshot):
        from core.competitor_health import watch_coverage_lines

        return watch_coverage_lines(snapshot)

    def test_one_competitor_is_too_few(self):
        text = "\n".join(self._lines(_snapshot(1, with_views=True)))
        self.assertIn("1 competitor", text)
        self.assertIn("needs 3", text)

    def test_no_view_counts_is_said(self):
        text = "\n".join(self._lines(_snapshot(4, with_views=False)))
        self.assertIn("no view counts", text)

    def test_enough_channels_with_views_says_nothing(self):
        self.assertEqual(self._lines(_snapshot(4, with_views=True)), [])

    def test_an_empty_snapshot_says_it_was_never_synced(self):
        self.assertIn("never synced", "\n".join(self._lines({})))

    def test_the_report_carries_the_lines(self):
        from core.competitor_health import CompetitorHealth, render_report

        report = CompetitorHealth(channel_id="tapin", coverage=["outlier watch: x"])
        self.assertIn("outlier watch: x", render_report(report))


if __name__ == "__main__":
    unittest.main()
