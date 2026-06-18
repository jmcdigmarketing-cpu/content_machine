"""Tests for the Obsidian vault fact reader and the key-facts prompt."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import obsidian_facts as of
from core.ui import prompt_key_facts


class TestLoadFacts(unittest.TestCase):
    def test_unset_vault_returns_empty(self):
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            self.assertEqual(of.load_facts("anything", "tapin"), [])

    def test_missing_vault_returns_empty(self):
        with patch.dict(
            "os.environ", {"OBSIDIAN_VAULT_PATH": "C:/no/such/vault/path"}, clear=False
        ):
            self.assertEqual(of.load_facts("anything", "tapin"), [])

    def test_reads_relevant_bullets_with_channel_scope(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "makhachev.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Makhachev\n"
                "- Islam Makhachev is the current lightweight champion as of June 2026\n"
                "- He defended the title at UFC 311\n",
                encoding="utf-8",
            )
            # A finance note that should NOT match a tapin UFC topic.
            (vault / "tapin" / "unrelated.md").write_text(
                "---\nchannel: tapin\n---\n# Cooking\n- Add salt to taste\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("Makhachev lightweight title defense", "tapin")
            self.assertTrue(
                any("Makhachev is the current lightweight champion" in f for f in facts)
            )
            self.assertFalse(any("salt" in f.lower() for f in facts))

    def test_channel_scoping_excludes_other_channel(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "moneywise.md").write_text(
                "---\nchannel: moneywise\ntags: [facts]\n---\n# Fed\n- Rate held at 5 percent\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("Fed rate decision", "tapin")
            self.assertEqual(facts, [])

    def test_dated_facts_note_does_not_leak_to_unrelated_topic(self):
        # A tags:[facts] (non-evergreen) note must surface only on topic match,
        # not bleed onto unrelated topics in the same channel.
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "ufc.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# UFC\n- Gaethje is the lightweight champion\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("Zelda gameplay tips", "tapin")
            self.assertEqual(facts, [])

    def test_evergreen_note_surfaces_on_any_topic(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "playbook.md").write_text(
                "---\nchannel: tapin\ntags: [facts, evergreen]\n---\n"
                "# Playbook\n- Fraud narratives outperform recaps\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("completely unrelated topic xyz", "tapin")
            self.assertTrue(any("Fraud narratives" in f for f in facts))

    def test_strips_markdown_emphasis(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "facts").mkdir()
            (vault / "facts" / "note.md").write_text(
                "# Topic\n- **Champion** is [Jon Jones](http://x) per `record` 27-1\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("Jon Jones champion record", "tapin")
            self.assertTrue(facts)
            self.assertNotIn("**", facts[0])
            self.assertNotIn("[", facts[0])


class TestPromptKeyFacts(unittest.TestCase):
    def test_accepts_suggestions_and_manual(self):
        outputs: list[str] = []
        inputs = iter(["", "Extra manual fact", ""])  # accept all suggestions, add one, stop
        with patch("core.obsidian_facts.load_facts", return_value=["Suggested fact A"]):
            facts = prompt_key_facts(
                "topic",
                "tapin",
                print_fn=lambda *a, **k: outputs.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: next(inputs),
            )
        self.assertIn("Suggested fact A", facts)
        self.assertIn("Extra manual fact", facts)

    def test_pick_specific_suggestions(self):
        inputs = iter(["1 3", ""])  # pick suggestions 1 and 3, no manual additions
        with patch("core.obsidian_facts.load_facts", return_value=["A", "B", "C"]):
            facts = prompt_key_facts(
                "topic", "tapin", print_fn=lambda *a, **k: None, input_fn=lambda *_: next(inputs)
            )
        self.assertEqual(facts, ["A", "C"])

    def test_no_suggestions_open_ended(self):
        inputs = iter(["Fact one", "Fact two", ""])
        with patch("core.obsidian_facts.load_facts", return_value=[]):
            facts = prompt_key_facts(
                "topic", "tapin", print_fn=lambda *a, **k: None, input_fn=lambda *_: next(inputs)
            )
        self.assertEqual(facts, ["Fact one", "Fact two"])

    def test_dedupes(self):
        inputs = iter(["", "Suggested fact A", ""])  # accept suggestion, re-type same manually
        with patch("core.obsidian_facts.load_facts", return_value=["Suggested fact A"]):
            facts = prompt_key_facts(
                "topic", "tapin", print_fn=lambda *a, **k: None, input_fn=lambda *_: next(inputs)
            )
        self.assertEqual(facts, ["Suggested fact A"])


if __name__ == "__main__":
    unittest.main()
