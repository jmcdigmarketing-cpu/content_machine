"""Ten ideas: five ideas and five previews/predictions (the operator, 2026-10-17, decision 66).

"need to work on idea generation, maybe expand it to 10? 5 ideas 5 previews/predictions?" The
menu showed five options where games competed for a league's place (decision 59); a thin day
showed fewer. Now the ideas (headlines, past winners, the follow-up, the mailbag) keep five
places and the coming events - marquee NFL/NBA games, UFC cards, awards, then the other NFL and
NBA games - fill five more. Overnight drafts from both.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from tests.test_idea_list import NFL_BOARD, _event

NOW = datetime(2026, 10, 17, 20, 0, tzinfo=timezone.utc)
UFC_BOARD = {
    "leagues": [
        {
            "calendar": [
                {"label": "UFC 334: Topuria vs. Holloway", "startDate": "2026-10-11T01:00Z"},
                {"label": "UFC 335: Nickal vs. Pyfer", "startDate": "2026-10-25T01:00Z"},
                {"label": "UFC Fight Night: Far Away", "startDate": "2026-12-06T01:00Z"},
            ]
        }
    ]
}
NBA_BOARD = {
    "events": [
        _event("Denver Nuggets at Los Angeles Lakers", "2026-10-21T02:30Z", ["ESPN"]),
        _event("Orlando Magic at Miami Heat", "2026-10-21T23:30Z", ["FanDuel SN"]),
    ]
}


def _scheduled():
    from core import seasonal_calendar

    details: dict = {}
    starts: dict = {}
    topics = []
    for league, board in (("nfl", NFL_BOARD), ("nba", NBA_BOARD)):
        topics += seasonal_calendar.topics_from_board(
            league, board, today=date(2026, 10, 17), starts=starts, details=details
        )
    topics += seasonal_calendar.ufc_cards(UFC_BOARD, now=NOW, starts=starts)
    topics.append(("Ballon d'Or 2026", "soccer"))
    return topics, details, starts


def _menu(fresh=(), recent=(), previews=None):
    from core import best_bet, seasonal_calendar

    topics, details, starts = _scheduled()
    entries = [
        {"topic": "GTA 6 map breakdown", "engaged_rate": 0.31, "composite_score": 60,
         "domain": "gaming", "views": 400},
        {"topic": "Fortnite chapter guide", "engaged_rate": 0.28, "composite_score": 55,
         "domain": "gaming", "views": 300},
    ]  # fmt: skip
    with (
        patch.object(seasonal_calendar, "_DETAILS", details),
        patch.object(seasonal_calendar, "_STARTS", starts),
        patch.object(best_bet, "_build_entries", return_value=entries),
        patch.object(best_bet, "recent_input_topics", return_value=list(recent)),
        patch.object(best_bet, "_fresh_candidates", return_value=list(fresh)),
        patch("core.seasonal_calendar.fetch_week_topics", return_value=topics),
        patch("core.topic_graph.follow_up_seed", return_value=None),
        patch("core.seasonal_calendar.due_topics", return_value=[]),
        patch("analytics.mailbag.top_question", return_value=None),
    ):
        return best_bet.get_idea_menu("tapin", now=NOW, previews=previews)


FRESH = [
    {"topic": "Raul Rosas Jr. makes RAF debut", "domain": "ufc", "source": "MMA Fighting"},
    {"topic": "New Steam museum game", "domain": "gaming", "source": "Dexerto"},
    {"topic": "Packers sign a new kicker", "domain": "nfl", "source": "ESPN"},
]


class UfcCardTests(unittest.TestCase):
    def test_the_next_two_weeks_of_cards_with_their_start(self):
        from core.seasonal_calendar import ufc_cards

        starts: dict = {}
        cards = ufc_cards(UFC_BOARD, now=NOW, starts=starts)
        self.assertEqual(cards, [("UFC 335: Nickal vs. Pyfer", "ufc")])
        self.assertEqual(starts["UFC 335: Nickal vs. Pyfer"], "2026-10-25T01:00Z")


class MenuShapeTests(unittest.TestCase):
    def test_five_ideas_and_five_previews(self):
        ideas, previews = _menu(fresh=FRESH)
        self.assertTrue(ideas)
        self.assertLessEqual(len(ideas), 5)
        self.assertFalse([b for b in ideas if b.source == "schedule"])
        self.assertEqual(len(previews), 5)
        self.assertTrue(all(b.source == "schedule" for b in previews))

    def test_previews_mix_the_kinds_of_event(self):
        _ideas, previews = _menu(fresh=FRESH)
        names = [b.topic for b in previews]
        # #1449: the marquee places take leagues in turn - the NFL's earliest, then the NBA's.
        self.assertIn("Houston Texans at Jacksonville Jaguars", names)
        self.assertIn("Denver Nuggets at Los Angeles Lakers", names)
        self.assertIn("UFC 335: Nickal vs. Pyfer", names)  # a UFC card
        self.assertIn("Ballon d'Or 2026", names)  # an award
        self.assertNotIn("Ohio State Buckeyes at Michigan Wolverines", names)  # college stays out
        card = next(b for b in previews if b.topic.startswith("UFC 335"))
        self.assertIn("Oct 24", card.rationale)  # 9:00 PM EDT the 24th

    def test_a_started_game_and_a_covered_one_are_not_previews(self):
        _ideas, previews = _menu(fresh=FRESH, recent=["Denver Nuggets at Los Angeles Lakers"])
        names = [b.topic for b in previews]
        self.assertNotIn("Denver Nuggets at Los Angeles Lakers", names)  # drafted already
        self.assertNotIn("UFC 334: Topuria vs. Holloway", names)  # last week's card


class SameStoryTests(unittest.TestCase):
    def test_a_card_an_idea_already_covers_is_not_a_preview(self):
        # Live, 2026-10-17: idea 3 "LIVE! UFC Edmonton Results: Buckley vs. Malott" and preview
        # 7 "UFC Fight Night: Buckley vs. Malott" were the same story.
        fresh = [*FRESH, {"topic": "Nickal and Pyfer weigh in for UFC 335", "domain": "ufc",
                          "source": "MMA Fighting"}]  # fmt: skip
        ideas, previews = _menu(fresh=fresh)
        self.assertTrue(any("Nickal" in b.topic for b in ideas))
        self.assertFalse(any("Nickal" in b.topic for b in previews))

    def test_one_shared_team_is_a_different_story(self):
        # "Packers sign a new kicker" is an idea. Since #1449 the NBA's game takes the second
        # marquee place, so the Cowboys-Packers game is the third - past the first five.
        _ideas, previews = _menu(fresh=FRESH, previews=8)
        self.assertIn("Dallas Cowboys at Green Bay Packers", [b.topic for b in previews])


class DisplayTests(unittest.TestCase):
    def test_two_groups_numbered_one_to_ten(self):
        from core.best_bet import BestBetResult, display_idea_menu

        def bet(topic, source):
            return BestBetResult(topic=topic, domain="nfl", avg_engaged_rate=0.0,
                                 source=source, supporting_runs=0, rationale="why")  # fmt: skip

        said: list[str] = []
        display_idea_menu([bet(f"idea {i}", "trending") for i in range(5)],
                          [bet(f"game {i}", "schedule") for i in range(5)],
                          print_fn=said.append)  # fmt: skip
        text = "\n".join(said)
        self.assertIn("Ideas", text)
        self.assertIn("Previews and predictions", text)
        self.assertIn("    1. [nfl] idea 0", text)
        self.assertIn("   10. [nfl] game 4", text)


class OvernightMixTests(unittest.TestCase):
    def test_overnight_takes_ideas_and_previews_in_turn(self):
        from core import batch_generation
        from core.best_bet import BestBetResult

        def bet(topic, source):
            return BestBetResult(topic=topic, domain="nfl", avg_engaged_rate=0.0,
                                 source=source, supporting_runs=0, rationale="why")  # fmt: skip

        ideas = [bet("idea a", "trending"), bet("idea b", "analytics")]
        previews = [bet("game a", "schedule"), bet("game b", "schedule")]
        with patch("core.best_bet.get_idea_menu", return_value=(ideas, previews)):
            topics = batch_generation.collect_topics("tapin", count=3)
        self.assertEqual(topics, ["idea a", "game a", "idea b"])


if __name__ == "__main__":
    unittest.main()
