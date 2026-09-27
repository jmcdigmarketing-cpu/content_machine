"""#897: the odds signal answers for the topic's sport, not for every topic.

`apis/odds_api.get_odds_data` fetched `/v4/sports` - the list of every sport the API
covers - and returned score 50 whenever the API answered, with that whole list as its
data. Every topic in a team-sport domain got the same bump. The same one call now picks
the sports the topic is about; none -> inactive, score 0. Quota use is unchanged.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

SPORTS = [
    {"key": "americanfootball_nfl", "group": "American Football", "title": "NFL",
     "description": "US Football", "active": True},
    {"key": "basketball_nba", "group": "Basketball", "title": "NBA",
     "description": "US Basketball", "active": True},
    {"key": "soccer_epl", "group": "Soccer", "title": "EPL",
     "description": "English Premier League", "active": True},
    {"key": "soccer_usa_mls", "group": "Soccer", "title": "MLS",
     "description": "Major League Soccer", "active": True},
    {"key": "americanfootball_cfl", "group": "American Football", "title": "CFL",
     "description": "Canadian Football", "active": True},
]  # fmt: skip


def _run(topic: str, *, remaining: str = "480"):
    from apis import odds_api

    response = SimpleNamespace(
        status_code=200, text="", headers={"x-requests-remaining": remaining}, json=lambda: SPORTS
    )
    with (
        patch.object(odds_api, "ODDS_API_KEY", "k"),
        patch.object(odds_api.requests, "get", return_value=response) as get,
    ):
        return odds_api.get_odds_data(topic), get


class OddsTopicTests(unittest.TestCase):
    def test_a_gaming_topic_gets_nothing(self):
        sig, _ = _run("GTA 6 trailer 3 breakdown")
        self.assertFalse(sig["active"])
        self.assertEqual(sig.get("score", 0), 0)

    def test_an_nfl_topic_gets_the_nfl_only(self):
        sig, _ = _run("Chiefs vs Bills: who covers the spread in the NFL playoffs")
        self.assertTrue(sig["active"])
        self.assertEqual([s["key"] for s in sig["data"]], ["americanfootball_nfl"])

    def test_an_epl_topic_gets_the_epl(self):
        sig, _ = _run("Premier League title race goes to the last day")
        self.assertEqual([s["key"] for s in sig["data"]], ["soccer_epl"])

    def test_a_club_story_naming_no_league_gets_nothing(self):
        sig, _ = _run("Manchester City fined again, what now")
        self.assertFalse(sig["active"])

    def test_still_one_call(self):
        _sig, get = _run("NBA Finals odds after Game 5")
        self.assertEqual(get.call_count, 1)

    def test_quota_exhaustion_is_unchanged(self):
        from apis.signal_contract import STATUS_QUOTA

        sig, _ = _run("NBA Finals odds after Game 5", remaining="0")
        self.assertEqual(sig["status"], STATUS_QUOTA)


if __name__ == "__main__":
    unittest.main()
