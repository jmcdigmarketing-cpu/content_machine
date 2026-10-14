"""Wave 84 (#1153-#1157): the sign-in, a fact said twice, one paid number, real sources.

Seen on 2026-10-13: the YouTube sign-in expired at 7 days and the header kept saying "nothing
is sending uploads - py -m scripts.ops worker". The 6-day reminder (#974) existed and the
overnight report - the one thing read after a night away - never printed it. Run 136, rendered
that day, said one fact twice. `ops growth` said "paid: 0% of all views" while YouTube counted
4,544 paid Shorts views. 50 of 71 stored source links were images or ended in a quote.
"""

from __future__ import annotations

import inspect
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_signin_reminder import NOW, _TokenCase
from tests.test_upload_last_mile import LATE

# ---- #1153: an overdue upload names the real blocker ----------------------------------------


class OverdueWordingTests(unittest.TestCase):
    def _lines(self, signed_out):
        from core import job_queue

        with (
            patch.object(job_queue, "overdue_uploads", return_value=[LATE]),
            patch.object(job_queue, "_signed_out", return_value=signed_out),
        ):
            (line,) = job_queue.overdue_lines([LATE], "tapin")
            return line, job_queue.overdue_short([LATE], "tapin")

    def test_a_dead_sign_in_is_what_the_upload_waits_on(self):
        line, short = self._lines(True)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", line)
        self.assertNotIn("nothing is sending uploads", line)
        self.assertEqual(short, "1 upload overdue - sign in")

    def test_signed_in_it_is_still_the_worker(self):
        line, short = self._lines(False)
        self.assertIn("py -m scripts.ops worker", line)
        self.assertEqual(short, "1 upload overdue - ops worker")


class ShelfWordingTests(unittest.TestCase):
    def test_a_queued_render_waits_on_the_sign_in(self):
        from core import stale_renders

        run = SimpleNamespace(id=132, title="Topuria's outlook", mp4_path="")
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[run]),
            patch("publishing.go_public.unlisted_holds", return_value=[]),
            patch.object(stale_renders, "_queued_runs", return_value={132: LATE}),
            patch.object(stale_renders, "_signed_out", return_value=True),
        ):
            (row,) = stale_renders.shelf_rows("tapin")
        self.assertIn("sign-in", row["state"])
        self.assertEqual(row["command"], "py -m youtube.oauth_setup --channel tapin")

    def test_the_count_line_says_it_too(self):
        from core import stale_renders

        counts = {"renders": 1, "queued": 1, "stale": 0, "unlisted": 0, "claim": 0}
        with patch.object(stale_renders, "_signed_out", return_value=True):
            (line,) = stale_renders.shelf_lines("tapin", counts)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", line)
        self.assertNotIn("ops worker", line)


class SignedOutTests(unittest.TestCase):
    def test_the_suite_never_asks_youtube(self):
        from youtube.oauth import signed_out

        with patch("youtube.oauth.sign_in_status", side_effect=AssertionError("asked")):
            self.assertFalse(signed_out("tapin"))

    def test_a_refused_sign_in_is_signed_out(self):
        from youtube import oauth

        with (
            patch.object(oauth, "live_youtube_forbidden", return_value=False),
            patch.object(oauth, "sign_in_status", return_value="expired or been revoked"),
        ):
            self.assertTrue(oauth.signed_out("tapin"))
        with (
            patch.object(oauth, "live_youtube_forbidden", return_value=False),
            patch.object(oauth, "sign_in_status", return_value=""),
        ):
            self.assertFalse(oauth.signed_out("tapin"))


# ---- #1154: the expiry is said where it is read ---------------------------------------------


class ReminderTests(_TokenCase):
    def _reminder(self, days_old):
        from youtube.oauth import sign_in_reminder

        self._write(signed_in_at=(NOW - timedelta(days=days_old)).isoformat())
        env = {k: v for k, v in os.environ.items() if k != "SIGN_IN_REMINDER_DAYS"}
        with patch.dict(os.environ, env, clear=True):
            return sign_in_reminder("tapin")

    def test_day_five_gives_two_days_notice(self):
        """2026-10-13: signed in on 10-06 at 23:27 UTC, dead on 10-13. The reminder started on
        day 6 - one day's notice."""
        line = self._reminder(5.2)
        self.assertIn("5 days old", line)
        self.assertIn("about 2 days left", line)

    def test_day_four_says_nothing(self):
        self.assertEqual(self._reminder(4.5), "")

    def test_the_last_day_says_so(self):
        self.assertIn("less than a day left", self._reminder(6.4))


