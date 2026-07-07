"""Domain inference with operator key-fact override (sports on gaming channel)."""

import unittest

from apis.topic_scorer import infer_domain
from core import content_engine as ce
from core.script_brief import build_script_brief


class TestInferDomainKeyFacts(unittest.TestCase):
    def test_standings_and_award_races_infer_nba(self):
        topic = "WAY too early final standing projections for 2027, award races included"
        self.assertEqual(infer_domain(topic, "tapin"), "nba")

    def test_key_facts_override_gaming_channel(self):
        topic = "Early standings take — who's real and who's fraud"
        facts = [
            "Source: Jonathan Wasserman's 2027 NBA Mock Draft",
            "Tyran Stokes will start atop the board.",
            "The Oklahoma City Thunder had one too many injuries.",
        ]
        self.assertEqual(infer_domain(topic, "tapin", key_facts=facts), "nba")

    def test_gaming_topic_without_sports_facts_stays_gaming(self):
        self.assertEqual(
            infer_domain("Marvel Rivals Season 3 tier list", "tapin"),
            "gaming",
        )


class TestScriptBriefSportsOnTapin(unittest.TestCase):
    def test_nba_matrix_on_tapin_with_key_facts(self):
        brief = build_script_brief(
            "2027 standings way too early",
            "tapin",
            key_facts=["Giannis Antetokounmpo was traded to the Miami Heat."],
        )
        self.assertIn("DOMAIN: nba", brief)
        self.assertIn("NBA SCRIPT MATRIX", brief)
        self.assertIn("Marvel Rivals", brief)
        self.assertNotIn("Primary franchise focus lately:", brief)


class TestVideoGameDrift(unittest.TestCase):
    def test_detects_marvel_rivals_with_nba_facts(self):
        script = "Early standings in Marvel Rivals have squads sitting pretty."
        facts = ["Tyran Stokes leads the 2027 mock draft.", "Knicks won the 2026 title."]
        self.assertTrue(ce._video_game_drift(script, facts, "2027 standings"))

    def test_no_drift_when_script_matches_facts(self):
        script = "The Knicks and Thunder look like paper tigers in early 2027 projections."
        facts = ["Knicks won the 2026 title.", "Oklahoma City Thunder had injury issues."]
        self.assertFalse(ce._video_game_drift(script, facts, "2027 NBA standings"))


if __name__ == "__main__":
    unittest.main()
