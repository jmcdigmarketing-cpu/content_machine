"""#896: the sports signal files only teams the topic names.

`apis/sports_data_api._team_search_term` falls back to the topic's first capitalised
word, and `core/signal_facts` filed the first three teams TheSportsDB returned as
"sports teams (API)" with no check that any of them was in the topic - `assessment.md`
weakness 3's "sports matched a cricket club". A team is kept when its name, short name
or an alternate name is in the topic as whole words, or when it carries the team the
NFL/NBA resolvers already found (a player -> team mapping, a nickname).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _run(topic: str, teams: list[dict]):
    from apis import sports_data_api

    response = SimpleNamespace(status_code=200, text="", json=lambda: {"teams": teams})
    with (
        patch.object(sports_data_api, "SPORTSDB_API_KEY", "k"),
        patch.object(sports_data_api.requests, "get", return_value=response),
    ):
        return sports_data_api.get_sports_data(topic)


class TeamInTopicTests(unittest.TestCase):
    def test_a_club_the_topic_never_names_is_not_filed(self):
        sig = _run(
            "Premier League title race goes to the last day",
            [{"strTeam": "Premier Cricket Club", "strAlternate": ""}],
        )
        self.assertFalse(sig["active"])
        self.assertIn("no team named in the topic", sig["status_detail"])
        self.assertEqual(sig.get("score", 0), 0)

    def test_only_the_named_club_is_kept(self):
        sig = _run(
            "Manchester City fined again, what now",
            [
                {"strTeam": "Manchester United", "strAlternate": "Man United, Man Utd"},
                {"strTeam": "Manchester City", "strAlternate": "Man City"},
            ],
        )
        self.assertTrue(sig["active"])
        self.assertEqual([t["strTeam"] for t in sig["data"]], ["Manchester City"])

    def test_an_alternate_name_counts(self):
        sig = _run(
            "Man Utd sack another manager",
            [{"strTeam": "Manchester United", "strAlternate": "Man United, Man Utd"}],
        )
        self.assertEqual([t["strTeam"] for t in sig["data"]], ["Manchester United"])

    def test_a_resolved_nickname_counts(self):
        sig = _run(
            "Knicks rally past the Celtics in Game 7",
            [{"strTeam": "New York Knicks", "strAlternate": ""}],
        )
        self.assertTrue(sig["active"])
        self.assertEqual([t["strTeam"] for t in sig["data"]], ["New York Knicks"])

    def test_the_facts_line_carries_only_kept_teams(self):
        from core.signal_facts import format_signal_facts

        sig = _run(
            "Manchester City fined again, what now",
            [
                {"strTeam": "Manchester United", "strAlternate": ""},
                {"strTeam": "Manchester City", "strAlternate": ""},
            ],
        )
        text = format_signal_facts({"sports": sig})
        self.assertIn("Manchester City", text)
        self.assertNotIn("Manchester United", text)

    def test_the_phrase_helper(self):
        from apis.topic_tokens import contains_phrase

        self.assertTrue(contains_phrase("Manchester City fined again", "Manchester City"))
        self.assertFalse(contains_phrase("Manchester City fined again", "Manchester United"))
        self.assertFalse(contains_phrase("The Premiership", "Premier"))
        self.assertFalse(contains_phrase("anything", ""))


if __name__ == "__main__":
    unittest.main()
