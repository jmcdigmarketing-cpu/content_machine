"""Wave 55: the views story the scoreboard opened (operator, 2026-10-03).

#943 week over week: weekly totals from the channel series, one history row per review,
     and an on-pace streak.
#941 uploads made outside Content OS: the channel's own uploads list (2 units a sync)
     counts toward "uploads this week", and the line says how many were made elsewhere.
#942 the mailbag loop: a question a run answered is no longer offered, and `ops mailbag`
     drafts the reply (the comment's own link and the new video's) - nothing is posted
     (operator: draft the reply, you post).
#940 comparable views: a video's views in its first 7 days (from views by day), and its
     lifetime views from the Data API - the 28-day window compared videos of different
     ages.
#938 the recommenders aim at 7-day views (operator: 7-day views, switchable): best bet,
     length and post time read `core/success/target.outcome`; `RECOMMEND_TARGET=engaged`
     is today's behaviour. The ledger scores each claim on its own target.
"""

from __future__ import annotations

import io
import json
import math
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

TODAY = date(2026, 10, 3)
VIEWS = {"RECOMMEND_TARGET": "views"}
ENGAGED = {"RECOMMEND_TARGET": "engaged"}


def _days(start: date, n: int, per_day: int) -> list[list]:
    return [[(start + timedelta(days=i)).isoformat(), per_day] for i in range(n)]


def _published(days_ago: int) -> datetime:
    return datetime.now(timezone.utc).replace(
        hour=18, minute=0, second=0, microsecond=0
    ) - timedelta(days=days_ago)


def _from_publish_day(published: datetime, n: int, per_day: int) -> list[list]:
    from analytics.view_curve import publish_day

    return _days(publish_day(published), n, per_day)


