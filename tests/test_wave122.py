"""Wave 122 (2026-10-22): the next five, and a defect found while planning them.

Measured first, on 053978c:
- the metrics sync stored a video's numbers only until its first-day snapshot: the one write of
  `metrics_json` sat inside `if log_id and not had_first_day` (wave 60, #49), so a second sync's
  2000 views left 90 stored - views, engaged rate, revenue and the organic rate froze at day 1 for
  every video whose analytics came in within 36 hours (#1542).
- the title check knew NFL and NBA teams only: "York Rangers", "Bay Lightning", "Louis Blues",
  "Diego Padres", "Ham United", "Hove Albion" and "Jersey Devils" passed, and "Vegas Golden
  Knights" read as a broken "Las Vegas" (#1481).
- nothing read the script for a broken name, and a caption cue could end inside one: at the
  karaoke style's 4 words, "Can the New England | Patriots win the AFC | East ..." (#1482).
- the thumbnail's short arm cut the title at 3 words: "Why the New", "How the Golden", "Can the
  Tampa" (#1483).

Batch B:
- overnight left no sign of life between its start and its finish: the 10-16 crash was known
  from Task Scheduler's exit code and the log's last write, a hand run had neither, and `ops
  status` said only "last started" (#1468).
- the health lines' tests fed hand-made shapes; none wrote a field the way production writes it
  and read it back, which is how the frozen metrics (#1542) went unseen (#1473,
  tests/test_health_writers.py).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from tests import test_first_day as first_day


class MetricsKeptTests(unittest.TestCase):
    """#1542: every sync stores what it fetched; the first-day snapshot stays the first day's."""

    def test_a_later_sync_is_stored(self):
        young = SimpleNamespace(
            id=9, content_run_id=109, youtube_video_id="v9", detail="Heat preseason",
            published_at=first_day.NOW - timedelta(hours=20), metrics_json="{}",
        )  # fmt: skip
        repo = first_day._Repo([young])
        sync = first_day.SyncTests()
        first, _emit = sync._refresh(repo, young, {"views": 90, "engaged_rate": 0.4})
        self.assertEqual(first["views"], 90)
        later, _emit = sync._refresh(repo, young, {"views": 2000, "engaged_rate": 0.55})
        self.assertEqual(later["views"], 2000)
        self.assertEqual(later["engaged_rate"], 0.55)
        self.assertEqual(later["snapshots"]["24h"]["views"], 90)  # the first day stays


class GazetteerTests(unittest.TestCase):
    """#1481: NFL, NBA, NHL, MLB and EPL in one table the title check reads."""

    def test_the_leagues(self):
        from apis.team_gazetteer import teams

        counts = {}
        for team in teams():
            counts[team.league] = counts.get(team.league, 0) + 1
        self.assertEqual((counts["NHL"], counts["MLB"], counts["EPL"]), (32, 30, 20))
        self.assertGreaterEqual(counts["NFL"], 32)
        self.assertGreaterEqual(counts["NBA"], 30)

    def test_a_name_that_lost_its_first_word(self):
        from core.title_generator import broken_place_name

        for title, full in (
            ("York Rangers fall to 2-5", "New York Rangers"),
            ("Bay Lightning stun the Rangers", "Tampa Bay Lightning"),
            ("Louis Blues rally late", "St. Louis Blues"),
            ("Diego Padres trade rumors", "San Diego Padres"),
            ("Ham United sack their manager", "West Ham United"),
            ("Hove Albion top the table", "Brighton & Hove Albion"),
            ("Jersey Devils win in OT", "New Jersey Devils"),
            ("New York Jets vs England Patriots", "New England Patriots"),
        ):
            self.assertEqual(broken_place_name(title), full, title)

    def test_a_whole_name_is_left_alone(self):
        from core.title_generator import broken_place_name

        for title in (
            "Vegas Golden Knights win again",
            "Toronto Maple Leafs open at home",
            "Boston Red Sox payroll",
            "Manchester United's new manager",
            "St Louis Blues rally",
            "St. Louis Blues rally",
            "New York Rangers fall to 2-5",
            "Trail Blazers rookies stand out",
            "Brighton & Hove Albion top the table",
        ):
            self.assertEqual(broken_place_name(title), "", title)


