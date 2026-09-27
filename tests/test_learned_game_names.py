"""#876: game names the keyword list lacks are learned from confirmed runs.

"Silksong delayed again" names no keyword `infer_topic_domain` knows, so it read
neutral. A run whose topic read neutral but whose live gaming signals (RAWG, IGDB, Steam,
Twitch - all matched to the topic) made it gaming is evidence the name is a game. Those
names are learned; a name also seen in a non-gaming run is not. Runs from before #866
stored no `domains`, and run 98's stale "gaming" must not teach "Manchester City".
"""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _run(rid, topic, domains=None, domain="gaming"):
    features = {"domain": domain}
    if domains is not None:
        features["domains"] = domains
    return SimpleNamespace(
        id=rid, selected_topic=topic, input_topic=topic, features_json=json.dumps(features)
    )


RUNS = [
    _run(101, "Silksong delayed again", {"topic": "neutral", "effective": "gaming"}),
    _run(102, "Palworld update drops tonight", {"topic": "neutral", "effective": "gaming"}),
    _run(98, "Manchester City found guilty", None, domain="gaming"),
    _run(103, "Arsenal vs Palworld sponsor row", {"topic": "soccer", "effective": "soccer"}),
    _run(104, "GTA 6 trailer", {"topic": "gaming", "effective": "gaming"}),
]


class LearnedGameNamesTests(unittest.TestCase):
    def _learn(self, runs=RUNS, flag="true"):
        from core import learned_domain_terms as ldt

        repo = SimpleNamespace(
            list_for_channel=lambda cid, status=None: runs if cid == "tapin" else []
        )
        ldt.reset_learned_terms()
        with (
            patch.dict(os.environ, {"LEARNED_GAME_NAMES": flag}),
            patch.object(ldt, "_run_repo", return_value=repo),
            patch.object(ldt, "_channel_ids", return_value=["tapin", "moneywise"]),
        ):
            return ldt.learned_game_name_sources(), ldt.learned_game_names()

    def tearDown(self):
        from core import learned_domain_terms as ldt

        ldt.reset_learned_terms()

    def test_a_signal_confirmed_neutral_topic_teaches_its_name(self):
        sources, names = self._learn()
        self.assertIn("silksong", names)
        self.assertEqual(sources["silksong"], [101])

    def test_a_name_seen_in_a_non_gaming_run_is_not_learned(self):
        _sources, names = self._learn()
        self.assertNotIn("palworld", names)

    def test_runs_before_domains_were_stored_teach_nothing(self):
        _sources, names = self._learn()
        self.assertFalse(any("manchester" in n for n in names))

    def test_the_flag_off_learns_nothing(self):
        _sources, names = self._learn(flag="false")
        self.assertEqual(names, frozenset())

    def test_the_topic_reads_gaming_once_learned(self):
        from apis.topic_scorer import infer_topic_domain

        with patch(
            "core.learned_domain_terms.learned_game_names", return_value=frozenset({"silksong"})
        ):
            self.assertEqual(infer_topic_domain("Silksong delayed again"), "gaming")
        self.assertEqual(infer_topic_domain("Silksong delayed again"), "neutral")

    def test_a_learned_name_never_beats_a_sport_keyword(self):
        from apis.topic_scorer import infer_topic_domain

        with patch(
            "core.learned_domain_terms.learned_game_names", return_value=frozenset({"silksong"})
        ):
            self.assertEqual(infer_topic_domain("UFC fighter plays Silksong"), "ufc")

    def test_the_suite_pins_it_off(self):
        self.assertEqual(os.environ.get("LEARNED_GAME_NAMES"), "false")


class GameNamesVerbTests(unittest.TestCase):
    def test_ops_game_names_lists_names_and_runs(self):
        import argparse
        import io
        from contextlib import redirect_stdout

        from scripts.ops import cmd_game_names

        out = io.StringIO()
        with (
            patch(
                "core.learned_domain_terms.learned_game_name_sources",
                return_value={"silksong": [101]},
            ),
            redirect_stdout(out),
        ):
            cmd_game_names(argparse.Namespace())
        self.assertIn("silksong", out.getvalue())
        self.assertIn("101", out.getvalue())


if __name__ == "__main__":
    unittest.main()
