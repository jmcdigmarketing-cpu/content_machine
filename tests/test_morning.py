"""Wave 82: a morning command, and monetization numbers that are true.

Operator, 2026-10-11: "why is morning review not in ops all?" and "how can it ... get closer
to monetization". Read that day:

- `ops all` is the weekly batch (checks, analytics, the weekly review). `batch-review` was in
  no batch and `daily-brief` did not call it, so the review of last night's drafts ran only
  when typed. The operator chose a new `ops morning`; `ops all` stays weekly (#1140).
- `ops ypp` had said 0 Shorts views and 0 long-form hours since it was added. YouTube's
  documentation writes the content type `SHORTS` / `VIDEO_ON_DEMAND`; its responses write
  `shorts` / `videoOnDemand`, and the code compared with the documented spelling (#1147).
  Real: 6,273 Shorts views in 90 days, about 10 long-form hours in a year, 69 subscribers.
- Nothing said how far the bar is at the current pace (#1144), which videos brought a
  subscriber (#1146), or that the newest video's "0 views" meant "not measured" (#1137).
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

TODAY = date(2026, 10, 11)


def _args(**kw):
    from scripts.ops import build_parser

    args = build_parser().parse_args(["list"])
    for k, v in kw.items():
        setattr(args, k, v)
    return args


# ---- #1140: `ops morning` ----------------------------------------------------------------


class MorningBatchTests(unittest.TestCase):
    def test_the_morning_batch_and_its_steps(self):
        from scripts import ops

        self.assertIn("morning", ops.BATCHES)
        self.assertEqual(
            ops.batch_leaves("morning"),
            [
                "sync-metrics",
                "crosspost-send",
                "overnight-last",
                "shelf",
                "corrections-open",
                "batch-review",
            ],
        )

    def test_ops_all_ends_with_the_morning(self):
        # Was "ops all stays weekly" (#1140); the operator, 2026-10-15, wanted the morning in
        # `all` (#1204).
        from scripts import ops

        self.assertEqual(ops.batch_leaves("all")[-1], "batch-review")

    def test_the_draft_review_without_a_console_says_how_to_run_it(self):
        from scripts.ops import COMMANDS

        with (
            patch("sys.stdin.isatty", return_value=False),
            patch("core.batch_review.review_drafts") as review,
            patch("core.batch_review.drafts_line", return_value="Drafts waiting: 4 - 4 need you"),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = COMMANDS["batch-review"][1](_args(_batch=True, channel="tapin"))
        self.assertEqual(code, 0)
        review.assert_not_called()
        self.assertIn("py -m scripts.ops batch-review --channel tapin", out.getvalue())
        self.assertIn("Drafts waiting: 4", out.getvalue())

    def test_typed_directly_the_review_runs(self):
        from core.batch_review import ReviewSummary
        from scripts.ops import COMMANDS

        with (
            patch("sys.stdin.isatty", return_value=False),
            patch("core.batch_review.review_drafts", return_value=ReviewSummary()) as review,
            redirect_stdout(io.StringIO()),
        ):
            COMMANDS["batch-review"][1](_args(channel="tapin"))
        review.assert_called_once()


class ConsoleTests(unittest.TestCase):
    """Found running `ops morning` from a shell with no console, 2026-10-11: Windows calls the
    NUL device a terminal, so the review started and died on its first question."""

    def test_the_nul_device_is_not_a_console(self):
        from scripts import ops

        with patch("sys.stdin.isatty", return_value=True):
            with patch.object(ops, "_real_console", return_value=False):
                self.assertFalse(ops._has_console())
            with patch.object(ops, "_real_console", return_value=True):
                self.assertTrue(ops._has_console())
        with patch("sys.stdin.isatty", return_value=False):
            self.assertFalse(ops._has_console())

    def test_the_review_is_skipped_when_the_terminal_is_nul(self):
        from scripts import ops

        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ops, "_real_console", return_value=False),
            patch("core.batch_review.review_drafts") as review,
            patch("core.batch_review.drafts_line", return_value=""),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = ops.COMMANDS["batch-review"][1](_args(_batch=True, channel="tapin"))
        self.assertEqual(code, 0)
        review.assert_not_called()
        self.assertIn("in a console", out.getvalue())

    def test_a_question_nobody_answers_is_not_a_crash(self):
        from scripts import ops

        with (
            patch.object(ops, "_has_console", return_value=True),
            patch("core.batch_review.review_drafts", side_effect=EOFError()),
            patch("core.batch_review.drafts_line", return_value=""),
            redirect_stdout(io.StringIO()) as out,
        ):
            in_batch = ops.COMMANDS["batch-review"][1](_args(_batch=True, channel="tapin"))
            typed = ops.COMMANDS["batch-review"][1](_args(channel="tapin"))
        self.assertEqual((in_batch, typed), (0, 1))
        self.assertIn("got no answer", out.getvalue())


class OvernightLastTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2026, 10, 12, 8, 0)

    def _draft(self, run_id, *, review=None):
        folder = os.path.join(self.tmp.name, f"draft_{run_id:04d}")
        os.makedirs(folder)
        meta = {"run_id": run_id, "title": f"Title {run_id}", "topic": f"Topic {run_id}"}
        if review is not None:
            meta["review"] = review
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh)

    def _at(self, hours_ago):
        return (self.now - timedelta(hours=hours_ago)).isoformat(timespec="seconds")

    def test_only_what_overnight_rendered_lately(self):
        from core.batch_review import overnight_rendered

        self._draft(136, review={"decision": "rendered", "by": "overnight", "at": self._at(3)})
        self._draft(123, review={"decision": "rendered", "by": "overnight", "at": self._at(4)})
        self._draft(90, review={"decision": "rendered", "by": "overnight", "at": self._at(200)})
        self._draft(140, review={"decision": "rendered", "at": self._at(2)})  # the operator's yes
        self._draft(141)
        got = overnight_rendered("tapin", root=self.tmp.name, now=self.now)
        self.assertEqual([row["run_id"] for row in got], [136, 123])
        self.assertEqual(got[0]["title"], "Title 136")

    def test_each_one_with_where_it_is_now(self):
        from core.batch_review import overnight_rendered_lines

        self._draft(136, review={"decision": "rendered", "by": "overnight", "at": self._at(3)})
        self._draft(123, review={"decision": "rendered", "by": "overnight", "at": self._at(4)})
        shelf = [
            {
                "run_id": 136,
                "title": "Title 136",
                "state": "unlisted on YouTube",
                "command": "py -m scripts.ops go-public abc123 --channel tapin --apply",
            }
        ]
        with patch("core.stale_renders.shelf_rows", return_value=shelf):
            text = "\n".join(overnight_rendered_lines("tapin", root=self.tmp.name, now=self.now))
        self.assertIn("rendered 2", text)
        self.assertIn("run 136  Title 136", text)
        self.assertIn("go-public abc123", text)
        self.assertIn("run 123", text)
        self.assertIn("not on the shelf", text)

    def test_a_night_with_no_render_says_so(self):
        from core.batch_review import overnight_rendered_lines

        self._draft(141)
        with patch("core.stale_renders.shelf_rows", return_value=[]):
            lines = overnight_rendered_lines("tapin", root=self.tmp.name, now=self.now)
        self.assertIn("nothing rendered", lines[0])

    def test_the_command_prints_it(self):
        from scripts.ops import COMMANDS

        with (
            patch("core.batch_review.overnight_rendered_lines", return_value=["Overnight - x"]),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = COMMANDS["overnight-last"][1](_args(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("Overnight - x", out.getvalue())


# ---- #1147: content types the way YouTube writes them --------------------------------------


class _Service:
    """`service.reports().query(**kw).execute()` answering by the query's metric."""

    def __init__(self, by_metric):
        self.by_metric = by_metric
        self.queries: list[dict] = []

    def reports(self):
        return self

    def query(self, **kw):
        self.queries.append(kw)
        self._last = kw
        return self

    def execute(self):
        return self.by_metric.get(self._last["metrics"], {})


