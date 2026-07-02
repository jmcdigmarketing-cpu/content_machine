"""Tests for headless key-facts input in scripts/auto_generate.py."""

import os
import tempfile
import unittest

from scripts.auto_generate import _collect_key_facts


class TestCollectKeyFacts(unittest.TestCase):
    def test_no_inputs_returns_empty(self):
        self.assertEqual(_collect_key_facts("", []), [])

    def test_repeated_fact_lines(self):
        facts = _collect_key_facts(
            "", ["Giannis traded to the Heat (Jun 30)", "Heat sent two first-round picks"]
        )
        self.assertEqual(len(facts), 2)
        self.assertIn("Giannis traded to the Heat (Jun 30)", facts)

    def test_facts_file_uses_paste_parser(self):
        block = (
            "Bucks trade Giannis Antetokounmpo to the Heat\n"
            "• Miami gets: Giannis Antetokounmpo\n"
            "• Milwaukee gets: Tyler Herro, 2027 first-round pick\n"
        )
        fd, path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(block)
            facts = _collect_key_facts(path, [])
        finally:
            os.unlink(path)
        self.assertTrue(facts)
        joined = " ".join(facts)
        self.assertIn("Giannis", joined)
        self.assertIn("Herro", joined)

    def test_missing_file_is_skipped_not_fatal(self):
        facts = _collect_key_facts(
            os.path.join(tempfile.gettempdir(), "does_not_exist_9f2.txt"),
            ["A real fact about the offseason 2026"],
        )
        self.assertEqual(len(facts), 1)

    def test_dedupe_across_file_and_flags(self):
        line = "Giannis Antetokounmpo traded to the Miami Heat for picks (Jun 30)"
        fd, path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(line + "\n")
            facts = _collect_key_facts(path, [line])
        finally:
            os.unlink(path)
        self.assertEqual(len(facts), 1)


if __name__ == "__main__":
    unittest.main()
