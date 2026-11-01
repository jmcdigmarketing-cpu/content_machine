"""Wave 140 (2026-11-01) - the next five (decision 92), S02 the shortfall it takes.

#1699 (S02) a true reason to follow at the end of each format that has one; #1936 a recap draft
gets one rewrite before review and review shows what recaps earn - and S06 reads with today's
detector; #1930 a crosspost round that cannot read YouTube says so; #1932 a frame cover is kept
beside the run's thumbnails, past the 3-day sweep; #1933 a retired render records why, so S03 can
be read.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.test_buffer_crosspost import CrosspostCase

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)


def _bet(source: str, **extra) -> dict:
    return {"offered": [{"topic": "t", "source": source}], "picked": 1, **extra}


# ---- #1699 (S02): a true reason to follow -------------------------------------------------------


class FollowReasonTests(unittest.TestCase):
    def test_a_countdown_names_tomorrows_day(self):
        from core.batch_generation import follow_brief

        brief = follow_brief(_bet("countdown", title_stem="GTA 6: 19 days to launch"))
        self.assertIn("18 days to go", brief)
        self.assertIn("every day until launch", brief)
        last = follow_brief(_bet("countdown", title_stem="GTA 6: 1 day to launch"))
        self.assertIn("out tomorrow", last)

    def test_a_long_video_names_the_weekly_show(self):
        from core.batch_generation import follow_brief

        brief = follow_brief(_bet("long", draft_kind="long"))
        self.assertIn("Week in Review", brief)
        self.assertIn("every Monday", brief)

    def test_a_launch_moment_while_the_countdown_runs(self):
        from core.batch_generation import follow_brief

        rows = [{"kind": "countdown", "subject": "GTA 6", "until": "2026-11-19"}]
        with patch("core.series.countdown.series_rows", return_value=rows):
            during = follow_brief(_bet("moment"), today=date(2026, 11, 12))
            after = follow_brief(_bet("moment"), today=date(2026, 11, 21))
        self.assertIn("GTA 6", during)
        self.assertIn("every day until launch", during)
        self.assertEqual(after, "")

    def test_anything_else_gets_no_line(self):
        from core.batch_generation import follow_brief

        self.assertEqual(follow_brief(_bet("trending")), "")
        self.assertEqual(follow_brief(None), "")

    def test_the_draft_carries_it(self):
        import inspect

        from core import batch_generation

        source = inspect.getsource(batch_generation.generate_draft)
        self.assertIn("follow_brief(best_bet", source)


# ---- #1936: a recap draft rewritten once; review shows the cost; S06 reads today's detector ------


class RecapTests(unittest.TestCase):
    def test_a_recap_draft_gets_one_rewrite(self):
        from core import batch_generation as bg

        with (
            patch("core.authenticity.has_insight", side_effect=lambda s: "watch whether" in s.lower()),
            patch("core.content_engine.insight_pass",
                  return_value=("Recap. Watch whether he holds.", {"insight_tries": 1})) as one,
        ):  # fmt: skip
            script, record = bg.recap_rewrite("Recap only.", ["fact"], "topic", intent="news")
        self.assertEqual(script, "Recap. Watch whether he holds.")
        self.assertEqual(record, {"tried": True, "kept": True, "insight_tries": 1})
        self.assertEqual(one.call_count, 1)

    def test_a_script_with_a_take_is_left(self):
        from core import batch_generation as bg

        with (
            patch("core.authenticity.has_insight", return_value=True),
            patch("core.content_engine.insight_pass") as one,
        ):
            script, record = bg.recap_rewrite("Watch whether it holds.", [], "topic")
        self.assertEqual((script, record), ("Watch whether it holds.", {}))
        one.assert_not_called()

    def test_a_refused_rewrite_keeps_the_script_and_says_so(self):
        from core import batch_generation as bg

        with (
            patch("core.authenticity.has_insight", return_value=False),
            patch("core.content_engine.insight_pass",
                  return_value=("Recap only.", {"insight_rejected": ["no take"]})),
        ):  # fmt: skip
            script, record = bg.recap_rewrite("Recap only.", [], "topic")
        self.assertEqual(script, "Recap only.")
        self.assertFalse(record["kept"])

    def test_the_draft_runs_it_before_its_verdict(self):
        import inspect

        from core import batch_generation as bg

        source = inspect.getsource(bg.generate_draft)
        self.assertIn("recap_rewrite(", source)
        self.assertLess(source.index("recap_rewrite("), source.index("evaluate_authenticity("))

    def test_the_rewrite_is_on_unless_switched_off(self):
        import inspect

        from core import batch_generation as bg

        with patch.dict("os.environ", {}):
            os.environ.pop("RECAP_REWRITE", None)
            self.assertTrue(bg._recap_rewrite_enabled())
        with patch.dict("os.environ", {"RECAP_REWRITE": "false"}):
            self.assertFalse(bg._recap_rewrite_enabled())
        self.assertIn("_recap_rewrite_enabled()", inspect.getsource(bg.generate_draft))

    def test_the_cost_line_says_too_few_under_five(self):
        from core import batch_review

        rows = [(True, 63), (True, 70), (False, 56), (False, 40), (False, 50)] + [(True, 80)] * 30
        with patch.object(batch_review, "_recap_rows", return_value=rows):
            batch_review.recap_cost_line.cache_clear()
            line = batch_review.recap_cost_line("tapin")
        self.assertIn("3 recaps", line)
        self.assertIn("too few", line)
        rows = [(False, 40)] * 6 + [(True, 80)] * 30
        with patch.object(batch_review, "_recap_rows", return_value=rows):
            batch_review.recap_cost_line.cache_clear()
            line = batch_review.recap_cost_line("tapin")
        self.assertIn("median 40 organic views", line)
        self.assertIn("80 with a take", line)
        batch_review.recap_cost_line.cache_clear()

    def test_review_prints_it_for_a_recap(self):
        import inspect

        from core import batch_review

        self.assertIn("recap_cost_line(", inspect.getsource(batch_review))

    def test_s06_reads_the_script_with_todays_detector(self):
        from core.success import shortfalls as sf

        rows = [SimpleNamespace(content_run_id=i, privacy_status="public", metrics_json="{}",
                                published_at=NOW - timedelta(days=3)) for i in (1, 2, 3)]  # fmt: skip
        scripts = {1: "A recap.", 2: "Watch whether he holds.", 3: None}
        verdicts = {1: "review", 2: "review", 3: "review"}
        with (
            patch.object(sf, "_public_rows", return_value=rows),
            patch.object(sf, "_saved_script", side_effect=lambda rid: scripts[rid]),
            patch.object(sf, "_run", side_effect=lambda rid: SimpleNamespace(
                quality_json=json.dumps({"authenticity_verdict": verdicts[rid]}))),
            patch("core.authenticity.has_insight", side_effect=lambda s: "watch whether" in s.lower()),
        ):  # fmt: skip
            got = sf.reading("S06", "tapin", now=NOW)
        self.assertIn("2 of 3", got.today)  # run 1 by today's detector, run 3 by its stored verdict


# ---- #1930: a round that cannot read YouTube says so ---------------------------------------------


class YouTubeUnreadTests(CrosspostCase):
    def test_the_round_says_youtube_was_not_read(self):
        from publishing.crosspost import send_due

        with patch("publishing.crosspost._held_by_youtube", return_value=None):
            send_due("tapin")
            self.public.append((113, "yt113"))
            lines = send_due("tapin")
        self.assertTrue(any("YouTube could not be read" in line for line in lines), lines)
        self.assertEqual(self.create.call_count, 2)  # the record's slot has passed - it goes

    def test_a_failed_read_is_none_not_empty(self):
        from publishing import crosspost

        with (
            patch("youtube.oauth.live_youtube_forbidden", return_value=False),
            patch("analytics.privacy_sync._service", side_effect=RuntimeError("signed out")),
        ):
            self.assertIsNone(crosspost._held_by_youtube("tapin", {113: "yt113"}))
        self.assertEqual(crosspost._held_by_youtube("tapin", {}), {})


# ---- #1932: the cover kept beside the run's thumbnails -------------------------------------------


class KeepCoverTests(unittest.TestCase):
    def test_the_cover_is_copied_into_the_channels_thumbnails(self):
        from assets.cover_frames import SUFFIX, keep_cover

        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "tmp", "fastcut_abc" + SUFFIX)
            os.makedirs(os.path.dirname(source))
            with open(source, "wb") as f:
                f.write(b"jpg")
            thumbs = os.path.join(tmp, "thumbnails")
            with patch("core.output_paths.ensure_channel_output_dirs",
                       return_value={"thumbnails": thumbs}):  # fmt: skip
                kept = keep_cover(source, "tapin", 219)
            self.assertTrue(kept.endswith(SUFFIX))
            self.assertEqual(os.path.dirname(kept), thumbs)
            self.assertIn("run219", os.path.basename(kept))
            with open(kept, "rb") as f:
                self.assertEqual(f.read(), b"jpg")
            self.assertEqual(keep_cover(os.path.join(tmp, "missing.jpg"), "tapin", 219), "")

    def test_the_strip_does_not_list_the_kept_copys_own_original(self):
        from assets import cover_frames

        rows = [{"hash": "0" * 16, "path": "C:/tmp/fastcut_abc_frame_cover.jpg"},
                {"hash": "f" * 16, "path": "C:/tmp/fastcut_xyz_frame_cover.jpg"}]  # fmt: skip
        image = MagicMock()
        image.__enter__.return_value = image
        with (
            patch.object(cover_frames, "used_covers", return_value=rows),
            patch("PIL.Image.open", return_value=image),
            patch.object(cover_frames, "dhash", return_value=0),
        ):
            lines = cover_frames.strip_lines("C:/out/thumbnails/run219-fastcut_abc_frame_cover.jpg")
        self.assertEqual(len(lines), 2)  # the head and fastcut_xyz only
        self.assertIn("fastcut_xyz", lines[1])

    def test_the_render_keeps_it(self):
        import inspect

        from core import pipeline

        self.assertIn("keep_cover(", inspect.getsource(pipeline.run_media_only))


# ---- #1933: a retired render records why --------------------------------------------------------


class RetireWhyTests(unittest.TestCase):
    def test_each_retirement_records_why(self):
        from core import stale_renders

        written = []
        with patch.object(stale_renders, "merge_features",
                          side_effect=lambda rid, data: written.append((rid, data))):  # fmt: skip
            stale_renders.retire_renders([SimpleNamespace(id=7)], why="wrong")
            stale_renders.retire_renders([SimpleNamespace(id=8)])
        self.assertEqual(written[0][1]["retired_why"], "wrong")
        self.assertEqual(written[1][1]["retired_why"], "by hand")

    def test_a_dead_render_is_past_its_game_and_the_command_takes_why(self):
        import inspect

        from core import stale_renders
        from scripts import ops

        self.assertIn('why="past its game"', inspect.getsource(stale_renders.retire_dead_renders))
        self.assertIn("why=", inspect.getsource(ops.cmd_retire_renders))

    def test_s03_counts_the_wrong_ones(self):
        from core.success import shortfalls as sf

        def run(rid, why, days_ago):
            stamp = (NOW - timedelta(days=days_ago)).isoformat()
            return SimpleNamespace(
                id=rid, features_json=json.dumps({"retired_at": stamp, "retired_why": why})
            )

        runs = [run(1, "wrong", 2), run(2, "past its game", 1), run(3, "wrong", 40)]
        with patch("storage.repositories.content_runs.get_content_run_repository") as repo:
            repo.return_value.list_for_channel.return_value = runs
            got = sf.reading("S03", "tapin", now=NOW)
            self.assertEqual(got.status, sf.NOT_YET)
            self.assertIn("1 render retired as wrong", got.today)
            repo.return_value.list_for_channel.return_value = runs[1:2]
            self.assertEqual(sf.reading("S03", "tapin", now=NOW).status, sf.WAITING)
            later = NOW + timedelta(days=40)
            self.assertEqual(sf.reading("S03", "tapin", now=later).status, sf.MET)


if __name__ == "__main__":
    unittest.main()