class _Stores(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self.d = self._tmp.name
        self.runs: dict[int, SimpleNamespace] = {}
        repo = SimpleNamespace(
            list_for_channel=lambda c: sorted(self.runs.values(), key=lambda r: -r.id),
            get=lambda i: self.runs.get(int(i)),
        )
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", os.path.join(d, "publish_log.json")),
            patch("core.success.goals.GOALS_FILE", os.path.join(d, "goals.json")),
            patch(
                "core.success.goals.CHANNEL_VIEWS_TEMPLATE", os.path.join(d, "views_{channel}.json")
            ),
            patch("core.success.goals.FOCUS_FILE", os.path.join(d, "focus.json")),
            patch("core.success.goals.HISTORY_TEMPLATE", os.path.join(d, "history_{channel}.json")),
            patch("core.success.verdicts.VERDICTS_FILE", os.path.join(d, "verdicts.json")),
            patch("core.success.review.REVIEWS_ROOT", os.path.join(d, "output")),
            patch("analytics.mailbag.MAILBAG_TEMPLATE", os.path.join(d, "mailbag_{channel}.json")),
            patch("core.run_trace.TRACES_DIR", os.path.join(d, "traces")),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _run(self, run_id, topic, **kw):
        self.runs[run_id] = SimpleNamespace(
            id=run_id, channel_id="tapin", input_topic=topic, selected_topic=topic,
            composite_score=50.0, timings_json=json.dumps(kw.get("timings") or {}),
            features_json=json.dumps(kw.get("features") or {}), quality_json="{}",
            status="done",
        )  # fmt: skip

    def _video(self, vid, *, run_id=None, published=None, views=100, rate=0.4, daily=None,
               title=None, domain=None):  # fmt: skip
        from storage.repositories.publish_log import get_publish_log_repository

        metrics = {"views": views, "engaged_rate": rate, "engaged_basis": "avg_view_pct"}
        if daily is not None:
            metrics["daily_views"] = daily
        if domain:
            metrics["domain"] = domain
        get_publish_log_repository().create(
            {
                "content_run_id": run_id,
                "channel_id": "tapin",
                "youtube_video_id": vid,
                "status": "uploaded",
                "detail": title or f"Video {vid}",
                "metrics_json": json.dumps(metrics),
                "published_at": published or _published(30),
            }
        )

    def _goal(self, **kw):
        goal = {"metric": "views", "target": 20000, "since": "2026-09-01", "by": "2026-12-31",
                "uploads_per_week": 5}  # fmt: skip
        goal.update(kw)
        with open(os.path.join(self.d, "goals.json"), "w", encoding="utf-8") as f:
            json.dump({"tapin": goal}, f)


# ---- #943 ------------------------------------------------------------------------------


class WeekOverWeekTests(_Stores):
    def test_weekly_totals_are_complete_iso_weeks(self):
        from core.success.goals import weekly_totals

        daily = _days(date(2026, 9, 1), 32, 100)  # Tuesday 2026-09-01 .. 10-02
        # W36 began on Monday 08-31, before the series: a part-week would read as a drop
        # (wave 55's live check printed "W34 3,400 · W35 5,740 ..." for a Thursday start).
        self.assertEqual(
            weekly_totals(daily, TODAY),
            [["2026-W37", 700], ["2026-W38", 700], ["2026-W39", 700]],
        )

    def test_the_scoreboard_prints_the_weeks(self):
        from core.success.goals import save_channel_views, scoreboard_lines

        self._goal()
        save_channel_views(
            "tapin", _days(date(2026, 9, 1), 25, 100) + _days(date(2026, 9, 26), 7, 140)
        )
        text = "\n".join(scoreboard_lines("tapin", today=TODAY))
        self.assertIn("weeks: W37 700 · W38 700 · W39 780 (W39 vs W38: +11%)", text)

    def test_a_review_writes_one_row_per_week_and_the_streak_counts(self):
        from core.success import goals, review

        self._goal(target=8000)
        goals.save_channel_views("tapin", _days(date(2026, 9, 1), 32, 100))
        goals.record_week("tapin", {"week": "2026-W39", "on_track": True})
        for _ in range(2):  # a second review in the same week replaces its row
            review.run_review("tapin", today=TODAY, ask=lambda _p: "", print_fn=lambda _l: None)
        rows = goals.review_history("tapin")
        self.assertEqual([r["week"] for r in rows], ["2026-W39", "2026-W40"])
        self.assertTrue(rows[-1]["on_track"])
        text = "\n".join(goals.scoreboard_lines("tapin", today=TODAY))
        self.assertIn("on pace 2 reviews running", text)
        with open(review.scorecard_path("tapin", TODAY), encoding="utf-8") as f:
            self.assertIn("## Week over week", f.read())


# ---- #941 ------------------------------------------------------------------------------


class OutsideUploadsTests(_Stores):
    def test_uploads_made_elsewhere_count_and_are_named(self):
        from core.success.goals import save_channel_uploads, save_channel_views, scoreboard_lines

        self._goal()
        save_channel_views("tapin", _days(date(2026, 9, 1), 32, 100))
        when = datetime(2026, 10, 1, 18, tzinfo=timezone.utc)
        self._video("v1", published=when)
        self._video("v2", published=when - timedelta(days=1))
        save_channel_uploads(
            "tapin",
            [
                {"video_id": "v1", "published_at": when.isoformat(), "title": "a"},
                {
                    "video_id": "v2",
                    "published_at": (when - timedelta(days=1)).isoformat(),
                    "title": "b",
                },
                {
                    "video_id": "x9",
                    "published_at": (when - timedelta(days=2)).isoformat(),
                    "title": "c",
                },
                {"video_id": "x8", "published_at": "2026-09-10T18:00:00+00:00", "title": "old"},
            ],
        )
        text = "\n".join(scoreboard_lines("tapin", today=TODAY))
        self.assertIn("uploads, last 7 days: 3 of 5 (1 made outside Content OS)", text)

    def test_the_sync_stores_the_uploads_list(self):
        from core.success import goals

        uploads = [{"video_id": "v1", "published_at": "2026-10-01T18:00:00+00:00", "title": "a"}]
        with (
            patch(
                "analytics.youtube_metrics.fetch_channel_daily_views",
                return_value=[["2026-10-01", 5]],
            ),
            patch("analytics.youtube_metrics.fetch_channel_uploads", return_value=uploads),
        ):
            goals.sync_channel_views("tapin", today=TODAY)
        self.assertEqual(goals.channel_uploads("tapin"), uploads)

    def test_one_helper_reads_the_uploads_playlist(self):
        from youtube.channel_uploads import uploads_playlist_items

        service = MagicMock()
        service.channels().list().execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]
        }
        service.playlistItems().list().execute.return_value = {
            "items": [
                {
                    "snippet": {"title": "GTA 6 map", "resourceId": {"videoId": "v1"}},
                    "contentDetails": {"videoPublishedAt": "2026-10-01T18:00:00Z"},
                }
            ]
        }
        self.assertEqual(
            uploads_playlist_items(service),
            [{"video_id": "v1", "title": "GTA 6 map", "published_at": "2026-10-01T18:00:00Z"}],
        )
        from publishing.youtube_publisher import _find_video_on_channel

        self.assertEqual(_find_video_on_channel(service, "GTA 6 map"), "v1")


