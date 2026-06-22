"""Tests for the post-generation fact-grounding check.

Precision is the priority: real invented specifics must be flagged, and generic
title-case prose must NOT be (false positives would train the operator to ignore
the warning).
"""

import unittest

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

    def test_invented_season_flagged(self):
        script = "Season 7 changes everything."
        facts = "VERIFIED FACTS:\n- The game is popular."
        self.assertIn("Season 7", find_ungrounded_entities(script, facts))

    def test_empty_inputs_safe(self):
        self.assertEqual(find_ungrounded_entities("", "facts"), [])
        self.assertEqual(find_ungrounded_entities("Emma Frost", ""), ["Emma Frost"])


if __name__ == "__main__":
    unittest.main()
