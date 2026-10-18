"""Wave 112 (2026-10-18): the next ten.

Measured first: `ops status` took 7.9 s, 5.0 of them `ops_doctor.gather` (torch's import for the
CUDA probe, a timed-out localhost connect for Ollama) for a line that only counts passes; a live
idea was another outlet's betting roundup; calls were made only for the menu's five previews; the
Monday compilation had no thumbnail of its own; retention curves were stored on 24 videos and
read by nothing - half the viewers were gone by 20% of the video.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOW = datetime(2026, 10, 18, 21, 0, tzinfo=timezone.utc)


class StatusDoctorTests(unittest.TestCase):
    """Item 1: the morning screen reuses a doctor result under 12 hours old."""

    def setUp(self):
        from core import ops_doctor

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = patch.object(ops_doctor, "DOCTOR_LAST_FILE", os.path.join(tmp.name, "doctor.json"))
        p.start()
        self.addCleanup(p.stop)

    def test_a_fresh_result_is_reused(self):
        from core import ops_doctor, status_summary

        checks = [{"name": "ollama", "ok": False, "detail": ""}, {"name": "feeds", "ok": True}]
        ops_doctor.save_last("tapin", checks, now=NOW - timedelta(hours=3))
        with (
            patch.object(ops_doctor, "_now", return_value=NOW),
            patch.object(ops_doctor, "gather") as gather,
        ):
            line = status_summary._doctor("tapin")
        gather.assert_not_called()
        self.assertIn("1 of 2 checks pass", line)
        self.assertIn("ollama", line)

    def test_a_stale_result_is_gathered_again_and_kept(self):
        from core import ops_doctor, status_summary

        ops_doctor.save_last(
            "tapin", [{"name": "feeds", "ok": True}], now=NOW - timedelta(hours=13)
        )
        fresh = {"channel_id": "tapin", "checks": [{"name": "feeds", "ok": True},
                                                   {"name": "oauth", "ok": True}]}  # fmt: skip
        with (
            patch.object(ops_doctor, "_now", return_value=NOW),
            patch.object(ops_doctor, "gather", return_value=fresh) as gather,
        ):
            line = status_summary._doctor("tapin")
            again = ops_doctor.last_checks("tapin")
        gather.assert_called_once()
        self.assertIn("2 of 2 checks pass", line)
        self.assertEqual(len(again or []), 2)


class RoundupIdeaTests(unittest.TestCase):
    """Item 2: live 2026-10-18, an idea was another outlet's betting roundup."""

    LIVE = "NFL Week 6 odds, predictions, expert picks: Cowboys roll into Lambeau Field to face Packers"

    def test_a_betting_roundup_is_not_an_idea(self):
        from core.best_bet import _is_roundup_headline

        self.assertTrue(_is_roundup_headline(self.LIVE))
        self.assertTrue(_is_roundup_headline("Week 7 NFL picks against the spread and best bets"))
        self.assertTrue(_is_roundup_headline("Lakers vs. Celtics player props and parlay picks"))

    def test_news_about_the_game_stays(self):
        from core.best_bet import _is_roundup_headline

        self.assertFalse(_is_roundup_headline("Micah Parsons ruled out for Cowboys at Packers"))
        self.assertFalse(_is_roundup_headline("Jets bench Justin Fields after Patriots loss"))

    def test_the_pool_drops_it(self):
        from core.best_bet import _consider_candidate

        with (
            patch("core.best_bet.infer_topic_domain", return_value="nfl", create=True),
            patch("apis.topic_scorer.infer_topic_domain", return_value="nfl"),
        ):
            got = _consider_candidate(self.LIVE, "CBS Sports", allowed={"nfl"}, exclude=set(),
                                      seen_local=set(), published=None, feed_domains=["nfl"])  # fmt: skip
        self.assertIsNone(got)