# ---- #942 ------------------------------------------------------------------------------

Q1 = "Will GTA 6 have a bigger map than San Andreas?"
Q2 = "When does the Nightreign DLC finally come out?"


class MailbagLoopTests(_Stores):
    def _mailbag(self):
        data = {
            "videos": 2,
            "comments": 5,
            "clusters": [
                {"question": Q1, "count": 3, "videos": ["v1", "v2"], "examples": [Q1],
                 "comments": [{"video_id": "v1", "comment_id": "c1", "text": Q1},
                              {"video_id": "v2", "comment_id": "c2", "text": "GTA 6 map bigger?"}]},
                {"question": Q2, "count": 2, "videos": ["v1"], "examples": [Q2],
                 "comments": [{"video_id": "v1", "comment_id": "c3", "text": Q2}]},
            ],
        }  # fmt: skip
        with open(os.path.join(self.d, "mailbag_tapin.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_the_comment_id_comes_back(self):
        from apis.youtube_comments_signal import _fetch_comments

        yt = MagicMock()
        yt.commentThreads().list().execute.return_value = {
            "items": [
                {
                    "id": "c1",
                    "snippet": {
                        "topLevelComment": {"snippet": {"textDisplay": Q1, "likeCount": 4}}
                    },
                }
            ]
        }
        self.assertEqual(_fetch_comments(yt, "v1", 10)[0]["comment_id"], "c1")

    def test_an_answered_question_is_not_offered_again(self):
        from analytics.mailbag import answered, top_question

        self._mailbag()
        self._run(5, Q1)
        self.assertIn(Q1.lower(), answered("tapin"))
        self.assertEqual(top_question("tapin")["question"], Q2)

    def test_a_best_bet_pick_answers_it_too(self):
        from analytics.mailbag import top_question

        self._mailbag()
        self._run(5, Q1)
        pick = {"offered": [{"topic": Q2, "source": "mailbag"}], "picked": 1, "by": "operator"}
        self._run(6, "Nightreign DLC date", features={"best_bet": pick})
        self.assertIsNone(top_question("tapin"))

    def test_ops_mailbag_drafts_the_reply_and_posts_nothing(self):
        from analytics.mailbag import mailbag_lines

        self._mailbag()
        self._run(5, Q1)
        self._video("new1", run_id=5, published=_published(1))
        text = "\n".join(mailbag_lines("tapin"))
        self.assertIn("Answered - reply drafts (you post them)", text)
        self.assertIn("https://www.youtube.com/watch?v=v1&lc=c1", text)
        self.assertIn("https://www.youtube.com/watch?v=v2&lc=c2", text)
        self.assertIn("Answered this one here: https://youtu.be/new1", text)


# ---- #940 ------------------------------------------------------------------------------


class SevenDayViewsTests(_Stores):
    def test_the_first_seven_days_from_the_publish_day(self):
        from core.success.target import views_7d

        when = _published(30)
        self.assertEqual(views_7d({"daily_views": _from_publish_day(when, 10, 100)}, when), 700)

    def test_a_series_that_starts_late_or_stops_early_says_nothing(self):
        from analytics.view_curve import publish_day
        from core.success.target import views_7d

        when = _published(30)
        late = _days(publish_day(when) + timedelta(days=2), 10, 100)
        early = _from_publish_day(when, 4, 100)
        self.assertIsNone(views_7d({"daily_views": late}, when))
        self.assertIsNone(views_7d({"daily_views": early}, when))

    def test_winners_rank_by_seven_day_views(self):
        from core.success.winners import winners_lines

        for i in range(9):
            when = _published(20 + i)
            self._video(f"v{i}", published=when, views=100 * (i + 1),
                        daily=_from_publish_day(when, 10, 10 * (9 - i)))  # fmt: skip
        text = "\n".join(winners_lines("tapin"))
        self.assertIn("by views in their first 7 days", text)
        self.assertIn('1. "Video v0" - 630 views in 7 days', text)

    def test_the_sync_keeps_lifetime_views(self):
        from analytics import sync_metrics
        from core.success.videos import channel_videos

        self._video("v1", published=_published(40))
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(sync_metrics, "_probe_analytics_api", return_value=(True, "")),
            patch.object(sync_metrics, "refresh_publish_metrics", return_value=None),
            patch("analytics.youtube_metrics.fetch_lifetime_views", return_value={"v1": 5400}),
            patch("core.success.goals.sync_channel_views", return_value=0),
            redirect_stdout(io.StringIO()),
        ):
            sync_metrics.sync_channel("tapin")
        self.assertEqual(channel_videos("tapin")[0].lifetime_views, 5400)

    def test_lifetime_views_come_from_one_statistics_call(self):
        from analytics import youtube_metrics

        service = MagicMock()
        service.videos().list().execute.return_value = {
            "items": [{"id": "a", "statistics": {"viewCount": "1234"}}]
        }
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch("analytics.youtube_metrics.get_youtube_service", return_value=service),
        ):
            self.assertEqual(
                youtube_metrics.fetch_lifetime_views(["a", "b"], channel_id="tapin"), {"a": 1234}
            )


