"""#1002 + #1005: the who's-who lookup reads the subject, not the sentence's first word.

Run 124: "How the 0-4 chargers can turn it around this year" gave `names_for` no team (the
topic is lower-case, and `title_phrases` reads only capitalised runs) and the angle's
sentence-initial "Next Sunday" became a name: Wikidata matched "Next" to NeXT (the
computer company - its check ignored case), and the freshness check counted "97 news
headline(s) named NeXT in 48 hours". Run 118 missed the Seahawks and Chargers the same way;
run 120's "People" resolved to "human: any single member of Homo sapiens".

- `apis.topic_tokens.name_phrases`: `title_phrases` minus a phrase made only of
  `COMMON_CAPITALISED` words (sentence-initial "Next", "People", "Game", weekdays).
- `apis.nfl_entities.team_names_in` / `apis.nba_teams.team_names_in`: a nickname as a whole
  word, in a text that reads as that sport, gives the full team name.
- `core.facts.entity_lookup.names_for` uses both.
- Wikidata: a class item ("any ...") is not an entity, and a one-word name must match the
  label's case past its first letter ("Next" is not "NeXT").
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

TOPIC = "How the 0-4 chargers can turn it around this year"


class NamesForTests(unittest.TestCase):
    def test_run_124(self):
        from core.facts.entity_lookup import names_for

        names = names_for(TOPIC, angle="Next Sunday decides whether the Chargers season survives")
        self.assertIn("Los Angeles Chargers", names)
        self.assertFalse([n for n in names if n.split()[0] in ("Next", "Sunday")], names)

    def test_the_lowercase_topic_alone_finds_the_team(self):
        from core.facts.entity_lookup import names_for

        self.assertEqual(names_for(TOPIC), ["Los Angeles Chargers"])

    def test_run_118_two_teams(self):
        from core.facts.entity_lookup import names_for

        names = names_for("seahawks vs chargers week 4 recap")
        self.assertIn("Seattle Seahawks", names)
        self.assertIn("Los Angeles Chargers", names)

    def test_phone_chargers_are_not_a_team(self):
        from apis.nfl_entities import team_names_in

        self.assertEqual(team_names_in("best phone chargers 2026"), [])
        self.assertEqual(team_names_in("the rams programs explained"), [])

    def test_nba_too(self):
        from apis.nba_teams import team_names_in

        self.assertEqual(team_names_in("can the lakers win game 7"), ["Los Angeles Lakers"])
        self.assertEqual(team_names_in("the heat wave in phoenix"), [])

    def test_common_words_are_not_names(self):
        from core.facts.entity_lookup import names_for

        self.assertEqual(names_for("People working with ai to blend video games"), [])
        self.assertNotIn("Game", names_for("Game of the year 2027 predictions"))
        self.assertIn("New York Jets", names_for("Can the New York Jets fix their offense"))


class NamePhrasesTests(unittest.TestCase):
    def test_all_common_phrases_drop(self):
        from apis.topic_tokens import name_phrases

        self.assertEqual(name_phrases("Next Sunday the Chargers play"), ["Chargers"])
        self.assertEqual(name_phrases("Never done this before? Read Start here."), [])
        self.assertEqual(name_phrases("Ghost of Yotei", connectors=True), ["Ghost of Yotei"])


class WikidataTests(unittest.TestCase):
    def _hit(self, hits, name):
        from core.facts import entity_lookup

        with patch.object(entity_lookup, "_get_json", return_value={"search": hits}):
            return entity_lookup._search_wikidata(name)

    def test_a_class_is_not_an_entity(self):
        hits = [{"id": "Q5", "label": "human", "description": "any single member of Homo sapiens",
                 "match": {"text": "People"}}]  # fmt: skip
        self.assertIsNone(self._hit(hits, "People"))

    def test_next_is_not_next_computer(self):
        hits = [{"id": "Q19355", "label": "NeXT", "description": "American computer company",
                 "match": {"text": "NeXT"}}]  # fmt: skip
        self.assertIsNone(self._hit(hits, "Next"))

    def test_a_real_name_still_resolves(self):
        hits = [{"id": "Q1", "label": "Los Angeles Chargers",
                 "description": "National Football League franchise in Inglewood, California",
                 "match": {"text": "Los Angeles Chargers"}}]  # fmt: skip
        self.assertEqual(self._hit(hits, "Los Angeles Chargers")["id"], "Q1")
        wemby = [{"id": "Q2", "label": "Victor Wembanyama", "description": "French basketball player",
                  "match": {"text": "Wemby"}}]  # fmt: skip
        self.assertEqual(self._hit(wemby, "Wemby")["id"], "Q2")


if __name__ == "__main__":
    unittest.main()
