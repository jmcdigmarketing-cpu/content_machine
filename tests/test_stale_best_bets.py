"""#1024 — a pooled best bet whose event has passed, or that drew 0 views, is not offered."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from core.best_bet import get_best_bets, pooled_drop_reason

_TODAY = date(2026, 10, 10)


class StaleBestBetTests(unittest.TestCase):
    def test_a_passed_date_and_a_zero_view_topic_are_dropped(self) -> None:
        self.assertIn("passed", pooled_drop_reason("NBA Free Agency Recap 7/7", 100, today=_TODAY))
        self.assertEqual(
            pooled_drop_reason("Manchester City ofund guilty", 0, today=_TODAY),
            "0 views",
        )
        self.assertEqual(pooled_drop_reason("UFC 325 main event", 40, today=_TODAY), "")

        entries = [
            {
                "topic": "NBA Free Agency Recap 7/7",
                "engaged_rate": 0.2,
                "composite_score": 40,
                "domain": "nba",
                "views": 100,
            },
            {
                "topic": "Manchester City ofund guilty",
                "engaged_rate": 0.3,
                "composite_score": 50,
                "domain": "soccer",
                "views": 0,
            },
            {
                "topic": "UFC 325 main event",
                "engaged_rate": 0.4,
                "composite_score": 60,
                "domain": "ufc",
                "views": 40,
            },
        ]
        with (
            patch("core.best_bet._build_entries", return_value=entries),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=[]),
            patch("core.best_bet._today", return_value=_TODAY),
        ):
            topics = [bet.topic for bet in get_best_bets("tapin", 5)]
        self.assertIn("UFC 325 main event", topics)
        self.assertNotIn("NBA Free Agency Recap 7/7", topics)
        self.assertNotIn("Manchester City ofund guilty", topics)