def _table(metric, rows):
    return {
        "columnHeaders": [
            {"name": "insightTrafficSourceType"},
            {"name": "creatorContentType"},
            {"name": metric},
        ],
        "rows": rows,
    }


class ContentTypeTests(unittest.TestCase):
    def _numbers(self, by_metric):
        from analytics import youtube_metrics

        service = _Service(by_metric)
        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
            patch.object(youtube_metrics, "_subscriber_count", return_value=69),
        ):
            return youtube_metrics.fetch_ypp_numbers(channel_id="tapin", today=TODAY), service

    def test_the_spelling_youtube_sends_is_counted(self):
        views = _table(
            "views",
            [
                ["ADVERTISING", "shorts", 3700],
                ["SHORTS", "shorts", 900],
                ["YT_SEARCH", "shorts", 204],
                ["YT_SEARCH", "videoOnDemand", 542],
            ],
        )
        minutes = _table(
            "estimatedMinutesWatched",
            [
                ["ADVERTISING", "videoOnDemand", 6000],
                ["YT_SEARCH", "videoOnDemand", 1800],
                ["SHORTS", "shorts", 900],
                ["SUBSCRIBER", "liveStream", 600],
            ],
        )
        numbers, _service = self._numbers({"views": views, "estimatedMinutesWatched": minutes})
        self.assertEqual(numbers["shorts_views_90d"], 1104)
        self.assertEqual(numbers["shorts_paid_90d"], 3700)
        self.assertEqual(numbers["long_hours_365d"], 40.0)

    def test_the_pace_numbers_come_with_them(self):
        views = _table("views", [["SHORTS", "shorts", 1952], ["ADVERTISING", "shorts", 400]])
        subs = {
            "columnHeaders": [{"name": "subscribersGained"}, {"name": "subscribersLost"}],
            "rows": [[5, 3]],
        }
        numbers, service = self._numbers(
            {"views": views, "subscribersGained,subscribersLost": subs}
        )
        self.assertEqual(numbers["shorts_views_28d"], 1952)
        self.assertEqual(numbers["subs_net_28d"], 2)
        self.assertEqual(numbers["pace_days"], 28)
        starts = {q["startDate"] for q in service.queries}
        self.assertIn((TODAY - timedelta(days=28)).isoformat(), starts)

    def test_a_failed_subscriber_read_leaves_the_key_out(self):
        numbers, _service = self._numbers({"views": _table("views", [["SHORTS", "shorts", 10]])})
        self.assertNotIn("subs_net_28d", numbers)


