"""#946: athlete and fighter names read as their sport.

`infer_topic_domain("Holloway vs Gaethje")`, "Topuria vs Holloway breakdown" and "Jon Jones
retires" all read neutral, and `infer_domain(..., "tapin")` turned them into the channel's
`gaming`: only "UFC" / "MMA"-style words made a topic `ufc`. The operator's Wemby Short
(2026-10-04 screenshots) read the same way - "wembanyama" is an NBA key, the nickname is not -
so it filed as gaming and cut UFC 5 footage (#955).

Two sources now name a sport, both checked after every keyword list and before the channel
fallback, so a game or league word still wins:
- `config/domain_names.json`, an operator-editable seed of names the channel has covered;
- names learned from runs whose stored `domains` say a sport (the #876 pattern for games): a
  name seen under two sports, or in a gaming run, teaches nothing.
"""

from __future__ import annotations

import io
import json
import os
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


def _run(rid, topic, domains):
    return SimpleNamespace(
        id=rid,
        selected_topic=topic,
        input_topic=topic,
        features_json=json.dumps({"domains": domains}),
    )


RUNS = [
    _run(201, "Steveson signs with the UFC", {"topic": "ufc", "effective": "ufc"}),
    _run(202, "Steveson debut date set", {"topic": "ufc", "effective": "ufc"}),
    _run(203, "Cooper Flagg summer league", {"topic": "nba", "effective": "nba"}),
    _run(204, "Cooper Flagg rookie ratings in 2K26", {"topic": "gaming", "effective": "gaming"}),
    _run(205, "Mendoza heads to the Raiders", {"topic": "nfl", "effective": "nfl"}),
    _run(206, "Mendoza walkout song", {"topic": "ufc", "effective": "ufc"}),
    _run(207, "New Update for the Jets", {"topic": "nfl", "effective": "nfl"}),
    _run(208, "Pre-#866 run about Steveson", None),
]


class SeedNamesTests(unittest.TestCase):
    def test_fighter_led_titles_read_ufc(self):
        from apis.topic_scorer import infer_domain, infer_topic_domain

        for topic in ("Holloway vs Gaethje", "Topuria vs Holloway breakdown", "Jon Jones retires"):
            self.assertEqual(infer_topic_domain(topic), "ufc", topic)
        self.assertEqual(infer_domain("Topuria vs Holloway breakdown", "tapin"), "ufc")

    def test_a_nickname_reads_as_its_sport(self):
        from apis.topic_scorer import infer_domain

        self.assertEqual(infer_domain("Wemby's 40-point night", "tapin"), "nba")

    def test_keywords_still_win(self):
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain("Messi in EA FC 26 ratings"), "gaming")
        self.assertEqual(infer_topic_domain("LeBron in NBA 2K26"), "nba")
        self.assertEqual(infer_topic_domain("GTA 6 trailer breakdown"), "gaming")

    def test_the_seed_names_only_sports(self):
        from apis.topic_scorer import KNOWN_DOMAINS
        from config.paths import DOMAIN_NAMES_FILE

        with open(DOMAIN_NAMES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        sports = {k for k in data if not k.startswith("_")}
        self.assertTrue(sports)
        self.assertTrue(sports <= set(KNOWN_DOMAINS), sports)
        for sport, names in data.items():
            if sport.startswith("_"):
                continue
            for name in names:
                self.assertEqual(name, name.lower().strip(), name)


class LearnedSportNamesTests(unittest.TestCase):
    def _learn(self, runs=RUNS, flag="true"):
        from core import learned_domain_terms as ldt

        repo = SimpleNamespace(
            list_for_channel=lambda cid, status=None: runs if cid == "tapin" else []
        )
        ldt.reset_learned_terms()
        with (
            patch.dict(os.environ, {"LEARNED_GAME_NAMES": flag}),
            patch.object(ldt, "_run_repo", return_value=repo),
            patch.object(ldt, "_channel_ids", return_value=["tapin"]),
        ):
            return ldt.learned_sport_name_sources(), ldt.learned_sport_names()

    def tearDown(self):
        from core import learned_domain_terms as ldt

        ldt.reset_learned_terms()

    def test_a_sport_run_teaches_its_names(self):
        sources, names = self._learn()
        self.assertEqual(names.get("steveson"), "ufc")
        self.assertEqual(sources["steveson"], ("ufc", [201, 202]))

    def test_a_name_also_seen_in_a_gaming_run_is_dropped(self):
        _sources, names = self._learn()
        self.assertNotIn("cooper flagg", names)

    def test_a_name_seen_under_two_sports_is_dropped(self):
        _sources, names = self._learn()
        self.assertNotIn("mendoza", names)

    def test_news_register_words_are_not_names(self):
        _sources, names = self._learn()
        self.assertNotIn("new update", names)
        self.assertEqual(names.get("jets"), "nfl")

    def test_switched_off_with_the_learned_names_flag(self):
        sources, names = self._learn(flag="false")
        self.assertEqual((sources, names), ({}, {}))

    def test_a_learned_name_moves_the_topic(self):
        from apis.topic_scorer import infer_domain, infer_topic_domain

        with patch(
            "core.learned_domain_terms.learned_sport_names", return_value={"steveson": "ufc"}
        ):
            self.assertEqual(infer_topic_domain("Steveson's next opponent"), "ufc")
            self.assertEqual(infer_domain("Steveson's next opponent", "tapin"), "ufc")
        self.assertEqual(infer_topic_domain("Steveson's next opponent"), "neutral")

    def test_the_names_verb_lists_sport_names(self):
        from scripts.ops import COMMANDS

        with patch(
            "core.learned_domain_terms.learned_sport_name_sources",
            return_value={"steveson": ("ufc", [201, 202])},
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                COMMANDS["game-names"][1](Namespace())
        out = buf.getvalue()
        self.assertIn("steveson", out)
        self.assertIn("ufc", out)


if __name__ == "__main__":
    unittest.main()