SENTENCE = "Can the New England Patriots win the AFC East this year without a run game."


def _words(text):
    return [
        {"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, w in enumerate(text.split())
    ]


class CaptionNameTests(unittest.TestCase):
    """#1482: the script is read for a broken name, and a cue never ends inside one."""

    def test_the_script_check_names_a_broken_name(self):
        from core.script_craft import script_check

        check = script_check(script="Can the England Patriots win the AFC East? Maybe.")
        self.assertFalse(check["ok"])
        self.assertTrue(any('"New England Patriots"' in w for w in check["why"]), check["why"])
        clean = script_check(script="Can the New England Patriots win the AFC East? Maybe.")
        self.assertFalse(any("name" in w for w in clean["why"]), clean["why"])
        # a fight script says "in Vegas" and "the Orleans Arena" - the city, not a broken name
        fight = script_check(
            script="UFC 333 is in Vegas this weekend at the Orleans Arena. Big night."
        )
        self.assertFalse(any("name" in w for w in fight["why"]), fight["why"])

    def test_a_cue_never_ends_inside_a_name(self):
        from video.caption_timing import group_into_lines
        from video.subtitles import split_script_into_lines

        for max_words in (3, 4, 5):
            lines = [
                " ".join(w["word"] for w in line)
                for line in group_into_lines(_words(SENTENCE), max_words)
            ]
            self.assertEqual(" ".join(lines), SENTENCE)
            self.assertTrue(
                any("New England Patriots" in line for line in lines), (max_words, lines)
            )
            self.assertTrue(any("AFC East" in line for line in lines), (max_words, lines))
            self.assertTrue(all(len(line.split()) <= max_words for line in lines), lines)
            plain = split_script_into_lines(SENTENCE, max_words)
            self.assertTrue(any("New England Patriots" in line for line in plain), plain)

    def test_a_sentence_without_names_is_cut_as_before(self):
        from video.caption_timing import group_into_lines
        from video.subtitles import split_script_into_lines

        plain = "this is a plain line of words with nothing much in it."
        want = ["this is a plain", "line of words with", "nothing much in it."]
        self.assertEqual(split_script_into_lines(plain, 4), want)
        got = [" ".join(w["word"] for w in line) for line in group_into_lines(_words(plain), 4)]
        self.assertEqual(got, want)


class ThumbnailNameTests(unittest.TestCase):
    """#1483: the words on the thumbnail never end inside a team's name."""

    def test_the_headline(self):
        from assets.thumbnail_compose import headline_words
        from core.title_generator import broken_place_name

        got = headline_words("Why are the New York Jets so bad this year")
        self.assertEqual(" ".join(got), "Why are the New York Jets")
        self.assertEqual(
            headline_words("Why the Chargers can still win the West"),
            ["Why", "the", "Chargers", "can", "still"],
        )  # no name, cut as before
        self.assertEqual(broken_place_name(" ".join(got)), "")

    def test_the_short_arm(self):
        from assets.thumbnail_compose import headline_words, short_headline

        for title, want in (
            ("Why the New England Patriots Can Still Win the East", "New England Patriots"),
            ("How the Golden State Warriors Lost Their Edge", "Golden State Warriors"),
            ("Can the Tampa Bay Buccaneers Survive Week 8", "Tampa Bay Buccaneers"),
            ("Topuria Knocks Out Holloway Again Tonight", "Topuria Knocks Out"),  # no name: 3
        ):
            self.assertEqual(" ".join(short_headline(headline_words(title), 3)), want, title)


class BeatTests(unittest.TestCase):
    """#1468: overnight writes a beat each minute; the morning and `ops status` read the gap."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.beat = os.path.join(tmp.name, "overnight_beat.json")
        self.record = os.path.join(tmp.name, "overnight_last.json")
        env = patch.dict(
            os.environ,
            {"OVERNIGHT_BEAT_FILE": self.beat, "OVERNIGHT_RECORD_FILE": self.record,
             "OVERNIGHT_BEAT": "true"},
        )  # fmt: skip
        env.start()
        self.addCleanup(env.stop)

    def _write(self, path, payload):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_the_beat_is_written_and_stops(self):
        from core import nightly_task

        started = datetime(2026, 10, 16, 4, 30, 7)
        self.assertTrue(nightly_task.start_beat(started, seconds=0.01))
        nightly_task.beat_step("drafting 1 of 3: Chargers week 7")
        threading.Event().wait(0.1)
        nightly_task.stop_beat()
        beat = nightly_task.last_beat()
        self.assertEqual(beat["started"], started.isoformat(timespec="seconds"))
        self.assertEqual(beat["step"], "drafting 1 of 3: Chargers week 7")
        self.assertFalse(any(t.name == "overnight-beat" for t in threading.enumerate()))

    def test_the_gap_is_said(self):
        from core import nightly_task

        self._write(self.record, {"channel": "tapin", "started": "2026-10-16T04:30:07",
                                  "finished": "", "drafts": None})  # fmt: skip
        self._write(self.beat, {"started": "2026-10-16T04:30:07", "beat": "2026-10-16T04:32:13",
                                "step": "rendering run 175"})  # fmt: skip
        line = nightly_task.beat_gap_line(now=datetime(2026, 10, 16, 9, 0))
        self.assertEqual(
            line,
            "Overnight's last sign of life was 4:32 AM on Oct 16, rendering run 175 "
            "(started 4:30 AM) - it never finished",
        )
        # still beating, finished, or a beat from another run: nothing to say
        self.assertEqual(nightly_task.beat_gap_line(now=datetime(2026, 10, 16, 4, 33)), "")
        self._write(self.beat, {"started": "2026-10-15T05:00:00", "beat": "2026-10-15T05:09:00",
                                "step": ""})  # fmt: skip
        self.assertEqual(nightly_task.beat_gap_line(now=datetime(2026, 10, 16, 9, 0)), "")

    def test_ops_status_and_the_morning_read_it(self):
        from core import nightly_task, status_summary

        self._write(self.record, {"channel": "tapin", "started": "2026-10-16T04:30:07",
                                  "finished": "", "drafts": None})  # fmt: skip
        self._write(self.beat, {"started": "2026-10-16T04:30:07", "beat": "2026-10-16T04:32:13",
                                "step": "rendering run 175"})  # fmt: skip
        with patch.object(nightly_task, "_now", return_value=datetime(2026, 10, 16, 9, 0)):
            status = status_summary._overnight("tapin")
            morning = nightly_task.overnight_stop_line()  # no Task Scheduler: the beat alone
        self.assertIn("last sign of life was 4:32 AM", status)
        self.assertIn("rendering run 175", morning)

    def test_ops_overnight_beats_while_it_runs(self):
        from scripts import ops

        seen = {}

        def run(*_a, **_k):
            seen["alive"] = any(t.name == "overnight-beat" for t in threading.enumerate())
            seen["file"] = os.path.isfile(self.beat)
            return SimpleNamespace(drafted=0)

        with (
            patch("core.overnight.run_overnight", side_effect=run),
            patch("core.overnight.render_overnight", return_value=""),
            patch("core.nightly_task.enable_crash_traceback", return_value=False),
        ):
            ops.cmd_overnight(SimpleNamespace(channel="tapin", count=1, file=None, facts_file=None))
        self.assertEqual(seen, {"alive": True, "file": True})
        self.assertFalse(any(t.name == "overnight-beat" for t in threading.enumerate()))


class CorpusTests(unittest.TestCase):
    def test_the_cases_are_filed(self):
        from core.regression_corpus import load_cases

        items = {c.get("item") for c in load_cases()}
        self.assertTrue({1481, 1482, 1483} <= items, "corpus cases for wave 122")


if __name__ == "__main__":
    unittest.main()
