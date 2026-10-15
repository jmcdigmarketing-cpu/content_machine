"""#1198: weekly-report and growth say which feed liked what.

An empty store says there are no platform results yet. No network.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch


class FeedReportTests(unittest.TestCase):
    def test_an_empty_store_says_there_are_no_platform_results(self):
        from analytics.growth import render
        from analytics.weekly_report import format_report
        from publishing.platform_recommend import feed_lines

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "publishing.platform_metrics.METRICS_TEMPLATE",
                os.path.join(tmp, "platform_metrics_{channel}.json"),
            ),
        ):
            self.assertEqual(feed_lines("tapin"), ["No platform results yet."])
            weekly = format_report({"channel_id": "tapin", "n": 0, "ready": False})
            growth = render("tapin")
        self.assertIn("No platform results yet.", weekly)
        self.assertIn("No platform results yet.", growth)

    def test_views_best_video_and_the_preferred_domain_are_named(self):
        from analytics.weekly_report import format_report
        from publishing import crosspost
        from publishing.platform_metrics import _save
        from publishing.platform_recommend import feed_lines

        rows = {}
        for i in range(4):
            rows[str(i)] = {
                "tiktok": {
                    "measured": True,
                    "views": 100 * (i + 1),
                    "hour": 21,
                    "domain": "ufc",
                    "length": "2",
                }
            }
        with (
            tempfile.TemporaryDirectory() as tmp,
            (
                patch(
                    "publishing.crosspost.CROSSPOST_TEMPLATE",
                    os.path.join(tmp, "crosspost_{channel}.json"),
                )
            ),
            patch(
                "publishing.platform_metrics.METRICS_TEMPLATE",
                os.path.join(tmp, "platform_metrics_{channel}.json"),
            ),
        ):
            crosspost._save("tapin", {"posts": {"3": {"title": "Topuria"}}})
            _save("tapin", {"rows": rows})
            text = "\n".join(feed_lines("tapin"))
            weekly = format_report({"channel_id": "tapin", "n": 0, "ready": False})
        self.assertIn("400", text)  # 100+200+300+400
        self.assertIn("Topuria", text)
        self.assertIn("ufc", text)
        self.assertIn("Topuria", weekly)
        self.assertIn("ufc", weekly)