# ---- #938 ------------------------------------------------------------------------------


class TargetTests(_Stores):
    def _two_domains(self):
        """Gaming: high engagement, few views. UFC: low engagement, many views."""
        for i in range(4):
            g, u = 10 + i, 20 + i
            self._run(g, f"Elden Ring tier list part {i}")
            self._run(u, f"UFC 320 Topuria knockout part {i}")
            wg, wu = _published(30 + i), _published(40 + i)
            self._video(
                f"g{i}", run_id=g, published=wg, rate=0.5, daily=_from_publish_day(wg, 10, 10)
            )
            self._video(
                f"u{i}", run_id=u, published=wu, rate=0.2, daily=_from_publish_day(wu, 10, 500)
            )

    def test_the_default_target_is_views(self):
        from core.success.target import target

        with patch.dict(os.environ, {"RECOMMEND_TARGET": ""}):
            self.assertEqual(target(), "views")
        with patch.dict(os.environ, ENGAGED):
            self.assertEqual(target(), "engaged")

    def test_the_best_bet_follows_the_target(self):
        from core.best_bet import get_best_bet

        self._two_domains()
        with patch.dict(os.environ, ENGAGED):
            engaged = get_best_bet("tapin")
        with patch.dict(os.environ, VIEWS):
            views = get_best_bet("tapin")
        self.assertEqual(engaged.domain, "gaming")
        self.assertIn("50.0% engagement", engaged.rationale)
        self.assertEqual(views.domain, "ufc")
        self.assertIn("3,500 views in 7 days", views.rationale)

    def test_the_length_recommender_follows_the_target(self):
        from core.length_recommender import get_recommended_length

        for i in range(6):
            choice, per_day, rate = ("1", 2000, 0.2) if i < 3 else ("3", 50, 0.6)
            self._run(i + 1, f"GTA 6 map leak {i}", timings={"length_preset": choice})
            when = _published(30 + i)
            self._video(f"v{i}", run_id=i + 1, published=when, rate=rate,
                        daily=_from_publish_day(when, 10, per_day))  # fmt: skip
        with patch.dict(os.environ, ENGAGED):
            self.assertEqual(get_recommended_length("tapin").length_choice, "3")
        with patch.dict(os.environ, VIEWS):
            rec = get_recommended_length("tapin")
        self.assertEqual(rec.length_choice, "1")
        self.assertIn("14,000 views in 7 days", rec.rationale)

    def test_post_time_learns_from_the_target(self):
        from analytics.post_timing import _collect_timed_samples

        when = _published(30)
        self._video("v1", published=when, rate=0.3, daily=_from_publish_day(when, 10, 100))
        with patch.dict(os.environ, VIEWS):
            ((_d, _w, value),) = _collect_timed_samples("tapin")
        self.assertAlmostEqual(value, math.log1p(700))
        with patch.dict(os.environ, ENGAGED):
            ((_d, _w, value),) = _collect_timed_samples("tapin")
        self.assertAlmostEqual(value, 0.3)

    def test_a_pick_records_its_target(self):
        from core.best_bet import BestBetResult, pick_record

        option = BestBetResult(topic="t", domain="gaming", avg_engaged_rate=6.5, source="analytics",
                               supporting_runs=3, rationale="")  # fmt: skip
        with patch.dict(os.environ, VIEWS):
            self.assertEqual(pick_record([option], 1)["target"], "views")

    def test_the_ledger_scores_each_claim_on_its_own_target(self):
        from core.predictions.ledger import LEDGER_KEY, ledger_rows

        when = _published(30)
        for run_id, claim in (
            (
                1,
                {"recommended": "1", "chosen": "1", "expected": math.log1p(500), "target": "views"},
            ),
            (2, {"recommended": "1", "chosen": "1", "expected": 0.25}),  # frozen before #938
        ):
            self._run(run_id, f"topic {run_id}",
                      features={LEDGER_KEY: {"backfilled": False, "length": claim}})  # fmt: skip
            self._video(f"v{run_id}", run_id=run_id, published=when, rate=0.3,
                        daily=_from_publish_day(when, 10, 1000 // 7 + 1))  # fmt: skip
        rows = {r["run_id"]: r for r in ledger_rows("tapin")}
        views_7d = 7 * (1000 // 7 + 1)
        self.assertAlmostEqual(
            rows[1]["length_error_views"], math.log1p(views_7d) - math.log1p(500)
        )
        self.assertNotIn("length_error", rows[1])
        self.assertAlmostEqual(rows[2]["length_error"], 0.05)

    def test_the_analytics_snapshot_names_a_target_change(self):
        from core.runs import analytics_snapshot

        with patch.dict(os.environ, ENGAGED):
            analytics_snapshot.save(9, "tapin")
        with patch.dict(os.environ, VIEWS):
            text = "\n".join(analytics_snapshot.diff_lines(9))
        self.assertIn("recommenders' target: engaged rate -> 7-day views", text)

    def test_ops_list_and_env_docs_name_the_switch(self):
        with open(".env.example", encoding="utf-8") as f:
            self.assertIn("RECOMMEND_TARGET=", f.read())


if __name__ == "__main__":
    unittest.main()
