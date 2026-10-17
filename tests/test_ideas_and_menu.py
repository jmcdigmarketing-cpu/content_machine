"""Wave 90 (#1191-#1193): what the operator raised on 2026-10-14.

Pasted from their terminal that evening: every best bet was a game ("ideas are only game
previews" - this week's games went in first and filled all five); "i dont know how to see or
access overnight uploads"; and python-dotenv warning that it "could not parse" lines of `.env`
without saying which or what to do (lines 35-36 begin "Client" - not NAME=value).
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

# ---- #1191: at most 2 of 5 best bets are games ----------------------------------------------------


def _bet(topic, source="trending"):
    from core.best_bet import BestBetResult

    return BestBetResult(topic=topic, domain="nfl" if source == "schedule" else "gaming",
                         avg_engaged_rate=0.0, source=source, supporting_runs=0, rationale="")  # fmt: skip


class GameShareTests(unittest.TestCase):
    """#1191 capped games at 2 of 5; #1244 (2026-10-16) made them compete in their league's
    slot instead - the reserved-slot tests went with `with_games`."""

    def test_the_live_list_of_2026_10_14(self):
        from core.best_bet import get_best_bets

        entries = [
            {"topic": "old ufc topic", "engaged_rate": 0.39, "composite_score": 60, "domain": "ufc"},
            {"topic": "old gaming topic", "engaged_rate": 0.25, "composite_score": 50,
             "domain": "gaming"},
        ]  # fmt: skip
        fresh = [
            {"topic": "Gaethje turns top 10 P4P", "domain": "ufc", "source": "ESPN MMA"},
            {"topic": "New roguelike hits Steam", "domain": "gaming", "source": "IGN"},
        ]
        games = [(f"Team {i} at Team {i + 10}", "nfl") for i in range(7)]
        with (
            patch("core.best_bet._build_entries", return_value=entries),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=fresh),
            patch("core.seasonal_calendar.fetch_week_topics", return_value=games),
        ):
            bets = get_best_bets("tapin", 5)
        sources = [b.source for b in bets]
        self.assertLessEqual(sources.count("schedule"), 2)
        self.assertIn("trending", sources)


# ---- #1192: the overnight videos, findable ----------------------------------------------------------


class OvernightVideoTests(unittest.TestCase):
    def test_the_start_menu_offers_them(self):
        from core.ui import prompt_startup_mode

        said: list[str] = []
        with patch("core.intelligence_report.intelligence_mode_enabled", return_value=False):
            mode = prompt_startup_mode(
                print_fn=lambda *a, **k: said.append(" ".join(str(x) for x in a)),
                input_fn=lambda prompt: "6",
            )
        self.assertEqual(mode, "overnight_review")
        self.assertTrue(any("6) Overnight videos and drafts" in s for s in said))

    def test_each_video_has_its_file_and_link(self):
        from core.batch_review import video_lines

        run = SimpleNamespace(mp4_path=r"C:\dev\content_machine\output\tapin\v.mp4")
        unlisted = SimpleNamespace(youtube_video_id="abc123", privacy_status="unlisted",
                                   content_run_id=126)  # fmt: skip
        with (
            patch("core.batch_review._run_record", return_value=run),
            patch("core.batch_review._publish_row", return_value=unlisted),
        ):
            text = "\n".join(video_lines(126, "tapin"))
        self.assertIn(r"C:\dev\content_machine\output\tapin\v.mp4", text)
        self.assertIn("https://studio.youtube.com/video/abc123/edit", text)
        public = SimpleNamespace(youtube_video_id="abc123", privacy_status="public",
                                 content_run_id=126)  # fmt: skip
        with (
            patch("core.batch_review._run_record", return_value=run),
            patch("core.batch_review._publish_row", return_value=public),
        ):
            self.assertIn("https://youtu.be/abc123", "\n".join(video_lines(126, "tapin")))

    def test_the_menu_choice_shows_them_then_the_drafts(self):
        import main

        order: list[str] = []
        with (
            patch("core.batch_review.overnight_rendered_lines",
                  side_effect=lambda ch, **kw: order.append("videos") or ["Overnight - tapin"]),
            patch("core.batch_review.review_drafts",
                  side_effect=lambda ch, **kw: order.append("drafts")),
            redirect_stdout(io.StringIO()),
        ):  # fmt: skip
            main._run_overnight_review("tapin")
        self.assertEqual(order, ["videos", "drafts"])


# ---- #1193: .env lines that are not NAME=value ------------------------------------------------------


class EnvFileTests(unittest.TestCase):
    def _problems(self, text):
        from core.secrets_doctor import env_file_problems

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return env_file_problems(path)

    def test_the_two_pasted_lines_of_2026_10_14(self):
        text = ("A_KEY=1\n\nClient abcdefghijklmnop\nClient qrstuvwxyz\n"
                "export B=2\n# Client note\nC = 3\nD=\"multi\nline\"\n")  # fmt: skip
        self.assertEqual(self._problems(text), [3, 4])

    def test_the_line_names_no_value(self):
        from core.secrets_doctor import env_file_line

        line = env_file_line([35, 36])
        self.assertIn("35, 36", line)
        self.assertIn("NAME=value", line)

    def test_no_file_no_problem(self):
        from core.secrets_doctor import env_file_problems

        self.assertEqual(env_file_problems(os.path.join(tempfile.gettempdir(), "nope.env")), [])

    def test_the_doctor_flags_it(self):
        from core import ops_doctor

        with (
            patch("core.secrets_doctor.env_file_problems", return_value=[35, 36]),
            patch(
                "core.ops_doctor._fetch_status",
                return_value={"status": {"indicator": "none"}},
            ),
            patch("core.ops_doctor._local_signal_failures", return_value=set()),
        ):
            checks = {c["name"]: c for c in ops_doctor.gather("tapin")["checks"]}
        self.assertFalse(checks["env-file"]["ok"])
        self.assertIn("35, 36", checks["env-file"]["detail"])


if __name__ == "__main__":
    unittest.main()