class OvernightSignInTests(unittest.TestCase):
    def test_the_report_says_the_sign_in_first(self):
        from core import overnight

        result = overnight.OvernightResult(channel_id="tapin", requested=3)
        result.sign_in_line = "YouTube sign-in for tapin has expired or been revoked - run: x"
        lines = overnight.render_overnight(result).splitlines()
        self.assertTrue(lines[2].startswith("Sign-in: YouTube sign-in for tapin has expired"))

    def test_a_working_sign_in_adds_no_line(self):
        from core import overnight

        result = overnight.OvernightResult(channel_id="tapin", requested=3)
        self.assertNotIn("Sign-in:", overnight.render_overnight(result))

    def test_overnight_reads_dead_before_due(self):
        from core import overnight
        from youtube import oauth

        with (
            patch.object(oauth, "live_youtube_forbidden", return_value=False),
            patch.object(oauth, "sign_in_status", return_value="dead"),
            patch.object(oauth, "sign_in_reminder", return_value="due"),
        ):
            self.assertEqual(overnight._sign_in_line("tapin"), "dead")
        with (
            patch.object(oauth, "live_youtube_forbidden", return_value=False),
            patch.object(oauth, "sign_in_status", return_value=""),
            patch.object(oauth, "sign_in_reminder", return_value="due"),
        ):
            self.assertEqual(overnight._sign_in_line("tapin"), "due")

    def test_the_suite_reads_nothing(self):
        from core import overnight

        self.assertEqual(overnight._sign_in_line("tapin"), "")

    def test_the_run_sets_the_line(self):
        from core import overnight

        self.assertIn("result.sign_in_line = _sign_in_line(", inspect.getsource(overnight))


# ---- #1155: a fact said twice ----------------------------------------------------------------

FIRST = "Houston has won three straight against Tennessee, including a shutout last season."
AGAIN = (
    "Houston has dominated this matchup, winning three straight, including a shutout last season."
)
RUN136 = (
    f"{FIRST} Houston has led in the fourth quarter in three of their four losses. This is a "
    "test of coaching adjustments and long-term identity for two struggling franchises. With "
    "C.J. Stroud's status uncertain, the Texans may lean on their run game and defense. The "
    f"Titans' 29th-ranked defense looks to capitalize. {AGAIN} The Texans' offense has been "
    "serviceable, but their defense has stumbled out of the gate. Tap in for more."
)


class SaidTwiceTests(unittest.TestCase):
    def test_run136_the_second_telling_is_found(self):
        from core.script_craft import said_twice

        self.assertEqual(said_twice(RUN136), [AGAIN])

    def test_two_facts_about_one_team_are_two_facts(self):
        from core.script_craft import said_twice

        script = (
            "Houston has won three straight against Tennessee in this building. Houston has "
            "led in the fourth quarter in three of their four losses this year."
        )
        self.assertEqual(said_twice(script), [])

    def test_a_short_refrain_is_not_a_fact(self):
        from core.script_craft import said_twice

        script = "That is the whole story. The line held all night. That is the whole story."
        self.assertEqual(said_twice(script), [])

    def test_run128_the_other_fighters_line_is_not_a_repeat(self):
        """Measured before the cut shipped: a looser rule called this a repeat."""
        from core.script_craft import said_twice

        script = (
            "Allen entered on a three-fight win streak, ranked sixth in the division. "
            "Duncan entered on a five-fight win streak, ranked twelfth in the division."
        )
        self.assertEqual(said_twice(script), [])

    def test_run131_a_callback_is_not_a_repeat(self):
        from core.script_craft import said_twice

        script = (
            "Ten turnovers, six picks, four fumbles - the Chargers are 0-4 for the first time "
            "since 2017. The line gave up nine sacks. That's how you go 0-4 for the first time "
            "since 2017."
        )
        self.assertEqual(said_twice(script), [])

    def test_run135_a_line_that_adds_a_fact_is_not_a_repeat(self):
        from core.script_craft import said_twice

        script = (
            "Green Bay's run game has no answer for that. Reports claim Green Bay's offensive "
            "line has cycled through combinations all season, and the run game has been the "
            "collateral damage."
        )
        self.assertEqual(said_twice(script), [])

    def test_the_finished_script_check_names_it(self):
        from core.script_craft import script_check, script_check_line

        check = script_check(script=RUN136, title="Texans at Titans")
        self.assertFalse(check["ok"])
        self.assertIn("1 thing said twice", check["why"])
        self.assertIn("said twice", script_check_line(check))

    def test_the_later_one_is_cut_when_the_length_holds(self):
        from core.script_craft import drop_repeats

        script, cut = drop_repeats(RUN136, min_words=40)
        self.assertEqual(cut, [AGAIN])
        self.assertNotIn(AGAIN, script)
        self.assertIn(FIRST, script)

    def test_a_script_at_its_minimum_keeps_both(self):
        from core.script_craft import drop_repeats

        script, cut = drop_repeats(RUN136, min_words=500)
        self.assertEqual((script, cut), (RUN136, []))

    def test_the_engine_runs_the_pass_and_lists_the_cut(self):
        from core import content_engine

        source = inspect.getsource(content_engine.generate_content_package)
        self.assertIn('"drop_repeats"', source)
        self.assertIn('cut_box["repeats"]', source)

    def test_the_recorded_rate_counts_it(self):
        from core.runs.script_report import _kind

        self.assertEqual(_kind("1 thing said twice"), "a thing said twice")