class WeekCallsTests(unittest.TestCase):
    """Item 3: calls were made only for the menu's five previews; "Picks, graded" needs more."""

    def test_overnight_calls_every_marquee_game_of_the_week(self):
        from types import SimpleNamespace

        from core import best_bet, overnight

        games = [best_bet.BestBetResult(topic=f"Team {i} at Team {i + 10}", domain="nfl",
                                        avg_engaged_rate=0.0, source="calendar", supporting_runs=0,
                                        rationale="") for i in range(7)]  # fmt: skip
        result = SimpleNamespace(channel_id="tapin", calls_line="")
        with (
            patch("core.seasonal_calendar.fetch_week_topics", return_value=[("x", "nfl")]),
            patch.object(best_bet, "suggested_games", return_value=games),
            patch(
                "core.predictions.calls.preview_calls",
                return_value={g.topic: {"call": "x"} for g in games},
            ) as made,  # fmt: skip
        ):
            overnight._call_week(result)
        self.assertEqual([b.topic for b in made.call_args.args[0]], [g.topic for g in games])
        self.assertIn("7", result.calls_line)


class WeekThumbnailTests(unittest.TestCase):
    """Item 4: the Monday compilation had no thumbnail of its own."""

    def test_the_compilation_gets_a_thumbnail_on_its_run(self):
        from types import SimpleNamespace

        from video import week_compile

        plan = week_compile.WeekPlan(
            channel_id="tapin", week="2026-10-19", title="TapIn Media Week in Review: Oct 15 - Oct 18",
            description="", seconds=590.0,
            items=[{"run_id": 1, "title": "A", "start": 0.0, "seconds": 100.0},
                   {"run_id": 2, "title": "B", "start": 100.0, "seconds": 85.0}],
        )  # fmt: skip
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "week.mp4")
            frames: list[list[str]] = []

            def run(argv, **_kw):
                frames.append(argv)
                open(argv[-1], "wb").close()
                return SimpleNamespace(returncode=0)

            with (
                patch("subprocess.run", side_effect=run),
                patch("PIL.Image.open", return_value=SimpleNamespace(convert=lambda *_: None)),
                patch(
                    "assets.thumbnail_compose.compose_thumbnail",
                    side_effect=lambda _b, _t, dest, **_k: open(dest, "wb").close(),
                ) as compose,  # fmt: skip
            ):
                thumb = week_compile.make_thumbnail(plan, video)
        self.assertTrue(thumb.endswith(".png"))
        self.assertIn("-ss", frames[0])
        self.assertEqual(frames[0][frames[0].index("-ss") + 1], "40.0")  # 40% into chapter one
        self.assertIn("Week in Review", compose.call_args.args[1])

    def test_the_record_carries_the_pick(self):
        from unittest.mock import MagicMock

        from video import week_compile

        plan = week_compile.WeekPlan(channel_id="tapin", week="2026-10-19", title="T",
                                     description="", items=[{"run_id": 1}], seconds=1.0)  # fmt: skip
        recorder = MagicMock(return_value=99)
        with patch("core.run_recorder.record_content_run", recorder):
            week_compile._record(plan, "C:/out/week.mp4", thumbnail="C:/out/week.png")
        features = recorder.call_args.kwargs["features"]
        self.assertEqual(features["thumbnail_pick"]["path"], "C:/out/week.png")


class FirstLineRuleTests(unittest.TestCase):
    """Item 6 (the operator: yes): half the viewers are gone by a quarter of the video, so the
    first sentence after the intro carries the stake and the call (or the take)."""

    def test_a_call_or_a_take_counts_and_a_bare_fact_does_not(self):
        from core.authenticity import first_line_take

        for line in (
            "Packers win this one, and Dallas can't stop the deep ball.",
            "Rakhmonov is 19-0 and the UFC is wasting him.",
            "If the Chargers can't cover Kelce, they lose by ten.",
            "My call: the Packers win by a touchdown.",
        ):
            self.assertTrue(first_line_take(line), line)
        for line in (
            "The Chargers are 0-4 for the first time since 2017.",
            "Gaethje TKO'd Topuria in round 2.",
            "Morales has three straight first-round knockouts.",
        ):
            self.assertFalse(first_line_take(line), line)

    def test_the_rewrite_takes_an_opener_with_a_call(self):
        from core import content_engine as ce

        script = ("The Chargers are 0-4 for the first time since 2017. Herbert has thrown six "
                  "interceptions. The defense ranks last against the pass.")  # fmt: skip
        openers = {"openers": ["The Chargers are 0-4 and Herbert keeps throwing picks.",
                               "The Chargers lose again unless Herbert stops throwing picks."]}  # fmt: skip
        sent: list[str] = []

        def llm(system, user, **_kw):
            sent.append(system)
            return openers

        with (
            patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "true", "FIRST_LINE_RULE": "true"}),
            patch.object(ce, "_call_content_llm", side_effect=llm),
            patch.object(ce, "_recent_openers", return_value=[]),
            patch("analytics.hook_learning.regen_guidance", return_value={}),
            patch("core.retention.drop_off_ratio", return_value=0.25),
        ):
            new, extra = ce._hook_variants(script, channel_id="tapin")
        self.assertIn("stake and the call", sent[0])
        self.assertTrue(new.startswith("The Chargers lose again unless"), extra)

    def test_growth_says_where_the_cliff_is(self):
        from core.retention import cliff_line

        with patch("core.retention.drop_off_ratio", return_value=0.25):
            line = cliff_line("tapin")
        self.assertIn("half the viewers are gone by 25%", line)


