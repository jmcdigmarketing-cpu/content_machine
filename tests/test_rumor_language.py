"""#346: leak/rumor topics must carry reportedly + an outlet, like odds voice."""

from __future__ import annotations

import unittest

from core.rumor_language import apply_rumor_language


class TestRumorLanguage(unittest.TestCase):
    def test_bare_delay_claim_on_a_leak_topic_is_softened(self):
        out, notes = apply_rumor_language(
            "GTA 6 is delayed to 2027.",
            topic="GTA 6 leak delay rumor",
        )
        self.assertNotEqual(out, "GTA 6 is delayed to 2027.")
        self.assertRegex(out.lower(), r"report(?:edly|s)|rumor")
        self.assertTrue(notes)

    def test_already_attributed_leak_is_left_alone(self):
        script = "Bloomberg reports GTA 6 is delayed to 2027."
        out, notes = apply_rumor_language(script, topic="GTA 6 leak")
        self.assertEqual(out, script)
        self.assertEqual(notes, [])

    def test_tapology_result_line_is_not_rewritten(self):
        script = "Ilia Topuria defeated Justin Gaethje at UFC 350."
        out, notes = apply_rumor_language(script, topic="UFC 350 results")
        self.assertEqual(out, script)
        self.assertEqual(notes, [])

    def test_reports_to_ea_is_not_caught(self):
        """Pattern catch: 'reports to EA' is employment, not a rumor hedge."""
        script = "The designer reports to EA on the next GTA."
        out, _notes = apply_rumor_language(script, topic="GTA 6 leak")
        self.assertIn("reports to EA", out)

    def test_known_gap_outlet_not_inferred_from_corpus(self):
        """We require an outlet-shaped token in the script, not the facts block.

        Closing this would pass the corpus into apply_rumor_language and copy
        the outlet name into the softened line.
        """
        out, _notes = apply_rumor_language(
            "GTA 6 is delayed to 2027.",
            topic="GTA 6 leak",
        )
        self.assertNotIn("Bloomberg", out)