# ---- #1144: the path, at the current pace --------------------------------------------------


REAL = {
    "as_of": "2026-10-11",
    "subscribers": 69,
    "shorts_views_90d": 6273,
    "long_hours_365d": 10.0,
    "shorts_views_28d": 1952,
    "subs_net_28d": 2,
    "pace_days": 28,
}


class PathTests(unittest.TestCase):
    def test_years_are_called_years(self):
        from core.ypp_readiness import path_lines

        text = "\n".join(path_lines(REAL))
        self.assertIn("+0.5 a week", text)
        self.assertIn("931 to go", text)
        self.assertIn("about 36 years", text)
        # 10,000,000 in 90 days is a weekly rate, not a total to save up for.
        self.assertIn("777,778 a week", text)
        self.assertIn("488 a week", text)
        self.assertIn("0.06%", text)
        self.assertIn("77 hours a week", text)

    def test_no_net_subscribers_is_never(self):
        from core.ypp_readiness import path_lines

        text = "\n".join(path_lines({**REAL, "subs_net_28d": 0}))
        self.assertIn("never", text)

    def test_a_closer_bar_reads_in_months_or_weeks(self):
        from core.ypp_readiness import path_lines

        self.assertIn("about 9 months", "\n".join(path_lines({**REAL, "subs_net_28d": 96})))
        self.assertIn(
            "about 4 weeks",
            "\n".join(path_lines({**REAL, "subscribers": 900, "subs_net_28d": 100})),
        )

    def test_numbers_stored_before_the_pace_have_no_path(self):
        from core.ypp_readiness import path_lines

        self.assertEqual(path_lines({"subscribers": 69, "shorts_views_90d": 0}), [])

    def test_ops_ypp_prints_the_path(self):
        from core.ypp_readiness import inspect_ypp, render_report

        report = inspect_ypp(
            "tapin", disclosure="d", cadence=SimpleNamespace(total=0, cap=5), numbers=REAL
        )
        text = render_report(report)
        self.assertIn("At the pace of the last 28 days", text)
        self.assertIn("about 36 years", text)

    def test_a_pace_ads_may_have_bought_says_so(self):
        """Live, 2026-10-13: `ops ypp` printed "+16.0 a week ... about 13 months" under
        "ads excluded". The channel gained 64 in 28 days, its 43 videos account for 2, and
        YouTube counts 4,544 paid Shorts views. Both paces are said, and which is which."""
        from core.ypp_readiness import path_lines

        numbers = {**REAL, "subs_net_28d": 64, "shorts_paid_90d": 4544}
        text = "\n".join(path_lines(numbers, from_videos={"total": 2, "videos": 43}))
        self.assertIn("+16.0 a week", text)
        self.assertIn("about 13 months", text)
        self.assertIn("2 of the 64", text)
        self.assertIn("4,544 paid", text)
        self.assertIn("while the ads run", text)
        self.assertIn("about 36 years", text)
        self.assertIn("spend add", text)

    def test_videos_that_brought_none_are_never(self):
        from core.ypp_readiness import path_lines

        numbers = {**REAL, "subs_net_28d": 64, "shorts_paid_90d": 4544}
        text = "\n".join(path_lines(numbers, from_videos={"total": 0, "videos": 43}))
        self.assertIn("never reached", text)

    def test_no_ads_no_second_pace(self):
        from core.ypp_readiness import path_lines

        text = "\n".join(path_lines(REAL, from_videos={"total": 2, "videos": 43}))
        self.assertNotIn("while the ads run", text)

    def test_the_heading_does_not_call_the_subscriber_pace_ad_free(self):
        from core.ypp_readiness import inspect_ypp, render_report

        report = inspect_ypp(
            "tapin", disclosure="d", cadence=SimpleNamespace(total=0, cap=5), numbers=REAL
        )
        text = render_report(report)
        self.assertNotIn("At the current pace (ads excluded)", text)
        shorts = next(line for line in text.splitlines() if "Shorts path" in line)
        self.assertIn("ads excluded", shorts)

    def test_ops_ypp_reads_what_the_videos_brought(self):
        from core.ypp_readiness import inspect_ypp

        numbers = {**REAL, "subs_net_28d": 64, "shorts_paid_90d": 4544}
        with (
            patch("core.ypp_readiness.load_ypp_numbers", return_value=numbers),
            patch("core.ypp_readiness._video_subscribers", return_value={"total": 2, "videos": 43}),
        ):
            report = inspect_ypp("tapin", disclosure="d", cadence=SimpleNamespace(total=0, cap=5))
        self.assertIn("2 of the 64", "\n".join(report.path))


