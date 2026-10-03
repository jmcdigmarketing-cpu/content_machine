"""Wave 54: tracking success - views - and taking part in it (operator, 2026-10-03).

The operator set the goal (views), picked what to build, and the ritual (a 10-minute
weekly review). Nothing in the engine stated a target, asked the operator's own opinion of
a video, showed the writer what had worked, or read what viewers asked.

#934 a goal and a scoreboard: `config/goals.json`, channel views by day from YouTube
     Analytics (or the videos' own days), pace needed vs pace now, in `ops scoreboard`, the
     startup banner and the weekly report.
#935 your verdict per video, against the audience's views.
#936 `ops review-week`: the week's videos, your rating and note, next week's focus, and a
     scorecard file.
#937 the winners library: the channel's top videos by views, in the script prompt above a
     sample floor (a disclosed prompt change), and `ops winners`.
#114 the comment mailbag: viewer questions from the channel's own videos, clustered, offered
     as a best-bet candidate.
#939 found on the way: the signal audit's "cited" column read `record.script`, a field a
     content run does not have, so it was 0 for every signal on every run.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

TODAY = date(2026, 10, 3)


def _at(day: date, hour: int = 18) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


class _Stores(unittest.TestCase):
    """A temp publish log, goals file and every new store."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self.d = self._tmp.name
        self.goals_path = os.path.join(d, "goals.json")
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", os.path.join(d, "publish_log.json")),
            patch("core.success.goals.GOALS_FILE", self.goals_path),
            patch(
                "core.success.goals.CHANNEL_VIEWS_TEMPLATE",
                os.path.join(d, "channel_views_{channel}.json"),
            ),
            patch("core.success.goals.FOCUS_FILE", os.path.join(d, "focus.json")),
            patch("core.success.verdicts.VERDICTS_FILE", os.path.join(d, "verdicts.json")),
            patch("core.success.review.REVIEWS_ROOT", os.path.join(d, "output")),
            patch("analytics.mailbag.MAILBAG_TEMPLATE", os.path.join(d, "mailbag_{channel}.json")),
            patch("core.run_trace.TRACES_DIR", os.path.join(d, "traces")),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _goal(self, **kw):
        goal = {"metric": "views", "target": 20000, "since": "2026-09-01", "by": "2026-12-31",
                "uploads_per_week": 5}  # fmt: skip
        goal.update(kw)
        with open(self.goals_path, "w", encoding="utf-8") as f:
            json.dump({"tapin": goal}, f)

    def _video(self, vid, title, day, views, *, run_id=None, daily=None, rate=0.4, domain="gaming"):
        from storage.repositories.publish_log import get_publish_log_repository

        metrics = {"views": views, "engaged_rate": rate, "engaged_basis": "avg_view_pct",
                   "domain": domain}  # fmt: skip
        if daily is not None:
            metrics["daily_views"] = daily
        get_publish_log_repository().create(
            {
                "content_run_id": run_id,
                "channel_id": "tapin",
                "youtube_video_id": vid,
                "status": "uploaded",
                "detail": title,
                "metrics_json": json.dumps(metrics),
                "published_at": _at(day),
            }
        )


def _days(start: date, end: date, per_day: int) -> list[list]:
    out, d = [], start
    while d <= end:
        out.append([d.isoformat(), per_day])
        d += timedelta(days=1)
    return out


# ---- #934 ---------------------------------------------------------------------------


