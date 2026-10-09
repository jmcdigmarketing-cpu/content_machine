"""#1003: NFL records, results and next games from ESPN.

Run 118 ("why can we not pull more up to date data?"): `sports/espn.py` pointed at ESPN's
keyless scoreboard for the NBA only, and `apis/live_scores_api.py` answered every NFL
topic "NBA scoreboard only (NFL live scores not wired yet)" - a week-4 recap had no result
to stand on and the model invented two different opponents. Run 124's Chargers topic had
the same hole: "'chargers' matched no team".

- `sports/espn.py`: the league is a parameter (nba, nfl); `get_team` reads a team page.
- `live_scores` on an NFL topic: each named team's record, standing and next game (team
  page), and the matching game on the scoreboard (that week's board for "week N").
- `core.signal_facts` prints them as dated "ESPN team (as of ...)" lines, signal tier.
- The team page is pinned (`apis.schema_pins`), so a renamed field reads as drift.
"""

from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

FIXTURE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "signal_payloads" / "live_scores.json")
    .read_text(encoding="utf-8")
)  # fmt: skip
TEAM = FIXTURE["response"]
BOARD = FIXTURE["other_responses"]["scoreboard"]
TOPIC = "How the 0-4 chargers can turn it around this year"


def _signal(topic=TOPIC):
    from apis import live_scores_api

    urls: list[str] = []

    def fake_team(league, abbr):
        urls.append(f"team:{league}:{abbr}")
        return TEAM

    def fake_board(league="nba", *, week=None):
        urls.append(f"board:{league}:{week}")
        return BOARD

    with (
        patch("sports.espn.get_team", side_effect=fake_team),
        patch("sports.espn.get_scoreboard", side_effect=fake_board),
    ):
        return live_scores_api.get_live_scores_signal(topic), urls


class NflTests(unittest.TestCase):
    def test_run_124_reads_the_chargers(self):
        sig, urls = _signal()
        self.assertEqual(sig["status"], "ok", sig.get("status_detail"))
        self.assertIn("team:nfl:lac", urls)
        team = sig["data"]["teams"][0]
        self.assertEqual(team["team"], "Los Angeles Chargers")
        self.assertEqual(team["record"], "0-4")
        self.assertIn("AFC West", team["standing"])
        self.assertIn("Denver Broncos", team["next_game"])
        self.assertEqual(sig["data"]["source"], "ESPN NFL")

    def test_a_week_topic_reads_that_week(self):
        _sig, urls = _signal("seahawks vs chargers week 4 recap")
        self.assertIn("board:nfl:4", urls)
        self.assertIn("team:nfl:sea", urls)

    def test_no_nfl_no_nba_is_inactive_without_a_call(self):
        sig, urls = _signal("best budget gaming mice")
        self.assertFalse(sig["active"])
        self.assertEqual(urls, [])

    def test_the_facts_are_dated_and_signal_tier(self):
        from core.grounding_tiers import build_tiered_corpus
        from core.signal_facts import format_signal_facts

        sig, _urls = _signal()
        with patch("core.signal_facts._today", return_value=date(2026, 10, 9)):
            text = format_signal_facts({"live_scores": sig})
        self.assertIn("ESPN team (as of 2026-10-09)", text)
        self.assertIn("Los Angeles Chargers: 0-4", text)
        self.assertIn("next: Denver Broncos at Los Angeles Chargers", text)
        self.assertNotIn("NBA scoreboard only", text)
        tiered = build_tiered_corpus(signal_facts=text)
        record = [tier for tier, line in tiered.lines if "0-4" in line]
        self.assertEqual(record, ["signal"])


class EspnClientTests(unittest.TestCase):
    def test_league_urls(self):
        from sports import espn

        calls: list[tuple] = []

        class _Resp:
            status_code = 200

            def json(self):
                return {}

        def fake_get(url, params=None, timeout=None):
            calls.append((url, params))
            return _Resp()

        with patch.object(espn.requests, "get", side_effect=fake_get):
            espn.get_scoreboard("nfl", week=4)
            espn.get_team("nfl", "lac")
            espn.get_scoreboard()
        self.assertIn("football/nfl/scoreboard", calls[0][0])
        self.assertEqual(calls[0][1], {"week": 4})
        self.assertIn("football/nfl/teams/lac", calls[1][0])
        self.assertIn("basketball/nba/scoreboard", calls[2][0])


if __name__ == "__main__":
    unittest.main()
