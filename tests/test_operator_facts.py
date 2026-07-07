"""Tests for operator key-facts parse, dedupe, and prompt packing."""

import os
import unittest
from unittest.mock import patch

from core.operator_facts import (
    capture_facts_to_vault,
    dedupe_facts,
    facts_for_prompt,
    is_writing_tip,
    parse_pasted_block,
)


class TestWritingTips(unittest.TestCase):
    def test_filters_playbook_lines(self):
        self.assertTrue(is_writing_tip("Open with a specific fact, number, or contradiction"))
        self.assertTrue(is_writing_tip("Never invent a fight result, record, or event date"))
        self.assertFalse(is_writing_tip("Giannis Antetokounmpo traded to Miami Heat June 2026"))

    def test_playbook_retention_lines_filtered(self):
        self.assertTrue(
            is_writing_tip(
                "Short-form punchy for breaking reactions; longer analysis for rankings/predictions"
            )
        )
        self.assertTrue(is_writing_tip('Retention pivot ~30s in ("but here\'s the thing…")'))


class TestParsePastedBlock(unittest.TestCase):
    def test_groups_trade_block(self):
        block = """
76ers trade for Jaylen Brown (July 1)
76ers get:
• Jaylen Brown
Celtics get:
• Paul George
• 2031 unprotected first-round draft pick
"""
        facts = parse_pasted_block(block)
        self.assertGreaterEqual(len(facts), 1)
        joined = " ".join(facts)
        self.assertIn("Jaylen Brown", joined)
        self.assertIn("Paul George", joined)

    def test_plain_lines(self):
        facts = parse_pasted_block(
            "First declarative sentence here.\nSecond declarative sentence here."
        )
        self.assertEqual(len(facts), 2)


class TestFactsForPrompt(unittest.TestCase):
    def test_char_budget_fits_more_than_five(self):
        facts = [f"Trade fact {i}: Player X to Team Y on July {i}" for i in range(1, 16)]
        sent = facts_for_prompt(facts)
        self.assertGreater(len(sent), 5)

    def test_manual_priority_preserved(self):
        ordered = ["FIRST manual fact"] + [f"vault {i}" for i in range(20)]
        sent = facts_for_prompt(ordered)
        self.assertEqual(sent[0], "FIRST manual fact")

    def test_env_char_budget(self):
        facts = ["x" * 200 for _ in range(30)]
        with patch.dict(os.environ, {"OPERATOR_KEY_FACT_CHAR_BUDGET": "500"}):
            sent = facts_for_prompt(facts)
        self.assertLessEqual(sum(len(s) for s in sent), 500)


class TestDedupe(unittest.TestCase):
    def test_drops_duplicates_and_tips(self):
        raw = [
            "Giannis to Miami",
            "giannis to miami",
            "Open with a specific fact, number, or contradiction",
            "Kawhi to Raptors June 30",
        ]
        out = dedupe_facts(raw)
        self.assertEqual(len(out), 2)


class TestVaultCapture(unittest.TestCase):
    def test_capture_no_vault_is_noop(self):
        with patch("core.obsidian_facts._vault_path", return_value=None):
            self.assertIsNone(capture_facts_to_vault("tapin", "topic", ["a fact"]))


if __name__ == "__main__":
    unittest.main()
