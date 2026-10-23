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
"""

from __future__ import annotations

import json
import unittest
from datetime import timedelta
from types import SimpleNamespace

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


class CorpusTests(unittest.TestCase):
    def test_the_cases_are_filed(self):
        from core.regression_corpus import load_cases

        items = {c.get("item") for c in load_cases()}
        self.assertTrue({1481, 1482, 1483} <= items, "corpus cases for wave 122")


if __name__ == "__main__":
    unittest.main()
