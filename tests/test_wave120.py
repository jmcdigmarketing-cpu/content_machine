"""Wave 120 (2026-10-21 night): the next ten.

Measured first: health said "1/10 recent runs missing quality_json" without the run, engagement gave
run numbers without dates, and no health line said where its number came from; nothing checked
that every public video has a run id (60 of 60 do); the weekly report never said how many drafts
an unsupported claim held; YPP numbers kept only today's snapshot; the compilation title named
nothing anyone searches for.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch


def _run(run_id, status="drafted", quality="{}", features='{"x": 1}'):
    return SimpleNamespace(id=run_id, status=status, quality_json=quality, features_json=features)


class DataQualityRunsTests(unittest.TestCase):
    """#1474 and #1395: a warning names its runs; a public video without a run id is named."""

    def _warnings(self, runs, rows):
        from core import data_quality

        repo = SimpleNamespace(list_for_channel=lambda c: runs)
        log = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
        ):
            data = {"signals": {}, "joins": data_quality._join_checks("tapin")}
        return data_quality.warnings(data)

    def test_the_run_is_named(self):
        runs = [_run(171, quality=""), _run(170, quality='{"g": 1}')]
        warns = self._warnings(runs, [])
        self.assertIn("1/2 recent runs missing quality_json (run 171)", warns[0])

    def test_a_public_video_without_a_run_id(self):
        rows = [
            SimpleNamespace(
                youtube_video_id="abc",
                content_run_id=None,
                privacy_status="public",
                metrics_json='{"v": 1}',
            ),
            SimpleNamespace(
                youtube_video_id="def",
                content_run_id=5,
                privacy_status="public",
                metrics_json='{"v": 1}',
            ),
        ]
        warns = self._warnings([], rows)
        self.assertEqual(
            warns, ["1 public video(s) have no run id (abc) - the learning cannot see them"]
        )


class HealthSourcesTests(unittest.TestCase):
    """#1471 and #1476: each health line names its source; engagement its dates."""

    def test_every_line_names_its_source(self):
        from core import channel_health

        report = channel_health.HealthReport(channel_id="tapin", overall="green")
        report.subs = [
            channel_health.HealthSub(
                "cadence", "green", "15 published in the last 7 days", source="publish log"
            )
        ]
        self.assertIn(
            "15 published in the last 7 days (from publish log)",
            channel_health.render_health(report),
        )
        self.assertEqual(
            set(channel_health.HEALTH_SOURCES), {name for name, _check in channel_health._CHECKS}
        )

    def test_the_engagement_window_has_dates(self):
        from core.channel_health import window_text

        made = {131: datetime(2026, 10, 9, tzinfo=timezone.utc), 157: datetime(2026, 10, 17, tzinfo=timezone.utc),
                169: datetime(2026, 10, 19, tzinfo=timezone.utc)}  # fmt: skip
        self.assertEqual(
            window_text([131, 140, 157], made, newest=169),
            "runs 131-157, Oct 9-17; newest measured run 169 (Oct 19)",
        )


class ClaimHoldRateTests(unittest.TestCase):
    """#1381: the week's share of drafts held for an unsupported claim, with up to 5 of them."""

    def test_the_rate_and_the_claims(self):
        from analytics.weekly_report import claim_hold_lines

        now = datetime(2026, 10, 21, 20, 0, tzinfo=timezone.utc)
        runs = [
            SimpleNamespace(
                id=177,
                created_at=datetime(2026, 10, 21, 10, 0),
                features_json=json.dumps({"claim_verification": {"x": 1}}),
            ),
            SimpleNamespace(
                id=176,
                created_at=datetime(2026, 10, 20, 21, 0),
                features_json=json.dumps({"claim_verification": {"x": 0}}),
            ),
            SimpleNamespace(
                id=100,
                created_at=datetime(2026, 10, 1, 9, 0),
                features_json=json.dumps({"claim_verification": {"x": 1}}),
            ),
        ]
        held = {1: ["Sean O'Malley publicly said Yan made a mistake ahead of the trilogy."]}
        with patch(
            "core.claim_types.blocking_unsupported",
            side_effect=lambda v: held.get((v or {}).get("x"), []),
        ):
            lines = claim_hold_lines(runs, now=now)
        self.assertEqual(lines[0], "Held for a claim: 1 of 2 drafts this week (50%)")
        self.assertEqual(
            lines[1],
            "  run 177: Sean O'Malley publicly said Yan made a mistake ahead of the trilogy.",
        )
        # run 162 was held, then rendered past with the operator's yes - the line says so
        runs[0].features_json = json.dumps(
            {"claim_verification": {"x": 1}, "grounding_override": True}
        )
        with patch(
            "core.claim_types.blocking_unsupported",
            side_effect=lambda v: held.get((v or {}).get("x"), []),
        ):
            self.assertTrue(
                claim_hold_lines(runs, now=now)[1].endswith("trilogy. (rendered past it)")
            )


