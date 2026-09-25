"""Tests for content-run feature normalization (feature-store substrate)."""

import unittest

from core.run_features import (
    build_features,
    classify_angle,
    classify_title_structure,
    extract_hook,
)


class TestClassifiers(unittest.TestCase):
    def test_title_structure(self):
        self.assertEqual(classify_title_structure("Top 5 UFC upsets"), "listicle")
        self.assertEqual(classify_title_structure("Is McGregor washed?"), "question")
        self.assertEqual(classify_title_structure("UFC 311 changed everything"), "number")
        self.assertEqual(classify_title_structure("Holloway: the silent killer"), "callout")
        self.assertEqual(classify_title_structure("Gaethje wins it all"), "statement")
        self.assertEqual(classify_title_structure(""), "unknown")

    def test_run_73_reaction_is_not_general(self):
        """#661. Generation said reaction; analytics said general."""
        self.assertEqual(classify_angle("GTA 6 looks amazing!!!", ""), "reaction")

    def test_explainer_seed_is_explainer(self):
        self.assertEqual(
            classify_angle("how does the offside rule actually work", ""),
            "explainer",
        )

    def test_default_intent_still_uses_keyword_labels(self):
        """Fraud/recap are analytics labels, not angle-intent frames. They fire
        only when detect_angle_intent returns default."""
        self.assertEqual(classify_angle("Max Holloway is a fraud", ""), "fraud")
        self.assertEqual(classify_angle("Full card results recap", ""), "recap")

    def test_extract_hook(self):
        self.assertEqual(
            extract_hook("He lost everything in one night. Then it got worse."),
            "He lost everything in one night.",
        )
        self.assertEqual(extract_hook(""), "")


class TestBuildFeatures(unittest.TestCase):
    def test_build_features_full(self):
        class Brief:
            recommended_format = "analysis"
            controversy_score = 0.7
            audience_sentiment = "divided"
            title_direction = "legacy framing"
            suggested_hook = "Two champs in one night."

        f = build_features(
            topic="UFC 250 Holloway fraud callout",
            channel_id="tapin",
            content_package={
                "title": "Is Holloway a fraud?",
                "script": "He lied. Big time.",
                "word_count": 90,
            },
            research_brief=Brief(),
            length_choice="2",
            key_facts=["Gaethje won"],
        )
        self.assertEqual(f["domain"], "ufc")
        self.assertEqual(f["angle"], "fraud")
        self.assertEqual(f["title_structure"], "question")
        self.assertEqual(f["hook_text"], "He lied.")
        self.assertEqual(f["controversy_score"], 0.7)
        self.assertEqual(f["fact_source"], "manual")
        self.assertEqual(f["key_facts_count"], 1)
        self.assertEqual(f["feature_version"], "v2")
        self.assertEqual(f["angle_intent"], "default")

    def test_build_features_no_brief_no_facts(self):
        f = build_features(
            topic="random gaming topic",
            channel_id="tapin",
            content_package={"title": "A title", "script": "Hello world."},
            research_brief=None,
            length_choice="1",
            key_facts=None,
        )
        self.assertEqual(f["fact_source"], "signals")
        self.assertEqual(f["key_facts_count"], 0)
        self.assertIsNone(f["controversy_score"])


if __name__ == "__main__":
    unittest.main()
