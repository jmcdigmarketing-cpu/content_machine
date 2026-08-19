"""Tests for the post-generation fact-grounding check.

Precision is the priority: real invented specifics must be flagged, and generic
title-case prose must NOT be (false positives would train the operator to ignore
the warning).
"""

import os
import unittest
from unittest.mock import patch

from core.fact_grounding import extract_entities, find_ungrounded_entities


class TestExtractEntities(unittest.TestCase):
    def test_multiword_proper_nouns(self):
        ents = extract_entities("Emma Frost and Black Widow joined the roster.")
        self.assertIn("Emma Frost", ents)
        self.assertIn("Black Widow", ents)

    def test_single_capital_word_ignored(self):
        # A lone capitalised word is too noisy to treat as a specific.
        self.assertEqual(extract_entities("Cyclops is strong."), [])

    def test_allcaps_acronyms_ignored(self):
        self.assertEqual(extract_entities("GTA VI and UFC are huge."), [])

    def test_version_token(self):
        self.assertIn("Season 8.5", extract_entities("The Season 8.5 update dropped."))


class TestFindUngrounded(unittest.TestCase):
    def test_invented_hero_flagged(self):
        # The run-#3 case: hero names absent from the facts.
        script = "Emma Frost brings the Radiant Shore theme to the game."
        facts = "VERIFIED FACTS:\n- Marvel Rivals mid-season update is coming."
        ungrounded = find_ungrounded_entities(script, facts)
        self.assertIn("Emma Frost", ungrounded)
        self.assertIn("Radiant Shore", ungrounded)

    def test_grounded_entity_not_flagged(self):
        script = "Emma Frost joins the roster."
        facts = "VERIFIED FACTS:\n- Emma Frost is the new duelist this season."
        self.assertEqual(find_ungrounded_entities(script, facts), [])

    def test_grounded_by_distinctive_token(self):
        # Facts name "Frost"; the full phrase still counts as grounded because
        # every distinctive token appears (Black is a common word).
        script = "Black Widow is back."
        facts = "Reports mention Widow returning."
        self.assertEqual(find_ungrounded_entities(script, facts), [])

    def test_generic_title_case_not_flagged(self):
        # Common-word phrases are never flagged regardless of the facts.
        script = "The Community is divided. Drop Your Thoughts in the comments."
        self.assertEqual(find_ungrounded_entities(script, ""), [])

    def test_sentence_initial_discourse_adverbs_not_flagged(self):
        # Live-run regression (2026-08-14): "Otherwise, we'll keep seeing…" was
        # reported as an unsupported specific because _MONONYM matches any 4+ char
        # capitalised word. It cost a real script 45 grounding points and a letter
        # grade (A -> B). These words can never be a name.
        script = (
            "The UFC needs to overhaul its rankings. Otherwise, we keep seeing this. "
            "However, the panel disagrees. Instead, they wait. Basically, it is broken. "
            "Meanwhile, nothing changes. Honestly, that is the problem."
        )
        self.assertEqual(find_ungrounded_entities(script, ""), [])

    def test_real_mononym_still_flagged_after_adverb_skip(self):
        # The adverb skip must not blunt the check: a real invented name still flags.
        # (Mononyms only extract in sports context — hence the UFC mention.)
        script = "Otherwise, Salkilld dominates the UFC lightweight division."
        self.assertIn("Salkilld", find_ungrounded_entities(script, "The UFC rankings updated."))

    def test_invented_season_flagged(self):
        script = "Season 7 changes everything."
        facts = "VERIFIED FACTS:\n- The game is popular."
        self.assertIn("Season 7", find_ungrounded_entities(script, facts))

    def test_empty_inputs_safe(self):
        self.assertEqual(find_ungrounded_entities("", "facts"), [])
        self.assertEqual(find_ungrounded_entities("Emma Frost", ""), ["Emma Frost"])

    def test_mononym_athlete_flagged_when_ungrounded(self):
        script = "LeBron is not re-signing with the Lakers this summer."
        facts = "VERIFIED FACTS:\n- Jaylen Brown was traded to the 76ers."
        ungrounded = find_ungrounded_entities(script, facts)
        self.assertIn("LeBron", ungrounded)

    def test_mononym_grounded_when_in_facts(self):
        script = "LeBron is leaving the Lakers."
        facts = "VERIFIED FACTS:\n- LeBron James will not re-sign with Los Angeles."
        self.assertNotIn("LeBron", find_ungrounded_entities(script, facts))

    def test_word_boundary_avoids_substring_false_grounding(self):
        script = "Art Walker leads the rebuild."
        facts = "VERIFIED FACTS:\n- Smart roster moves matter."
        self.assertIn("Art Walker", find_ungrounded_entities(script, facts))

    def test_common_transition_words_not_flagged_as_mononyms(self):
        script = (
            "Meanwhile, Rookie of the Year is wide open. Bottom line: the Thunder look fragile."
        )
        facts = "VERIFIED FACTS:\n- Oklahoma City Thunder had injury issues in the playoffs."
        self.assertEqual(find_ungrounded_entities(script, facts), [])


class TestKeyFactsPriority(unittest.TestCase):
    def test_manual_facts_win_over_vault_when_capped(self):
        from core.content_engine import key_facts_for_prompt

        ordered = [
            "Giannis traded to Miami Heat June 22 2026",
            "Jaylen Brown to 76ers July 1 2026",
            "Kawhi Leonard to Raptors June 30 2026",
            "Ja Morant to Trail Blazers June 29 2026",
            "Walker Kessler to Lakers July 1 2026",
            "Fraud narratives outperform recaps",
            "Rankings framing beats reactions",
        ]
        sent = key_facts_for_prompt(ordered)
        self.assertGreaterEqual(len(sent), 5)
        self.assertIn("Giannis", sent[0])
        self.assertNotIn("Fraud", " ".join(sent))

    def test_max_operator_key_facts_env(self):
        from core.operator_facts import facts_for_prompt, max_operator_key_facts

        facts = [f"fact {i}" for i in range(10)]
        with patch.dict(os.environ, {"MAX_OPERATOR_KEY_FACTS": "8"}):
            self.assertEqual(max_operator_key_facts(), 8)
            sent = facts_for_prompt(facts)
        self.assertEqual(len(sent), 8)


if __name__ == "__main__":
    unittest.main()