class ScoreboardTests(_Stores):
    def _channel_views(self, per_day=100):
        from core.success.goals import save_channel_views

        save_channel_views("tapin", _days(date(2026, 9, 1), date(2026, 10, 2), per_day))

    def test_pace_needed_against_pace_now(self):
        from core.success.goals import scoreboard_lines

        self._goal()
        self._channel_views()  # 32 days x 100 = 3,200; the last 28 days = 700 a week
        text = "\n".join(scoreboard_lines("tapin", today=TODAY))
        self.assertIn("so far: 3,200 views (16%)", text)
        self.assertIn("89 days left", text)
        self.assertIn("need 1,321/week, getting 700/week", text)
        self.assertIn("behind", text)
        self.assertIn("channel views by day", text)

    def test_pace_reads_the_last_four_weeks_even_for_a_new_goal(self):
        """Live check, wave 54: a goal counted from 2026-10-01 clipped the pace window to
        two days and still printed "(last 4 weeks)". Pace is the channel's rate now."""
        from core.success.goals import save_channel_views, scoreboard_lines

        self._goal(since="2026-10-01")
        save_channel_views(
            "tapin",
            _days(date(2026, 9, 1), date(2026, 9, 30), 100)
            + _days(date(2026, 10, 1), date(2026, 10, 2), 400),
        )
        text = "\n".join(scoreboard_lines("tapin", today=TODAY))
        self.assertIn("so far: 800 views", text)
        self.assertIn("getting 850/week (last 4 weeks)", text)  # (26 x 100 + 800) / 4

    def test_a_short_series_says_how_short(self):
        from core.success.goals import save_channel_views, scoreboard_lines

        self._goal()
        save_channel_views("tapin", _days(date(2026, 9, 26), date(2026, 10, 2), 100))
        self.assertIn(
            "getting 700/week (last 7 days)", "\n".join(scoreboard_lines("tapin", today=TODAY))
        )

    def test_on_track_says_so(self):
        from core.success.goals import scoreboard

        self._goal(target=8000)
        self._channel_views()
        board = scoreboard("tapin", today=TODAY)
        self.assertTrue(board["on_track"])
        self.assertEqual(board["projected"], 3200 + round(700 * 89 / 7))

    def test_without_channel_views_the_videos_days_are_summed(self):
        from core.success.goals import scoreboard

        self._goal()
        self._video(
            "v1", "A", date(2026, 9, 20), 900, daily=_days(date(2026, 9, 20), date(2026, 9, 29), 50)
        )
        self._video(
            "v2", "B", date(2026, 9, 25), 300, daily=[["2026-09-25", 120], ["2026-09-26", 80]]
        )
        board = scoreboard("tapin", today=TODAY)
        self.assertEqual(board["so_far"], 700)
        self.assertEqual(board["source"], "videos")

    def test_seeded_rows_never_count_toward_the_goal(self):
        from core.success.goals import scoreboard

        self._goal()
        self._video("seed_tapin_1", "old", date(2026, 9, 10), 5000,
                    daily=[["2026-09-10", 5000]])  # fmt: skip
        board = scoreboard("tapin", today=TODAY)
        self.assertEqual(board["so_far"], 0)

    def test_the_week_uploads_best_and_weakest(self):
        from core.success.goals import scoreboard_lines

        self._goal()
        self._channel_views()
        self._video("v1", "Elden Ring tier list", date(2026, 9, 29), 900)
        self._video("v2", "GTA 6 map", date(2026, 10, 1), 120)
        self._video("v3", "Older one", date(2026, 9, 20), 4000)
        text = "\n".join(scoreboard_lines("tapin", today=TODAY))
        self.assertIn("uploads, last 7 days: 2 of 5", text)
        self.assertIn('best: "Elden Ring tier list" 900 views', text)
        self.assertIn('weakest: "GTA 6 map" 120 views', text)

    def test_no_goal_says_where_to_set_one(self):
        from core.success.goals import banner_line, scoreboard_lines

        self.assertIn("config/goals.json", "\n".join(scoreboard_lines("tapin", today=TODAY)))
        self.assertEqual(banner_line("tapin", today=TODAY), "")

    def test_the_banner_is_one_line_with_the_focus(self):
        from core.success.goals import banner_line, set_focus

        self._goal()
        self._channel_views()
        set_focus("tapin", "hooks under 8 words")
        line = banner_line("tapin", today=TODAY)
        self.assertNotIn("\n", line)
        self.assertIn("3,200 / 20,000 views", line)
        self.assertIn("focus: hooks under 8 words", line)

    def test_the_sync_keeps_the_channel_series(self):
        from core.success import goals

        self._goal()
        with patch(
            "analytics.youtube_metrics.fetch_channel_daily_views",
            return_value=[["2026-10-01", 40], ["2026-10-02", 60]],
        ) as fetch:
            self.assertEqual(goals.sync_channel_views("tapin", today=TODAY), 2)
        fetch.assert_called_once()
        self.assertEqual(goals.channel_daily_views("tapin")[1], "channel")

    def test_the_metrics_sync_calls_it(self):
        from analytics import sync_metrics

        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(sync_metrics, "_probe_analytics_api", return_value=(True, "")),
            patch("core.success.goals.sync_channel_views", return_value=31) as sync,
            redirect_stdout(io.StringIO()) as out,
        ):
            sync_metrics.sync_channel("tapin")
        sync.assert_called_once_with("tapin")
        self.assertIn("31 day(s)", out.getvalue())

    def test_the_weekly_report_opens_with_it(self):
        from analytics.weekly_report import format_report

        self._goal()
        self._channel_views()
        with patch("core.success.goals._today", return_value=TODAY):
            text = format_report({"ready": False, "channel_id": "tapin", "n": 0})
        self.assertTrue(text.startswith("Scoreboard - tapin"))

    def test_ops_scoreboard(self):
        from scripts.ops import COMMANDS

        self._goal()
        self._channel_views()
        with (
            patch("core.success.goals._today", return_value=TODAY),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = COMMANDS["scoreboard"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("getting 700/week", out.getvalue())


# ---- #935 #936 ------------------------------------------------------------------------


class VerdictTests(_Stores):
    def _six(self):
        from core.success import verdicts

        for vid, views, rating in (("a", 5000, 5), ("b", 4000, 2), ("c", 900, 3),
                                   ("d", 800, 3), ("e", 100, 5), ("f", 50, 1)):  # fmt: skip
            self._video(vid, f"Video {vid}", date(2026, 9, 1), views)
            verdicts.record("tapin", vid, rating, note=f"note {vid}")

    def test_your_rating_against_the_views(self):
        from core.success.verdicts import verdict_report

        self._six()
        text = "\n".join(verdict_report("tapin"))
        self.assertIn("agreed on 4 of 6", text)
        self.assertIn('rated 4-5, landed in the bottom third: "Video e"', text)
        self.assertIn('rated 1-2, landed in the top third: "Video b"', text)

    def test_a_rating_outside_one_to_five_is_refused(self):
        from core.success import verdicts

        with self.assertRaises(ValueError):
            verdicts.record("tapin", "a", 6)

    def test_too_few_says_how_many_more(self):
        from core.success import verdicts

        self._video("a", "A", date(2026, 9, 1), 100)
        verdicts.record("tapin", "a", 4)
        self.assertIn("rate 2 more", "\n".join(verdicts.verdict_report("tapin")))


class ReviewWeekTests(_Stores):
    def test_a_scripted_review_writes_verdicts_focus_and_a_scorecard(self):
        from core.success import goals, review, verdicts

        self._goal()
        goals.save_channel_views("tapin", _days(date(2026, 9, 1), date(2026, 10, 2), 100))
        self._video("v1", "Elden Ring tier list", date(2026, 9, 29), 900)
        self._video("v2", "GTA 6 map", date(2026, 10, 1), 120)
        answers = iter(["5", "hook landed", "", "short hooks, one game per video"])
        lines: list[str] = []
        path = review.run_review(
            "tapin", today=TODAY, ask=lambda _p: next(answers), print_fn=lines.append
        )
        self.assertEqual(verdicts.load("tapin")["v1"]["rating"], 5)
        self.assertEqual(verdicts.load("tapin")["v1"]["note"], "hook landed")
        self.assertNotIn("v2", verdicts.load("tapin"))  # Enter skipped it
        self.assertEqual(goals.focus("tapin"), "short hooks, one game per video")
        self.assertTrue(path.endswith(os.path.join("tapin", "reviews", "2026-W40.md")))
        with open(path, encoding="utf-8") as f:
            card = f.read()
        self.assertIn("Elden Ring tier list", card)
        self.assertIn("hook landed", card)
        self.assertIn("short hooks, one game per video", card)
        self.assertIn("getting 700/week", card)

    def test_ops_review_week_runs_it(self):
        from scripts.ops import COMMANDS

        self._goal()
        with (
            patch("core.success.goals._today", return_value=TODAY),
            patch("core.ask.ask_text", return_value=""),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = COMMANDS["review-week"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("2026-W40.md", out.getvalue())

    def test_ops_verdicts(self):
        from scripts.ops import COMMANDS

        with redirect_stdout(io.StringIO()) as out:
            COMMANDS["verdicts"][1](Namespace(channel="tapin"))
        self.assertIn("Your verdicts vs the audience", out.getvalue())


# ---- #937 ------------------------------------------------------------------------------


class WinnersTests(_Stores):
    def _videos(self, n):
        for i in range(n):
            self._video(f"v{i}", f"Video {i}", date(2026, 8, 1) + timedelta(days=i), 100 * (i + 1),
                        domain="ufc" if i % 2 else "gaming")  # fmt: skip

    def test_nothing_below_the_floor(self):
        from core.success.winners import winners_block

        self._videos(7)
        self.assertEqual(winners_block("tapin"), "")

    def test_the_top_videos_with_their_hook_and_length(self):
        from core.success.winners import winners_block

        self._videos(12)
        record = type("R", (), {"features_json": json.dumps(
            {"hook_text": "Nobody saw this KO coming.", "format": "Medium (40-60s)", "domain": "ufc"}
        )})()  # fmt: skip
        repo = type("Repo", (), {"get": lambda self, i: record if i == 11 else None})()
        self._video(
            "v11b", "Topuria stuns everyone", date(2026, 9, 1), 9000, run_id=11, domain="ufc"
        )
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            block = winners_block("tapin")
        self.assertTrue(block.startswith("WHAT WORKS ON THIS CHANNEL"))
        self.assertIn('"Topuria stuns everyone" - 9,000 views', block)
        self.assertIn('hook: "Nobody saw this KO coming."', block)
        self.assertIn("Medium (40-60s)", block)
        self.assertEqual(block.count("\n- "), 3)  # 13 measured: top 10%, at least 3

    def test_the_script_prompt_carries_it(self):
        from core import content_engine

        with patch(
            "core.success.winners.winners_block", return_value="WHAT WORKS ON THIS CHANNEL x"
        ):
            _system, user = _prompts(content_engine)
        self.assertIn("WHAT WORKS ON THIS CHANNEL x", user)

    def test_it_can_be_switched_off(self):
        from core.success.winners import winners_block

        self._videos(12)
        with patch.dict(os.environ, {"WINNERS_IN_PROMPT": "false"}):
            self.assertEqual(winners_block("tapin"), "")

    def test_ops_winners(self):
        from scripts.ops import COMMANDS

        self._videos(3)
        with redirect_stdout(io.StringIO()) as out:
            COMMANDS["winners"][1](Namespace(channel="tapin"))
        self.assertIn("3 measured video(s); the library needs 8", out.getvalue())


def _prompts(content_engine):
    return content_engine._build_prompts(
        topic="GTA 6 map", signals={}, min_words=90, max_words=130, today="2026-10-03",
        channel_id="tapin", script_brief="", seo_block="", signal_facts="",
        signal_summary="", brief_block="", length_choice="2",
    )  # fmt: skip


# ---- #114 ------------------------------------------------------------------------------

COMMENTS = {
    "v1": [
        {"text": "Will GTA 6 have a bigger map than San Andreas?", "likes": 40, "replies": 2, "video_id": "v1"},
        {"text": "great video man", "likes": 3, "replies": 0, "video_id": "v1"},
        {"text": "When does the Nightreign DLC finally come out?", "likes": 5, "replies": 0, "video_id": "v1"},
    ],
    "v2": [
        {"text": "Is the GTA 6 map actually bigger than RDR2 or not?", "likes": 12, "replies": 1, "video_id": "v2"},
        {"text": "honestly how big is the GTA 6 map going to be?", "likes": 2, "replies": 0, "video_id": "v2"},
    ],
}  # fmt: skip


class MailbagTests(_Stores):
    def _fetch(self):
        from analytics import mailbag

        self._video("v1", "GTA 6 trailer 3", date(2026, 9, 28), 900)
        self._video("v2", "GTA 6 price", date(2026, 9, 30), 400)
        with (
            patch("apis.youtube_api._get_youtube_client", return_value=object()),
            patch(
                "apis.youtube_comments_signal._fetch_comments",
                side_effect=lambda _yt, vid, _n: COMMENTS.get(vid, []),
            ),
        ):
            return mailbag.fetch("tapin")

    def test_questions_cluster_by_shared_words(self):
        data = self._fetch()
        top = data["clusters"][0]
        self.assertEqual(top["question"], "Will GTA 6 have a bigger map than San Andreas?")
        self.assertEqual(top["count"], 3)
        self.assertEqual(sorted(top["videos"]), ["v1", "v2"])
        self.assertEqual(data["clusters"][1]["count"], 1)
        self.assertEqual(data["videos"], 2)

    def test_it_becomes_a_best_bet_candidate(self):
        from core import best_bet

        self._fetch()
        entry = {"run_id": 1, "topic": "GTA 6 trailer", "input_topic": "GTA 6 trailer",
                 "selected_topic": "", "engaged_rate": 0.4, "subscribers_gained": 0,
                 "composite_score": 50.0, "domain": "gaming", "age_days": 3.0}  # fmt: skip
        with (
            patch.object(best_bet, "_build_entries", return_value=[entry]),
            patch.object(best_bet, "_fresh_enabled", return_value=False),
            patch.object(best_bet, "recent_input_topics", return_value=[]),
            patch("core.topic_graph.follow_up_seed", return_value=None),
            patch("core.seasonal_calendar.due_topics", return_value=[]),
            patch("core.topic_db.graveyard_topics", return_value=[]),
        ):
            options = best_bet.get_best_bets("tapin", n=3)
        asked = [o for o in options if o.source == "mailbag"]
        self.assertEqual(len(asked), 1)
        self.assertEqual(asked[0].topic, "Will GTA 6 have a bigger map than San Andreas?")
        self.assertIn("viewers asked: 3 viewers on 2 videos", asked[0].rationale)

    def test_a_single_question_is_not_a_candidate(self):
        from analytics.mailbag import top_question

        with open(os.path.join(self.d, "mailbag_tapin.json"), "w", encoding="utf-8") as f:
            json.dump({"clusters": [{"question": "Why?", "count": 1, "videos": ["v1"]}]}, f)
        self.assertIsNone(top_question("tapin"))

    def test_ops_mailbag_fetches_then_lists(self):
        from scripts.ops import COMMANDS

        self._video("v1", "GTA 6 trailer 3", date(2026, 9, 28), 900)
        self._video("v2", "GTA 6 price", date(2026, 9, 30), 400)
        with (
            patch("apis.youtube_api._get_youtube_client", return_value=object()),
            patch(
                "apis.youtube_comments_signal._fetch_comments",
                side_effect=lambda _yt, vid, _n: COMMENTS.get(vid, []),
            ),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = COMMANDS["mailbag"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("3 viewers: Will GTA 6 have a bigger map than San Andreas?", out.getvalue())

    def test_the_sync_fetches_only_when_asked(self):
        from analytics import sync_metrics

        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true", "MAILBAG_SYNC": ""}),
            patch.object(sync_metrics, "_probe_analytics_api", return_value=(True, "")),
            patch("core.success.goals.sync_channel_views", return_value=0),
            patch("analytics.mailbag.fetch") as fetch,
            redirect_stdout(io.StringIO()),
        ):
            sync_metrics.sync_channel("tapin")
            fetch.assert_not_called()
            with patch.dict(os.environ, {"MAILBAG_SYNC": "true"}):
                sync_metrics.sync_channel("tapin")
            fetch.assert_called_once_with("tapin")


# ---- #939 ------------------------------------------------------------------------------


class SignalAuditCitedTests(_Stores):
    def test_cited_reads_the_runs_full_script(self):
        from core.run_trace import write_full_script
        from core.runs.signal_audit import contribution_rows, load_runs

        traces = os.path.join(self.d, "traces")
        os.makedirs(traces, exist_ok=True)
        rawg = {"connected": True, "active": True, "status": "ok",
                "data": [{"name": "Elden Ring Nightreign", "released": "2025-05-30"}]}  # fmt: skip
        with open(os.path.join(traces, "7.signals.json"), "w", encoding="utf-8") as f:
            json.dump({"signals": {"rawg": rawg}}, f)
        with open(os.path.join(traces, "7.json"), "w", encoding="utf-8") as f:
            json.dump({"run_id": 7, "selected_topic": "Nightreign", "channel_id": "tapin"}, f)
        write_full_script(7, "Elden Ring Nightreign changed everything this week.")
        rows = {r["signal"]: r for r in contribution_rows(load_runs(channel_id="tapin"))}
        self.assertEqual(rows["rawg"]["cited"], 1)


if __name__ == "__main__":
    unittest.main()
