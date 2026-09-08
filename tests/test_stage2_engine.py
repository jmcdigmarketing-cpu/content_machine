"""#333 negative-fact store, #550 superlatives, #541/#540/#542 script craft.

Fail-then-fix: unmodified code has no negative store and does not strip a
pre-CTA recap or flag ungrounded 'first ever'.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.fact_grounding import find_ungrounded_entities
from core.persona_lint import lint_persona_script


class TestNegativeFactStore(unittest.TestCase):
    def test_a_walked_back_leak_cannot_be_reasserted(self):
        from core.negative_facts import matching_negatives, record_negative

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "negative_facts.json"
            with patch("core.negative_facts.STORE_PATH", store):
                record_negative(
                    "gta",
                    "GTA 6 leaked for a June 2025 release",
                    reason="walked back by Rockstar",
                )
                hits = matching_negatives(
                    "Insiders say GTA 6 leaked for a June 2025 release last night.",
                    franchise="gta",
                )
                miss = matching_negatives(
                    "Ilia Topuria is the featherweight champion as of June 2026.",
                    franchise="gta",
                )
        self.assertTrue(hits)
        self.assertIn("June 2025", " ".join(hits))
        self.assertEqual(miss, [])

    def test_grounding_merges_negative_hits(self):
        from core.negative_facts import record_negative

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "negative_facts.json"
            with patch("core.negative_facts.STORE_PATH", store):
                record_negative("gta", "GTA 6 leaked for a June 2025 release")
                from core.negative_facts import apply_negative_facts

                flags = apply_negative_facts(
                    "GTA 6 leaked for a June 2025 release according to the forum.",
                    franchise="gta",
                )
        self.assertTrue(flags)


class TestSuperlativesNeedASource(unittest.TestCase):
    def test_first_ever_without_facts_is_flagged_not_only_as_a_conjunction(self):
        from core.script_craft import find_ungrounded_superlatives

        script = "This is the first ever worldwide release of the map."
        self.assertTrue(find_ungrounded_superlatives(script, "the map drops Friday"))
        self.assertFalse(
            find_ungrounded_superlatives(
                "This is the first ever worldwide release of the map.",
                "Rockstar called it the first ever worldwide release.",
            )
        )
        self.assertFalse(
            find_ungrounded_superlatives(
                "It is not only a leak but also a trailer.",
                "trailer facts",
            )
        )


class TestLlmTellsAndRhythm(unittest.TestCase):
    def test_per_channel_tells_include_delve_and_in_todays_video(self):
        hits = lint_persona_script(
            "In today's video we delve into the purse.",
            channel_id="tapin",
        )
        blob = " ".join(hits).lower()
        self.assertIn("delve", blob)
        self.assertIn("today's video", blob)

    def test_moneywise_range_still_is_not_a_tell(self):
        hits = lint_persona_script(
            "Expect 5-10 years of compounding at 10-15%.",
            channel_id="moneywise",
        )
        self.assertEqual(hits, [])

    def test_uniform_sentence_length_is_flagged(self):
        from core.script_craft import sentence_rhythm_flags

        flat = "Cats sat down. Dogs ran hard. Birds flew out. Fish swam fast. Frogs jumped high."
        varied = (
            "The featherweight champion walked into the octagon under the lights. "
            "He won. "
            "That one-night swing is why the division looks different this week, and why the next card already feels overdue."
        )
        self.assertTrue(sentence_rhythm_flags(flat))
        self.assertFalse(sentence_rhythm_flags(varied))

    def test_pre_cta_summary_paragraph_is_cut_and_pre_count_survives(self):
        from core.script_craft import strip_pre_cta_summary

        script = (
            "Ilia Topuria kept the belt in June. The take is that the division is stuck.\n\n"
            "In summary, Topuria is still champion and the division is stuck.\n\n"
            "Like and subscribe for the next card."
        )
        cleaned, report = strip_pre_cta_summary(script)
        self.assertNotIn("In summary", cleaned)
        self.assertIn("Like and subscribe", cleaned)
        self.assertIn("Ilia Topuria kept the belt", cleaned)
        self.assertEqual(report["pre_paragraphs"], 3)
        self.assertEqual(report["post_paragraphs"], 2)
        self.assertTrue(report["stripped"])
        untouched, none = strip_pre_cta_summary(
            "Ilia Topuria kept the belt in June.\n\nLike and subscribe for the next card."
        )
        self.assertFalse(none["stripped"])
        self.assertEqual(
            untouched,
            "Ilia Topuria kept the belt in June.\n\nLike and subscribe for the next card.",
        )


class TestGroundingStillSeesEntities(unittest.TestCase):
    def test_superlative_helper_does_not_replace_entity_grounding(self):
        hits = find_ungrounded_entities(
            "Emma Frost joined the roster.",
            "A generic gaming recap with no names.",
        )
        self.assertTrue(any("Emma" in h for h in hits))
