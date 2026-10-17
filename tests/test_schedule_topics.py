"""#1023 — a game or award still ahead can be a best bet; a finished one cannot."""

from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

from core.best_bet import get_best_bets
from core.seasonal_calendar import topics_from_board, week_topics

_TODAY = date(2026, 10, 10)
_BOARD = {
    "events": [
        {
            "name": "Bruins at Canadiens",
            "date": "2026-10-12T23:00Z",
            "status": {"type": {"completed": False}},
        },
        {
            "name": "Bruins at Maple Leafs",
            "date": "2026-10-01T23:00Z",
            "status": {"type": {"completed": True}},
        },
    ]
}


class ScheduleTopicTests(unittest.TestCase):
    def test_this_weeks_game_is_offered_and_last_weeks_is_not(self) -> None:
        topics = topics_from_board("nhl", _BOARD, today=_TODAY)
        self.assertEqual(topics, [("Bruins at Canadiens", "nhl")])

    def test_an_award_inside_the_window_is_offered(self) -> None:
        names = [topic for topic, _domain in week_topics({}, today=_TODAY)]
        self.assertIn("Ballon d'Or 2026", names)
        self.assertNotIn("The Game Awards 2026", names)

    def test_the_best_bet_list_includes_the_coming_game(self) -> None:
        def fake_board(league="nba", *, week=None):
            return _BOARD if league == "nhl" else {"events": []}

        with (
            patch.dict(os.environ, {"BEST_BET_SCHEDULE": "true"}),
            patch("core.best_bet._build_entries", return_value=[]),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=[]),
            patch("sports.espn.get_scoreboard", side_effect=fake_board),
            patch("core.seasonal_calendar._board_today", return_value=_TODAY),
        ):
            topics = [bet.topic for bet in get_best_bets("tapin", 5)]
        # #1242 (the operator, 2026-10-16): only marquee NFL and NBA games become ideas - the
        # NHL game is still dated by the board, and no longer suggested.
        self.assertNotIn("Bruins at Canadiens", topics)
        self.assertNotIn("Bruins at Maple Leafs", topics)
