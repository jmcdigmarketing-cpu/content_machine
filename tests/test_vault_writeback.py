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
    def test_beliefs_rank_domains_and_topics(self):
        with patch("core.best_bet._build_entries", return_value=_ENTRIES):
            beliefs = vw.build_channel_beliefs("tapin")
        joined = "\n".join(beliefs)
        self.assertIn("ufc is the strongest domain", joined)
        self.assertIn("gaming underperforms", joined)
        self.assertTrue(any("UFC fraud callout" in b for b in beliefs))

    def test_no_entries_returns_empty(self):
        with patch("core.best_bet._build_entries", return_value=[]):
            self.assertEqual(vw.build_channel_beliefs("tapin"), [])

    def test_falls_back_to_signal_score_without_engagement(self):
        entries = [
            {"topic": "A", "engaged_rate": None, "composite_score": 80, "domain": "ufc"},
            {"topic": "B", "engaged_rate": None, "composite_score": 50, "domain": "ufc"},
        ]
        with patch("core.best_bet._build_entries", return_value=entries):
            beliefs = vw.build_channel_beliefs("tapin")
        self.assertTrue(any("scored highly on signals" in b for b in beliefs))


class TestWriteBeliefs(unittest.TestCase):
    def test_writes_note_to_channel_folder(self):
        with tempfile.TemporaryDirectory() as d:
            with (
                patch("core.best_bet._build_entries", return_value=_ENTRIES),
                patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False),
            ):
                path = vw.write_channel_beliefs("tapin")
            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("channel: tapin", text)
            self.assertIn("tags: [machine, beliefs]", text)
            self.assertIn("Machine belief:", text)
            self.assertEqual(path.parent.name, "tapin")

    def test_no_vault_returns_none(self):
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False),
        ):
            self.assertIsNone(vw.write_channel_beliefs("tapin"))

    def test_written_beliefs_are_readable_back(self):
        # The machine note must be picked up by the human-facing reader (loop closed).
        from core import obsidian_facts as of

        with tempfile.TemporaryDirectory() as d:
            with (
                patch("core.best_bet._build_entries", return_value=_ENTRIES),
                patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False),
            ):
                vw.write_channel_beliefs("tapin")
                facts = of.load_facts("UFC fraud callout angle", "tapin")
            self.assertTrue(any("Machine belief" in f for f in facts))


if __name__ == "__main__":
    unittest.main()