class ThirdChannelGateTests(unittest.TestCase):
    """Item 7, #1079: a third channel is decided with data - the gate, printed."""

    def _rows(self, stayed):
        return [{"stayed": s, "published": NOW - timedelta(days=i)} for i, s in enumerate(stayed)]

    def test_the_line_says_where_tapin_stands_against_the_bar(self):
        from analytics import growth

        with (
            patch.object(growth, "_rows", return_value=self._rows([0.25] * 12)),
            patch.dict(os.environ, {"THIRD_CHANNEL_BAR": "0.35"}),
        ):
            line = growth.third_channel_line("tapin")
        self.assertIn("not yet", line)
        self.assertIn("25%", line)
        self.assertIn("35%", line)

    def test_the_bar_cleared_says_so(self):
        from analytics import growth

        with (
            patch.object(growth, "_rows", return_value=self._rows([0.40] * 10 + [0.1] * 5)),
            patch.dict(os.environ, {"THIRD_CHANNEL_BAR": "0.35"}),
        ):
            line = growth.third_channel_line("tapin")
        self.assertIn("cleared", line)


class PaidSignalOutcomeTests(unittest.TestCase):
    """Item 8, #1071 step 1: the "keep" was measured on the composite score the signals feed."""

    def _traces(self):
        traces = []
        for run_id in range(1, 13):
            on = run_id % 2 == 0
            traces.append({"run_id": run_id, "composite_score": 90.0 if on else 30.0,
                           "signals": {"tiktok_trends": {"active": on, "status": "ok"}}})  # fmt: skip
        return traces

    def test_lift_is_read_on_measured_outcomes_not_the_composite(self):
        from core.paid_signal_attribution import attribute_paid_signals

        # Runs with the signal held worse: 20% engaged against 30%.
        engaged = {r: (0.20 if r % 2 == 0 else 0.30) for r in range(1, 13)}
        lifts = attribute_paid_signals(self._traces(), names=("tiktok_trends",),
                                       outcomes={"engaged_rate": engaged})  # fmt: skip
        lift = lifts[0]
        self.assertEqual(lift.metric, "engaged_rate")
        self.assertLess(lift.lift, 0)

    def test_no_outcomes_is_wait_not_the_composite(self):
        from core.paid_signal_attribution import attribute_paid_signals, recommend_catalog_action

        lift = attribute_paid_signals(self._traces(), names=("tiktok_trends",), outcomes={})[0]
        self.assertNotEqual(lift.metric, "composite_score")
        self.assertEqual(recommend_catalog_action(lift), "wait")

    def test_the_report_joins_the_channels_outcomes(self):
        from core import paid_signal_attribution as psa

        engaged = {r: (0.20 if r % 2 == 0 else 0.30) for r in range(1, 13)}
        with (
            patch("core.engagement_predictor.run_engagement_map", return_value=engaged),
            patch("core.predictions.ledger._views_outcomes", return_value={}),
        ):
            text = psa.report_from_traces(self._traces(), channel_id="tapin")
        self.assertIn("engaged_rate", text)
        self.assertIn("disable", text)


if __name__ == "__main__":
    unittest.main()
