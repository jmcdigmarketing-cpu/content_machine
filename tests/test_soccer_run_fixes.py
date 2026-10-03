"""Three defects the operator's soccer run (2026-10-01, wave 52 on the PC) put on screen.

#931 an all-lowercase overview ("State of the sport, pro football (soccer) as of oct 1
     2026, including la liaga, bundsaleiga, premier league, and early champions league
     projections") had no names to pull, so its search seed became the first clause:
     "State of the sport, pro football (soccer) as". Wikipedia matched "State" and the
     sports signal looked for a team called "State". The seed now takes known league /
     competition phrases from the domain lists, and the operator confirms it (operator).
#932 none of the five angles finished scoring inside VARIANT_SCORING_DEADLINE_S (15 s), so
     all five were dropped without a word and the seed was offered alone at 0.0. Unscored
     angles are now scored on the seed's signals already fetched, and the menu says so.
#933 the Headroom line printed three times, mid-spinner: every variant's registry
     re-emitted it, and since #922 the YouTube units really move between them.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

SOCCER = (
    "State of the sport, pro football (soccer) as of oct 1 2026, including la liaga, "
    "bundsaleiga, premier league, and early champions league projections"
)


class SeedTests(unittest.TestCase):
    def test_known_phrases_seed_a_lowercase_overview(self):
        from core.idea_intake import search_seed_from_thoughts

        self.assertEqual(search_seed_from_thoughts(SOCCER), "premier league champions league")

    def test_domain_phrases_keep_the_typed_order(self):
        from apis.topic_scorer import domain_phrases

        self.assertEqual(domain_phrases(SOCCER), ["premier league", "champions league"])
        self.assertEqual(domain_phrases("UFC 320 and the NBA finals"), ["ufc", "nba"])

    def test_named_subjects_still_win(self):
        from core.idea_intake import search_seed_from_thoughts

        seed = search_seed_from_thoughts(
            "I think Manchester City getting found guilty changes the whole premier league title race"
        )
        self.assertIn("Manchester City", seed)

    def test_the_operator_confirms_or_replaces_the_seed(self):
        import main

        with (
            patch("main.ask_text", side_effect=[SOCCER, ""]),
            patch("core.console_input.input_pending", return_value=False),
        ):
            topic, brief = main._ask_topic_or_thoughts()
        self.assertEqual(topic, "premier league champions league")
        self.assertIn("bundsaleiga", brief)
        with (
            patch("main.ask_text", side_effect=[SOCCER, "la liga bundesliga premier league"]),
            patch("core.console_input.input_pending", return_value=False),
        ):
            topic, _brief = main._ask_topic_or_thoughts()
        self.assertEqual(topic, "la liga bundesliga premier league")


class DeadlineTests(unittest.TestCase):
    def test_unscored_angles_are_scored_on_the_seed(self):
        from core import pipeline

        def slow(variant, channel_id, base, *, seed_topic=""):
            time.sleep(1.0)
            return variant, 99.0, base, 99.0

        angles = [f"angle {i}" for i in range(5)]
        with (
            patch.dict("os.environ", {"VARIANT_SCORING_DEADLINE_S": "0.1"}),
            patch.object(pipeline, "_score_variant", side_effect=slow),
            patch.object(pipeline, "composite_score", return_value=41.5),
        ):
            evaluated, _raw, meta = pipeline.collect_scored_variants(
                angles, "tapin", {"youtube": {"active": True}}, "seed topic"
            )
        self.assertEqual([v for v, _s, _sig in evaluated], angles)
        self.assertTrue(all(score == 41.5 for _v, score, _sig in evaluated))
        self.assertEqual(meta["unscored_on_seed"], 5)

    def test_the_menu_says_why(self):
        from core.pipeline import variant_fallback_note

        note = variant_fallback_note({"unscored_on_seed": 5}, total=5)
        self.assertIn("5 of 5 angles scored on the seed's signals", note)
        self.assertIn("VARIANT_SCORING_DEADLINE_S", note)
        self.assertEqual(variant_fallback_note({}, total=5), "")


class HeadroomTests(unittest.TestCase):
    def test_a_variant_registry_prints_no_headroom(self):
        from apis import register_signals

        with (
            patch.object(register_signals, "_active_signal_sources", return_value=()),
            patch("core.discovery_headroom.emit_headroom") as emit,
        ):
            register_signals.build_registry("angle 1", reuse_signals={"youtube": {"active": True}})
            self.assertFalse(emit.called)
            register_signals.build_registry("seed topic")
            self.assertTrue(emit.called)


if __name__ == "__main__":
    unittest.main()
