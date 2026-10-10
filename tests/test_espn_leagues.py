"""#1022 — NHL, MLB, college football and soccer, plus a dated injury line.

Recorded payloads only. The Chargers nickname the NFL list already knows still matches.
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

TEAM_PAGE = {
    "team": {
        "displayName": "Boston Bruins",
        "standingSummary": "Atlantic",
        "record": {"items": [{"type": "total", "summary": "10-2"}]},
        "nextEvent": [{"name": "at Maple Leafs", "date": "2026-10-12T23:00Z"}],
    }
}
INJURIES = {
    "injuries": [
        {
            "athlete": {"displayName": "Brad Marchand"},
            "status": "Out",
            "details": {"detail": "upper body"},
        }
    ]
}


def _signal(topic: str):
    from apis import live_scores_api

    urls: list[str] = []

    def fake_team(league, abbr):
        urls.append(f"team:{league}:{abbr}")
        page = dict(TEAM_PAGE)
        page["team"] = dict(TEAM_PAGE["team"])
        return page

    def fake_board(league="nba", *, week=None):
        urls.append(f"board:{league}:{week}")
        return {"events": []}

    def fake_injuries(league, abbr):
        urls.append(f"injuries:{league}:{abbr}")
        return INJURIES

    with (
        patch("sports.espn.get_team", side_effect=fake_team),
        patch("sports.espn.get_scoreboard", side_effect=fake_board),
        patch("sports.espn.get_injuries", side_effect=fake_injuries),
    ):
        return live_scores_api.get_live_scores_signal(topic), urls


class OtherLeagueTests(unittest.TestCase):
    def test_four_leagues_read_a_team_and_its_injuries(self) -> None:
        cases = (
            ("Bruins injury report", "nhl", "bos"),
            ("Yankees rotation news", "mlb", "nyy"),
            ("Crimson Tide injury report", "college-football", "ala"),
            ("Manchester City injuries", "soccer", "382"),
        )
        for topic, league, abbr in cases:
            sig, urls = _signal(topic)
            self.assertEqual(sig["status"], "ok", topic)
            self.assertIn(f"team:{league}:{abbr}", urls, topic)
            self.assertIn(f"injuries:{league}:{abbr}", urls, topic)
            self.assertEqual(
                sig["data"]["teams"][0]["injuries"], ["Brad Marchand (Out, upper body)"]
            )

    def test_the_injury_is_a_dated_fact(self) -> None:
        from core.signal_facts import format_signal_facts

        sig, _urls = _signal("Bruins injury report")
        with patch("core.signal_facts._today", return_value=date(2026, 10, 10)):
            text = format_signal_facts({"live_scores": sig})
        self.assertIn("as of 2026-10-10", text)
        self.assertIn("Brad Marchand (Out, upper body)", text)

    def test_chargers_still_matches_the_nfl_list(self) -> None:
        from apis.nfl_entities import team_names_in

        self.assertEqual(
            team_names_in("How the 0-4 chargers can turn it around this year"),
            ["Los Angeles Chargers"],
        )