class PrivacyMatchTests(unittest.TestCase):
    """#1389: the sync says what it checked when nothing needed correcting."""

    def test_all_match(self):
        from analytics.privacy_sync import sync_lines

        self.assertEqual(
            sync_lines({"checked": 12, "changed": []}),
            ["Privacy: 12 videos checked - the record matches YouTube"],
        )
        self.assertEqual(sync_lines({"checked": 0, "changed": []}), [])


class FirstSecondsTests(unittest.TestCase):
    """#1426: each video's retention at 3 seconds, from its curve."""

    def test_the_text(self):
        from core.retention import first_seconds_text

        curve = [(0.0, 1.2), (0.05, 0.98), (0.1, 0.9), (0.5, 0.5)]
        self.assertEqual(first_seconds_text(curve, 60.0), "98% still watching at 3 s")
        self.assertEqual(first_seconds_text(curve, None), "")
        # run 153 read "140% still watching": YouTube's ratio counts a replayed opening again
        self.assertEqual(first_seconds_text(curve, 300.0), "120% at 3 s (the opening was replayed)")


NUMBERS = {"as_of": "2026-10-21", "subscribers": 70, "long_hours_365d": 10.2, "shorts_views_90d": 2615,
           "shorts_paid_90d": 0, "subs_net_28d": 6}  # fmt: skip


class MonthlyYppTests(unittest.TestCase):
    """#1320: one YPP snapshot a month, and the four numbers against last month's."""

    def test_a_month_is_kept_and_compared(self):
        import os
        import tempfile

        from core import ypp_readiness

        with tempfile.TemporaryDirectory() as tmp:
            template = os.path.join(tmp, "ypp_{channel}.json")
            with patch.object(ypp_readiness, "YPP_TEMPLATE", template):
                ypp_readiness.save_ypp_numbers(
                    "tapin",
                    dict(
                        NUMBERS,
                        as_of="2026-09-30",
                        subscribers=60,
                        long_hours_365d=8.0,
                        shorts_views_90d=1900,
                        subs_net_28d=3,
                    ),
                )
                self.assertEqual(
                    ypp_readiness.monthly_card(ypp_readiness.load_ypp_numbers("tapin")),
                    [
                        "This month: subscribers 60, long-form hours 8.0, organic Shorts views (90 days) 1,900, net subscribers (28 days) 3 - first month on record"
                    ],
                )
                ypp_readiness.save_ypp_numbers("tapin", dict(NUMBERS))
                card = ypp_readiness.monthly_card(ypp_readiness.load_ypp_numbers("tapin"))
        self.assertEqual(
            card,
            [
                "This month: subscribers 70 (+10 on Sep), long-form hours 10.2 (+2.2), organic Shorts views "
                "(90 days) 2,615 (+715), net subscribers (28 days) 6 (+3)"
            ],
        )


ITEMS = [
    {"title": "Fans react to GTA 6 launch trailer with hype and cautious optimism", "names": ["GTA"], "views": 300},
    {"title": "Chargers' Pass Defense vs Chiefs' Offense: Key Preview for Oct 18",
     "names": ["Los Angeles Chargers", "Kansas City Chiefs", "Los Angeles Chargers'"], "views": 500},
    {"title": "Bo Nickal's UFC 335 bout with Joe Pyfer elevated to main event in Cleveland",
     "names": ["Bo Nickal", "UFC", "Joe Pyfer", "Cleveland"], "views": 900},
    {"title": "Ben Affleck Gets Destroyed by 12-Year-Olds in Fortnite", "names": ["Ben Affleck", "Fortnite"], "views": 10},
]  # fmt: skip


class CompilationTitleTests(unittest.TestCase):
    """#1316: the compilation's title names the week's most-viewed subjects."""

    def test_the_names(self):
        from video.week_compile import subject_name

        self.assertEqual(subject_name(ITEMS[0]["title"], ITEMS[0]["names"]), "GTA 6")
        self.assertEqual(subject_name(ITEMS[1]["title"], ITEMS[1]["names"]), "Chargers")
        self.assertEqual(subject_name(ITEMS[2]["title"], ITEMS[2]["names"]), "Bo Nickal")
        self.assertEqual(subject_name("Modern Warfare 4 campaign praised by Steam players",
                                      ["Steam", "Modern Warfare"]), "Modern Warfare 4")  # fmt: skip

    def test_the_title(self):
        from video.week_compile import compilation_title

        title = compilation_title("TapIn", ITEMS, "Oct 13-19")
        self.assertEqual(title, "Bo Nickal, Chargers & GTA 6 - TapIn Week in Review (Oct 13-19)")
        self.assertLessEqual(len(compilation_title("TapIn", ITEMS, "Oct 13-19", limit=50)), 50)
        self.assertEqual(
            compilation_title("TapIn", [], "Oct 13-19"), "TapIn Week in Review (Oct 13-19)"
        )


if __name__ == "__main__":
    unittest.main()