# ---- #1156: one paid number -------------------------------------------------------------------


def _row(i, *, lifetime, paid_days=(), paid_key=None, views=None):
    metrics = {
        "lifetime_views": lifetime,
        "daily_paid_views": [[f"2026-09-{20 + n}", count] for n, count in enumerate(paid_days)],
    }
    if paid_key is not None:
        metrics["paid_views"] = paid_key
    if views is not None:
        metrics["views"] = views
    return SimpleNamespace(
        id=i,
        content_run_id=100 + i,
        youtube_video_id=f"v{i}",
        detail=f"Video {i}",
        published_at=datetime(2026, 9, 1, 18, tzinfo=timezone.utc),
        metrics_json=json.dumps(metrics),
    )


class PaidNumberTests(unittest.TestCase):
    TODAY = datetime(2026, 10, 13, tzinfo=timezone.utc)

    def _report(self, rows, channel_paid=None):
        from analytics import growth

        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
        numbers = {"shorts_paid_90d": channel_paid} if channel_paid is not None else None
        with (
            patch("analytics.growth._repo", return_value=repo),
            patch("analytics.growth._today", return_value=self.TODAY),
            patch("core.ypp_readiness.load_ypp_numbers", return_value=numbers),
        ):
            return growth.report("tapin")

    def test_the_daily_paid_rows_are_counted(self):
        """Live: one video held 573 paid views in its daily rows and the report said 0%: it
        read `paid_views`, a key on 5 of 43 videos."""
        rep = self._report(
            [_row(1, lifetime=1152, paid_days=(109, 130, 334)), _row(2, lifetime=848)]
        )
        self.assertEqual(rep["paid"]["views"], 573)
        self.assertEqual(rep["paid"]["videos"], 1)
        self.assertAlmostEqual(rep["paid_share"], 573 / 2000, places=3)

    def test_the_stored_key_still_counts_when_it_is_the_larger(self):
        rep = self._report([_row(1, lifetime=1000, paid_days=(10,), paid_key=400, views=900)])
        self.assertEqual(rep["paid"]["views"], 400)

    def test_the_line_says_what_youtube_counts_beyond_these_videos(self):
        from analytics.growth import paid_line

        rep = self._report(
            [_row(1, lifetime=1152, paid_days=(109, 130, 334)), _row(2, lifetime=848)],
            channel_paid=4544,
        )
        line = paid_line(rep)
        self.assertIn("573 paid views on 1 of 2 videos", line)
        self.assertIn("YouTube counts 4,544 paid Shorts views in 90 days", line)
        self.assertIn("3,971", line)

    def test_no_ads_is_said_plainly(self):
        from analytics.growth import paid_line

        self.assertEqual(paid_line(self._report([_row(1, lifetime=500)])), "paid: none")

    def test_the_report_prints_the_line(self):
        from analytics import growth

        source = inspect.getsource(growth.render)
        self.assertIn("paid_line(rep)", source)
        self.assertNotIn("of all views", source)


# ---- #1157: only real sources ----------------------------------------------------------------


