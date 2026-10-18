"""Wave 102 (#1242-#1246): what the idea list offers - the operator, 2026-10-16: "why do we get
video ideas that are just the names of sporting events, and then have those be the only ideas
that show up?"

- ESPN's board put every unplayed game of the week into the ideas - 40 that night (16 college
  football, 13 NFL), each as its bare name ("New Orleans Saints at New York Giants") with "on the
  board this week" as its reason. TapIn had published no NFL video at all.
- Games held 2 of 5 slots (1 of overnight's 3) whatever they were up against, and filled any slot
  the other sources left empty. Oct 11 drafted 3 games and nothing else.
- The menu's follow-up read "Ben Affleck": run 126 was uploaded unlisted at 7:07 PM and became
  the newest arc before anyone had seen it.
- The menu replayed "Messi World Cup Hat Trick", a World Cup story months old.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

_TODAY = date(2026, 10, 16)


def _event(name, when, nets, records=("3-3", "4-1"), notes=()):
    away, home = name.split(" at ")
    return {
        "name": name,
        "date": when,
        "status": {"type": {"completed": False}},
        "competitions": [
            {
                "broadcasts": [{"names": list(nets)}],
                "notes": [{"headline": n} for n in notes],
                "competitors": [
                    {"homeAway": "home", "team": {"shortDisplayName": home.split()[-1]},
                     "records": [{"summary": records[1]}]},
                    {"homeAway": "away", "team": {"shortDisplayName": away.split()[-1]},
                     "records": [{"summary": records[0]}]},
                ],
            }
        ],
    }  # fmt: skip


NFL_BOARD = {
    "events": [
        _event("Dallas Cowboys at Green Bay Packers", "2026-10-19T00:20Z", ["NBC"]),
        _event("New Orleans Saints at New York Giants", "2026-10-18T17:00Z", ["Fox"]),
        _event("Los Angeles Chargers at Kansas City Chiefs", "2026-10-18T20:25Z", ["CBS"]),
        _event("Houston Texans at Jacksonville Jaguars", "2026-10-18T13:30Z", ["NFL Net"],
               notes=["NFL London Games"]),
    ]
}  # fmt: skip
CFB_BOARD = {"events": [_event("Ohio State Buckeyes at Michigan Wolverines",
                               "2026-10-17T16:00Z", ["FOX"])]}  # fmt: skip


def _games(covered=("How the chargers can still make the superbowl after starting 0-4",)):
    from core import best_bet, seasonal_calendar

    details: dict = {}
    topics = []
    for league, board in (("nfl", NFL_BOARD), ("college-football", CFB_BOARD)):
        topics += seasonal_calendar.topics_from_board(league, board, today=_TODAY, details=details)
    # Wave 108: on the real clock this went red at 13:30Z on 2026-10-18, when the London game
    # in the fixture kicked off. The board's own day is the moment it is read.
    board_day = datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc)
    with patch.object(seasonal_calendar, "_DETAILS", details):
        return best_bet.suggested_games(topics, covered_topics=list(covered), now=board_day)


# ---- #1242: only marquee NFL and NBA games -------------------------------------------------------


class MarqueeTests(unittest.TestCase):
    def test_the_board_keeps_each_games_details(self):
        from core.seasonal_calendar import topics_from_board

        details: dict = {}
        topics_from_board("nfl", NFL_BOARD, today=_TODAY, details=details)
        detail = details["Dallas Cowboys at Green Bay Packers"]
        self.assertEqual(detail["broadcasts"], ["NBC"])
        self.assertEqual(detail["away"]["record"], "3-3")

    def test_national_tv_london_and_your_team_only(self):
        names = [bet.topic for bet in _games()]
        self.assertIn("Dallas Cowboys at Green Bay Packers", names)  # NBC
        self.assertIn("Houston Texans at Jacksonville Jaguars", names)  # London
        self.assertIn("Los Angeles Chargers at Kansas City Chiefs", names)  # the operator's team
        self.assertNotIn("New Orleans Saints at New York Giants", names)  # regional Fox
        self.assertNotIn("Ohio State Buckeyes at Michigan Wolverines", names)  # college

    def test_without_the_chargers_ideas_their_game_is_regional(self):
        names = [bet.topic for bet in _games(covered=())]
        self.assertNotIn("Los Angeles Chargers at Kansas City Chiefs", names)

    def test_a_game_the_board_drafted_is_not_a_team_you_covered(self):
        # Live, 2026-10-16: "Panthers at Eagles" was offered as "Eagles, a team you made videos
        # about" - the only Eagles topic was the old board's "Philadelphia Eagles at Jacksonville
        # Jaguars" draft.
        names = [bet.topic for bet in _games(covered=("Kansas City Chiefs at Denver Broncos",))]
        self.assertNotIn("Los Angeles Chargers at Kansas City Chiefs", names)


# ---- #1243: a game idea says when, where and the records -----------------------------------------


class StartedTests(unittest.TestCase):
    def test_a_game_that_has_tipped_off_is_not_an_idea(self):
        # Live, 2026-10-16 11:44 PM CDT: "Nuggets at Lakers, Fri Oct 16 9:30 PM" was still
        # offered - the board is dated in UTC (Oct 17) and its cached copy said not completed.
        from datetime import datetime, timezone

        from core import best_bet, seasonal_calendar

        details: dict = {}
        topics = seasonal_calendar.topics_from_board("nfl", NFL_BOARD, today=_TODAY,
                                                     details=details)  # fmt: skip
        after_the_early_games = datetime(2026, 10, 18, 19, 0, tzinfo=timezone.utc)
        with patch.object(seasonal_calendar, "_DETAILS", details):
            names = [b.topic for b in best_bet.suggested_games(
                topics, covered_topics=["Chargers Hopeium going into week 5"],
                now=after_the_early_games)]  # fmt: skip
        self.assertNotIn("Houston Texans at Jacksonville Jaguars", names)  # 13:30Z, under way
        self.assertIn("Dallas Cowboys at Green Bay Packers", names)  # 00:20Z the next day


class GameLineTests(unittest.TestCase):
    def test_the_reason_is_the_game_not_the_board(self):
        bet = next(b for b in _games() if b.topic.startswith("Dallas"))
        self.assertNotEqual(bet.rationale, "on the board this week")
        self.assertIn("NBC", bet.rationale)
        self.assertIn("Cowboys 3-3 at Packers 4-1", bet.rationale)

    def test_your_team_says_why(self):
        bet = next(b for b in _games() if b.topic.startswith("Los Angeles Chargers"))
        self.assertIn("Chargers", bet.rationale)
        self.assertIn("you made videos about", bet.rationale)


# ---- #1244: games compete like any idea ------------------------------------------------------------


def _bets(fresh, games):
    from core import best_bet

    entries = [
        {"topic": "GTA 6 map breakdown", "engaged_rate": 0.31, "composite_score": 60,
         "domain": "gaming", "views": 400},
        {"topic": "Fortnite chapter guide", "engaged_rate": 0.28, "composite_score": 55,
         "domain": "gaming", "views": 300},
    ]  # fmt: skip
    with (
        patch.object(best_bet, "_build_entries", return_value=entries),
        patch.object(best_bet, "recent_input_topics", return_value=[]),
        patch.object(best_bet, "_fresh_candidates", return_value=fresh),
        patch.object(best_bet, "suggested_games", return_value=games),
        patch("core.seasonal_calendar.fetch_week_topics", return_value=[]),
        patch("core.topic_graph.follow_up_seed", return_value=None),
        patch("core.seasonal_calendar.due_topics", return_value=[]),
        patch("analytics.mailbag.top_question", return_value=None),
    ):
        return best_bet.get_best_bets("tapin", 5)


def _game(topic, domain="nfl"):
    from core.best_bet import BestBetResult

    return BestBetResult(topic=topic, domain=domain, avg_engaged_rate=0.0, source="schedule",
                         supporting_runs=0, rationale="Sun · NBC")  # fmt: skip


class CompeteTests(unittest.TestCase):
    def test_a_thin_day_shows_fewer_ideas_not_more_games(self):
        fresh = [{"topic": "Raul Rosas Jr. makes RAF debut", "domain": "ufc", "source": "ESPN"}]
        games = [_game(f"Team {i} at Team {i + 10}") for i in range(6)]
        sources = [b.source for b in _bets(fresh, games)]
        self.assertLessEqual(sources.count("schedule"), 1)

    def test_a_headline_in_the_league_beats_its_game(self):
        fresh = [{"topic": "Packers sign a new kicker", "domain": "nfl", "source": "ESPN"}]
        bets = _bets(fresh, [_game("Dallas Cowboys at Green Bay Packers")])
        nfl = [b for b in bets if b.domain == "nfl"]
        self.assertEqual(nfl[0].source, "trending")


# ---- #1245: a follow-up waits for its video to be public -------------------------------------------


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "topic_graph.json")
        p = patch("config.paths.TOPIC_GRAPH_FILE", self.path)
        p.start()
        self.addCleanup(p.stop)

    def _arcs(self, privacy):
        from core import topic_graph

        topic_graph.record_published_topic("tapin", "UFC Illia Islam", video_id="pub1")
        topic_graph.record_published_topic(
            "tapin", "Ben Affleck admits he gets into arguments with 12-year-olds in Fortnite",
            video_id="NmFh9n57y4M",
        )  # fmt: skip
        rows = [SimpleNamespace(youtube_video_id="pub1", privacy_status="public"),
                SimpleNamespace(youtube_video_id="NmFh9n57y4M", privacy_status=privacy)]  # fmt: skip
        repo = SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            return topic_graph.follow_up_seed("tapin")

    def test_an_unlisted_video_does_not_lead_the_menu(self):
        seed = self._arcs("unlisted")
        # The public arc is "UFC Illia Islam", which #1259 no longer repeats, so the
        # menu can have no follow-up. It must not be the unlisted Affleck video.
        self.assertTrue(seed is None or "Affleck" not in seed.topic)

    def test_once_it_is_public_a_name_cut_from_its_headline_is_still_not_offered(self):
        # Wave 105 (the operator: drop bare-name follow-ups): public now, but "Ben Affleck" alone
        # is not a video - the arc no longer leads the menu with it.
        self.assertIsNone(self._arcs("public"))

    def test_an_arc_saved_before_the_id_matches_its_upload_by_time(self):
        # The live row: written 00:08:23Z, three seconds after run 126's upload was logged.
        from core import topic_graph

        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"channels": {"tapin": {"arcs": {"fortnite": {
                "ordinal": 1, "updated_at": "2026-10-17T00:08:23+00:00",
                "last_topic": "Ben Affleck admits he gets into arguments with 12-year-olds"}}}}},
                fh)  # fmt: skip
        rows = [SimpleNamespace(youtube_video_id="NmFh9n57y4M", privacy_status="unlisted",
                                published_at="2026-10-16 20:08:20.331075-04:00")]  # fmt: skip
        repo = SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            self.assertIsNone(topic_graph.follow_up_seed("tapin"))


# ---- #1246: a replay is never a news story -------------------------------------------------------


class ReplayTests(unittest.TestCase):
    def test_a_world_cup_hat_trick_does_not_replay(self):
        from core.best_bet import pooled_drop_reason

        self.assertTrue(pooled_drop_reason("Messi World Cup Hat Trick", 120, today=_TODAY))

    def test_an_evergreen_game_guide_still_can(self):
        from core.best_bet import pooled_drop_reason

        self.assertEqual(pooled_drop_reason("GTA 6 map breakdown", 400, today=_TODAY), "")


if __name__ == "__main__":
    unittest.main()
