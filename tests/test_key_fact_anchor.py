"""Tests for keeping the operator's subject anchored through the pipeline."""

import unittest
from unittest.mock import patch

from apis import topic_variants as tv
from core import content_engine as ce

_KEY_FACTS = ["Manel Kape scored a knockout of Kyoji Horiguchi at the event."]
_FACTS = "Manel Kape knocked out Kyoji Horiguchi. Kape avenged a prior loss."
_TOPIC = "MMA divisional rankings: Kape punches his ticket"


class TestSubjectTerms(unittest.TestCase):
    def test_keeps_single_word_subject(self):
        self.assertIn("Kape", tv._subject_terms("MMA divisional rankings: Kape punches his ticket"))

    def test_drops_allcaps_and_common_words(self):
        terms = tv._subject_terms("MMA divisional rankings: Kape punches his ticket")
        self.assertNotIn("MMA", terms)  # acronym/domain, not a subject
        self.assertNotIn("Rankings", terms)

    def test_anchor_rules_mention_subject(self):
        rules = tv._anchor_rules("MMA divisional rankings: Kape punches his ticket", None)
        self.assertIn("Kape", rules)
        self.assertIn("Keep the seed's subject", rules)


class TestKeyFactRecenter(unittest.TestCase):
    def test_recenters_when_script_ignores_key_facts(self):
        drifted = "Dricus Du Plessis is the most underrated fighter in the division right now."
        recentered = (
            "Manel Kape just knocked out Kyoji Horiguchi and shook up the flyweight rankings — "
            "a statement win nobody can ignore."
        )
        with patch.object(ce, "_call_content_llm", return_value={"script": recentered}):
            out = ce._maybe_recenter_on_key_facts(drifted, _KEY_FACTS, _TOPIC, _FACTS)
        self.assertEqual(out, recentered)

    def test_noop_when_script_mentions_key_subject(self):
        on_topic = "Manel Kape just delivered a statement knockout to climb the rankings."
        with patch.object(ce, "_call_content_llm") as mock_llm:
            out = ce._maybe_recenter_on_key_facts(on_topic, _KEY_FACTS, _TOPIC, _FACTS)
            mock_llm.assert_not_called()
        self.assertEqual(out, on_topic)

    def test_rejects_rewrite_still_off_topic(self):
        drifted = "Dricus Du Plessis is underrated and everyone is sleeping on him."
        still_off = "Israel Adesanya is the only real story in the division this year, honestly."
        with patch.object(ce, "_call_content_llm", return_value={"script": still_off}):
            out = ce._maybe_recenter_on_key_facts(drifted, _KEY_FACTS, _TOPIC, _FACTS)
        self.assertEqual(out, drifted)  # kept original — rewrite didn't fix the drift

    def test_disabled_is_noop(self):
        with patch.dict("os.environ", {"KEY_FACT_ANCHOR_ENABLED": "false"}, clear=False):
            with patch.object(ce, "_call_content_llm") as mock_llm:
                out = ce._maybe_recenter_on_key_facts(
                    "Du Plessis stuff", _KEY_FACTS, _TOPIC, _FACTS
                )
                mock_llm.assert_not_called()
        self.assertEqual(out, "Du Plessis stuff")

    def test_no_key_facts_is_noop(self):
        self.assertEqual(
            ce._maybe_recenter_on_key_facts("anything", None, _TOPIC, _FACTS), "anything"
        )

    def test_numeric_only_facts_noop(self):
        # No proper-noun subject to anchor on → no-op even if facts exist.
        with patch.object(ce, "_call_content_llm") as mock_llm:
            out = ce._maybe_recenter_on_key_facts(
                "some script", ["The score was 5 to 3."], _TOPIC, ""
            )
            mock_llm.assert_not_called()
        self.assertEqual(out, "some script")

    def test_recenters_on_video_game_drift_with_nba_facts(self):
        drifted = "Marvel Rivals standings show paper tigers at the top of the leaderboard."
        nba_facts = [
            "Tyran Stokes leads Jonathan Wasserman's 2027 mock draft.",
            "The New York Knicks won the 2026 title.",
        ]
        fixed = (
            "The Knicks look like paper tigers in early 2027 projections — "
            "Tyran Stokes is the prospect everyone is sleeping on."
        )
        with patch.object(ce, "_call_content_llm", return_value={"script": fixed}):
            out = ce._maybe_recenter_on_key_facts(
                drifted, nba_facts, "2027 NBA standings too early", _FACTS
            )
        self.assertEqual(out, fixed)


if __name__ == "__main__":
    unittest.main()
