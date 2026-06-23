"""Tests for machine-belief writeback into the Obsidian vault."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import vault_writeback as vw

_ENTRIES = [
    {"topic": "UFC fraud callout", "engaged_rate": 0.45, "composite_score": 60, "domain": "ufc"},
    {"topic": "Gaming recap", "engaged_rate": 0.20, "composite_score": 40, "domain": "gaming"},
    {"topic": "Gaming tier list", "engaged_rate": 0.30, "composite_score": 55, "domain": "gaming"},
]


class TestBuildBeliefs(unittest.TestCase):
    def test_beliefs_are_domain_and_pattern_not_per_topic(self):
        # Beliefs should name domains and patterns, NOT recycle a literal past topic
        # (that reinforcement of fabricated seeds is the feedback loop we removed).
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.vault_writeback._pattern_beliefs", return_value=[]),
        ):
            beliefs = vw.build_channel_beliefs("tapin")
        joined = "\n".join(beliefs)
        self.assertIn("ufc is the strongest domain", joined)
        self.assertIn("gaming underperforms", joined)
        self.assertFalse(any("UFC fraud callout" in b for b in beliefs))
        self.assertFalse(any("repeat this angle" in b for b in beliefs))

    def test_pattern_beliefs_from_report(self):
        report = {
            "ready": True,
            "baseline": 0.25,
            "dimensions": {
                "angle": [
                    {"value": "fraud", "avg": 0.45, "n": 4, "delta": 0.20},
                    {"value": "recap", "avg": 0.10, "n": 3, "delta": -0.15},
                ]
            },
        }
        with patch("analytics.weekly_report.build_report", return_value=report):
            beliefs = vw._pattern_beliefs("tapin")
        joined = "\n".join(beliefs)
        self.assertIn("fraud angle over-performs", joined)
        self.assertIn("recap angle under-performs", joined)
        # No literal topic strings — patterns only.
        self.assertFalse(any("'" in b for b in beliefs))

    def test_pattern_beliefs_empty_when_report_not_ready(self):
        with patch("analytics.weekly_report.build_report", return_value={"ready": False}):
            self.assertEqual(vw._pattern_beliefs("tapin"), [])

    def test_no_entries_returns_empty(self):
        with (
            patch("core.best_bet._build_entries", return_value=[]),
            patch("core.vault_writeback._pattern_beliefs", return_value=[]),
        ):
            self.assertEqual(vw.build_channel_beliefs("tapin"), [])


class TestWriteBeliefs(unittest.TestCase):
    def test_writes_note_to_channel_folder(self):
        with tempfile.TemporaryDirectory() as d:
            with (
                patch("core.best_bet._build_entries", return_value=_ENTRIES),
                patch("core.vault_writeback._pattern_beliefs", return_value=[]),
                patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False),
            ):
                path = vw.write_channel_beliefs("tapin")
            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("channel: tapin", text)
            self.assertIn("tags: [machine, beliefs, evergreen]", text)
            self.assertIn("Machine belief:", text)
            self.assertEqual(path.parent.name, "tapin")

    def test_no_vault_returns_none(self):
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.vault_writeback._pattern_beliefs", return_value=[]),
            patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False),
        ):
            self.assertIsNone(vw.write_channel_beliefs("tapin"))

    def test_written_beliefs_are_readable_back(self):
        # The machine note must be picked up by the human-facing reader (loop closed).
        from core import obsidian_facts as of

        with tempfile.TemporaryDirectory() as d:
            with (
                patch("core.best_bet._build_entries", return_value=_ENTRIES),
                patch("core.vault_writeback._pattern_beliefs", return_value=[]),
                patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False),
            ):
                vw.write_channel_beliefs("tapin")
                facts = of.load_facts("UFC fraud callout angle", "tapin")
            self.assertTrue(any("Machine belief" in f for f in facts))


if __name__ == "__main__":
    unittest.main()