class RealSourceTests(unittest.TestCase):
    JUNK = (
        'lastfm data: {"url": "https://www.last.fm/music/Chicago+Bears/_/Superbowl+Shuffle", '
        '"image": "https://lastfm-img.freetls.fastly.net/i/u/34s/2a96.png"} '
        'coingecko data: {"thumb": "https://coin-images.coingecko.com/coins/images/20612/thumb/GN.jpg"} '
        "twitch art https://static-cdn.jtvnw.net/ttv-boxart/509672-{width}x{height}.jpg "
        "story (https://www.espn.com/nba/story/_/id/123/cavs-beat-magic)."
    )

    def test_links_are_read_without_the_punctuation_around_them(self):
        from core.source_diversity import urls_from_text

        self.assertEqual(
            urls_from_text(self.JUNK),
            [
                "https://www.last.fm/music/Chicago+Bears/_/Superbowl+Shuffle",
                "https://www.espn.com/nba/story/_/id/123/cavs-beat-magic",
            ],
        )

    def test_a_picture_is_not_a_source(self):
        from core.source_diversity import is_page_url

        for url in (
            "https://coin-images.coingecko.com/coins/images/20612/large/GN_UVm3d_400x400.jpg",
            "https://static-cdn.jtvnw.net/ttv-boxart/32",
            "https://static-cdn.jtvnw.net/ttv-boxart/509672-{width}x{height}.jpg",
            "https://lastfm-img.freetls.fastly.net/i/u/34s/2a96.png",
        ):
            self.assertFalse(is_page_url(url), url)
        self.assertTrue(is_page_url("https://www.espn.com/nba/story/_/id/123/cavs-beat-magic"))

    def test_the_correction_scan_skips_what_was_stored_before(self):
        """50 of 71 stored links were of this kind; the scan warned six times a night."""
        from core import correction_dossier

        run = SimpleNamespace(
            features_json=json.dumps(
                {
                    "claim_verification": {"claims": [{"claim": "x", "supported": True}]},
                    "source_urls": [
                        'https://coin-images.coingecko.com/coins/images/1/thumb/a.jpg"',
                        'https://www.last.fm/music/Agust+D/_/People"',
                        "https://www.espn.com/nba/story/_/id/123/cavs-beat-magic",
                    ],
                }
            )
        )
        _claims, sources = correction_dossier._claims_and_sources(run)
        self.assertEqual(
            sources,
            [
                "https://www.last.fm/music/Agust+D/_/People",
                "https://www.espn.com/nba/story/_/id/123/cavs-beat-magic",
            ],
        )


if __name__ == "__main__":
    unittest.main()


class MarkupTests(unittest.TestCase):
    """Found scanning for a stray control character: the pattern that removes script and
    style blocks held a backspace where a word boundary was meant, and had never matched."""

    def test_script_and_style_blocks_are_not_article_text(self):
        from core.correction_dossier import strip_markup

        page = (
            "<style>.retracted { color: red }</style><script>var corrected = 1;</script>"
            "<p>The Cavaliers won.</p>"
        )
        text = strip_markup(page)
        self.assertIn("The Cavaliers won.", text)
        self.assertNotIn("corrected", text)
        self.assertNotIn("retracted", text)

    def test_no_source_file_holds_a_control_character(self):
        """A heredoc turns a backslash-b into a backspace without a word. Twice now."""
        import glob

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        held = []
        for pattern in ("core/**/*.py", "apis/**/*.py", "analytics/**/*.py", "youtube/**/*.py",
                        "scripts/**/*.py", "publishing/**/*.py", "video/**/*.py", "main.py"):  # fmt: skip
            for path in glob.glob(os.path.join(root, pattern), recursive=True):
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                if any(ord(ch) < 32 and ch not in "\n\r\t\f" for ch in text):
                    held.append(os.path.relpath(path, root))
        self.assertEqual(held, [])


# ---- #1158: an angle keeps no lens name -------------------------------------------------------


class LensNameTests(unittest.TestCase):
    def _angles(self, raw):
        from apis.topic_variants import _clean_angle_lines

        return _clean_angle_lines(raw, [], topic="NBA preseason")

    def test_run142_the_lens_name_is_not_part_of_the_angle(self):
        (angle,) = self._angles(
            'Factual read: "NBA Finals and Awards Predictions: A Season in Preview'
        )
        self.assertEqual(angle, "NBA Finals and Awards Predictions: A Season in Preview")

    def test_run137_what_changed(self):
        (angle,) = self._angles(
            "What Changed: Can Cleveland's Recent Roster Moves Help Turn Around Their Season?"
        )
        self.assertEqual(
            angle, "Can Cleveland's Recent Roster Moves Help Turn Around Their Season?"
        )

    def test_a_shortened_lens_name_goes_too(self):
        (angle,) = self._angles("Forward look: where the Spurs go from here")
        self.assertEqual(angle, "where the Spurs go from here")

    def test_a_subject_before_a_colon_stays(self):
        raw = "Chargers Hopeium: Herbert's deep ball is back"
        self.assertEqual(self._angles(raw), [raw])