# ---- #1146: subscribers per video ----------------------------------------------------------


def _video(i, views, subs):
    published = datetime(2026, 10, 1, 18, tzinfo=timezone.utc) - timedelta(days=i)
    metrics = {"views": views, "paid_views": 0, "subscribers_gained": subs}
    return SimpleNamespace(
        id=i,
        content_run_id=100 + i,
        youtube_video_id=f"v{i}",
        detail=f"Video {i}",
        published_at=published,
        metrics_json=json.dumps(metrics),
    )


class SubscribersPerVideoTests(unittest.TestCase):
    def _report(self, rows):
        from analytics.growth import report

        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
        with (
            patch("analytics.growth._repo", return_value=repo),
            patch("analytics.growth._today", return_value=TODAY),
        ):
            return report("tapin")

    def test_which_videos_brought_any(self):
        from analytics.growth import subscriber_line

        rep = self._report([_video(0, 300, 0), _video(1, 968, 1), _video(2, 120, 2)])
        subs = rep["subscribers"]
        self.assertEqual((subs["total"], subs["videos_with"], subs["videos"]), (3, 2, 3))
        self.assertEqual(subs["top"][0]["subs"], 2)
        line = subscriber_line(rep)
        self.assertIn("3 from 3 videos", line)
        self.assertIn("2 brought any", line)
        self.assertIn("120 views", line)

    def test_none_yet_says_none(self):
        from analytics.growth import subscriber_line

        rep = self._report([_video(0, 300, 0), _video(1, 200, 0)])
        self.assertIn("none of 2 videos", subscriber_line(rep))


# ---- #1137: "0 views" that means "not measured" --------------------------------------------


class LastVideoTests(unittest.TestCase):
    def _last(self, metrics):
        from core import status

        row = SimpleNamespace(
            id=1,
            youtube_video_id="abc",
            published_at="2026-10-10T16:39:31",
            detail="",
            metrics_json=json.dumps(metrics),
        )
        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: [row])
        with (
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=repo,
            ),
            patch("storage.repositories.publish_log.is_seeded", return_value=False),
        ):
            return status._hdr_last("tapin")

    def test_a_video_with_no_window_yet_is_not_zero(self):
        self.assertEqual(self._last({}), "last video not measured yet")

    def test_the_lifetime_count_is_used_when_it_is_all_there_is(self):
        got = self._last({"lifetime_views": 12, "lifetime_views_at": "2026-10-11"})
        self.assertEqual(got, "last video 12 views so far")

    def test_a_measured_window_reads_as_before(self):
        self.assertEqual(self._last({"views": 500, "paid_views": 20}), "last video 480 views")

    def test_a_measured_zero_is_still_zero(self):
        self.assertEqual(self._last({"views": 0, "paid_views": 0}), "last video 0 views")


if __name__ == "__main__":
    unittest.main()
