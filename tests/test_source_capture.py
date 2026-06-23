"""Tests for capturing external links into the Obsidian vault for reuse."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core.obsidian_facts import load_facts
from core.source_capture import capture_sources


class TestCaptureSources(unittest.TestCase):
    def test_noop_without_vault(self):
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            self.assertIsNone(
                capture_sources("tapin", "GTA VI", [{"url": "https://x.com", "title": "X"}])
            )

    def test_noop_with_no_valid_sources(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False):
                self.assertIsNone(capture_sources("tapin", "GTA VI", []))
                # non-http entries are dropped
                self.assertIsNone(
                    capture_sources("tapin", "GTA VI", [{"url": "not-a-url", "title": "X"}])
                )

    def test_writes_channel_scoped_file(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False):
                path = capture_sources(
                    "tapin",
                    "GTA VI pre-orders",
                    [{"url": "https://rockstar.com/gta6", "title": "GTA VI pre-order prices"}],
                    today=date(2026, 6, 23),
                )
            self.assertIsNotNone(path)
            self.assertEqual(Path(path).parent.name, "tapin")
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("channel: tapin", text)
            self.assertIn("https://rockstar.com/gta6", text)
            self.assertIn("2026-06-23", text)
            self.assertIn("re: GTA VI pre-orders", text)

    def test_appends_and_dedupes_by_url(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False):
                capture_sources("tapin", "t1", [{"url": "https://a.com", "title": "A"}])
                capture_sources(
                    "tapin",
                    "t2",
                    [
                        {"url": "https://a.com", "title": "A again"},  # dup -> skipped
                        {"url": "https://b.com", "title": "B"},  # new -> appended
                    ],
                )
                text = (Path(d) / "tapin" / "_sources.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("https://a.com"), 1)
            self.assertIn("https://b.com", text)

    def test_captured_source_is_readable_by_load_facts(self):
        # The round trip: a captured source resurfaces on a related future topic.
        with tempfile.TemporaryDirectory() as d:
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False):
                capture_sources(
                    "tapin",
                    "Marvel Rivals season roadmap",
                    [{"url": "https://beebom.com/mr", "title": "Marvel Rivals Season 8.5 roadmap"}],
                )
                facts = load_facts("Marvel Rivals next update", "tapin")
            self.assertTrue(any("Marvel Rivals" in f for f in facts))


if __name__ == "__main__":
    unittest.main()
