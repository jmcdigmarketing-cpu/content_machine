"""Tests for the Obsidian vault fact reader and the key-facts prompt."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import obsidian_facts as of
from core import vault_index
from core.ui import prompt_key_facts


class TestLoadFacts(unittest.TestCase):
    def setUp(self):
        vault_index.clear_cache()

    def tearDown(self):
        vault_index.clear_cache()

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

    def test_generic_shared_token_does_not_match(self):
        # Regression: a gaming note mentioning "Summer Game Fest" must NOT surface on
        # a UFC topic that merely says "this summer" (generic token leak).
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "gaming.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Gaming\n- Onimusha was a standout at Summer Game Fest 2026\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("Max Holloway will fight Conor McGregor this summer", "tapin")
            self.assertFalse(any("Onimusha" in f for f in facts))

    def test_evergreen_factual_note_surfaces_on_weak_match(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "nba.md").write_text(
                "---\nchannel: tapin\ntags: [facts, evergreen]\n---\n"
                "# NBA\n- Jaylen Brown was traded to the 76ers on July 1, 2026\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("completely unrelated topic xyz", "tapin")
            self.assertTrue(any("Jaylen Brown" in f for f in facts))

    def test_require_distinctive_blocks_genre_only_matches(self):
        # Live-run regression: a Palworld topic surfaced NBA/Marvel-Rivals facts via
        # generic tokens ("patch", "notes", "massive"). Under require_distinctive
        # those must be dropped while a real Palworld fact still surfaces.
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "rivals.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Marvel Rivals July 2026 Patch Notes\n"
                "- The July patch notes rework the massive support meta\n",
                encoding="utf-8",
            )
            (vault / "tapin" / "nba.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# NBA offseason\n"
                "- NBA teams show interest in massive defensive centers this offseason\n",
                encoding="utf-8",
            )
            (vault / "tapin" / "palworld.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Palworld\n- Palworld 1.0 released with notes exceeding Steam limits\n",
                encoding="utf-8",
            )
            topic = "Palworld's 1.0 patch notes are so massive Steam wouldn't accept them"
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                strict = of.load_facts(topic, "tapin", require_distinctive=True)
                loose = of.load_facts(topic, "tapin")
            self.assertTrue(any("Palworld 1.0" in f for f in strict))
            self.assertFalse(any("NBA" in f for f in strict))
            self.assertFalse(any("support meta" in f for f in strict))
            # Default behavior unchanged: the generic-token leak still exists there.
            self.assertTrue(any("Palworld 1.0" in f for f in loose))

    def test_generic_english_verbs_do_not_establish_topic_relevance(self):
        # Live-run regression (2026-08-14): the topic "…Salkilld, Thainara break
        # through" pulled Marvel Rivals facts into a UFC script on the single token
        # "break" (from "I break down the buffs"). Generic English verbs/adverbs are
        # not topic identity, only names/events are.
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "rivals.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Marvel Rivals\n"
                "- NetEase redesigning team-ups. I break down the hero buffs\n"
                "- There are over 50 characters in Marvel Rivals right through Season 9\n",
                encoding="utf-8",
            )
            (vault / "tapin" / "mma.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# MMA rankings\n- Quillan Salkilld submitted Mateusz Gamrot in round one\n",
                encoding="utf-8",
            )
            topic = "MMA divisional rankings: Quillan Salkilld, Alexia Thainara break through"
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                strict = of.load_facts(topic, "tapin", require_distinctive=True)
            self.assertTrue(any("Salkilld submitted" in f for f in strict))
            self.assertFalse(any("Marvel Rivals" in f for f in strict))
            self.assertFalse(any("NetEase" in f for f in strict))

    def test_require_distinctive_removes_evergreen_bypass(self):
        # Evergreen zero-overlap notes surface under the default path but must NOT
        # under require_distinctive (the operator-suggestions path).
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "nba.md").write_text(
                "---\nchannel: tapin\ntags: [facts, evergreen]\n---\n"
                "# NBA\n- Jaylen Brown was traded to the 76ers on July 1, 2026\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                strict = of.load_facts(
                    "Palworld 1.0 Steam launch", "tapin", require_distinctive=True
                )
                loose = of.load_facts("Palworld 1.0 Steam launch", "tapin")
            self.assertEqual(strict, [])
            self.assertTrue(any("Jaylen Brown" in f for f in loose))

    def test_strategy_playbook_excluded_from_key_facts(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "playbook.md").write_text(
                "---\nchannel: tapin\ntags: [facts, evergreen, strategy]\n---\n"
                "# Playbook\n- Fraud narratives outperform straight recaps\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("NBA offseason trades", "tapin")
            self.assertEqual(facts, [])

    def test_machine_beliefs_excluded_from_key_facts(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "_machine-beliefs.md").write_text(
                "---\nchannel: tapin\ntags: [machine, beliefs, evergreen]\n---\n"
                "# Beliefs\n"
                "- Prefer reports suggest over stating an unverified specific as fact\n"
                "- Competitor video titles show what's trending, NOT what's true\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("LeBron free agency", "tapin")
                self.assertEqual(facts, [])
                pb = of.load_playbook("tapin")
                self.assertTrue(any("reports suggest" in b for b in pb))

    def test_strategy_bullet_filtered_even_in_factual_note(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "mixed.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# NBA\n"
                "- Rankings and tier-list framings outperform highlight reactions\n"
                "- Giannis Antetokounmpo was traded to the Miami Heat on June 22, 2026\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("NBA trades Giannis", "tapin")
            joined = " ".join(facts)
            self.assertIn("Giannis", joined)
            self.assertNotIn("tier-list", joined)

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
    def test_auto_attaches_suggestions_and_takes_manual(self):
        # Default (VAULT_FACTS_AUTO on): relevant vault facts attach with NO prompt.
        outputs: list[str] = []
        inputs = iter(["Extra manual fact", ""])  # only fact-entry inputs consumed
        with patch("core.obsidian_facts.load_facts", return_value=["Suggested fact A"]):
            facts = prompt_key_facts(
                "topic",
                "tapin",
                print_fn=lambda *a, **k: outputs.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: next(inputs),
            )
        self.assertIn("Suggested fact A", facts)
        self.assertIn("Extra manual fact", facts)
        self.assertTrue(any("auto-attached" in o for o in outputs))

    def test_vault_sourced_facts_are_not_written_back(self):
        # Live-run regression (2026-08-14): re-saving auto-attached vault facts copied
        # them into a note titled with THIS topic, permanently stamping foreign facts
        # as this topic's own — a laundering loop that compounds every run. Only facts
        # new to the vault get persisted; the LLM still receives the full set.
        inputs = iter(["Brand new operator fact", ""])
        with (
            patch("core.obsidian_facts.load_facts", return_value=["Borrowed vault fact"]),
            patch("core.operator_facts.capture_facts_to_vault") as capture,
        ):
            capture.return_value = "some/note.md"
            facts = prompt_key_facts(
                "topic", "tapin", print_fn=lambda *a, **k: None, input_fn=lambda *_: next(inputs)
            )
        # Both reach the LLM...
        self.assertIn("Borrowed vault fact", facts)
        self.assertIn("Brand new operator fact", facts)
        # ...but only the new one is written back to the vault.
        capture.assert_called_once()
        persisted = capture.call_args[0][2]
        self.assertEqual(persisted, ["Brand new operator fact"])

    def test_vault_only_facts_write_nothing_back(self):
        # Nothing new => no vault write at all (run 65 wrote 8 borrowed facts).
        inputs = iter([""])
        with (
            patch("core.obsidian_facts.load_facts", return_value=["Borrowed A", "Borrowed B"]),
            patch("core.operator_facts.capture_facts_to_vault") as capture,
        ):
            facts = prompt_key_facts(
                "topic", "tapin", print_fn=lambda *a, **k: None, input_fn=lambda *_: next(inputs)
            )
        self.assertEqual(facts, ["Borrowed A", "Borrowed B"])
        capture.assert_not_called()

    def test_no_relevant_facts_skips_silently(self):
        outputs: list[str] = []
        inputs = iter([""])
        with patch("core.obsidian_facts.load_facts", return_value=[]):
            facts = prompt_key_facts(
                "topic",
                "tapin",
                print_fn=lambda *a, **k: outputs.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: next(inputs),
            )
        self.assertEqual(facts, [])
        self.assertTrue(any("skipped" in o for o in outputs))
        self.assertFalse(any("Use these?" in o for o in outputs))

    def test_pick_specific_suggestions(self):
        # Interactive pick survives behind VAULT_FACTS_AUTO=false.
        inputs = iter(["1 3", ""])  # pick suggestions 1 and 3, no manual additions
        with (
            patch.dict("os.environ", {"VAULT_FACTS_AUTO": "false"}, clear=False),
            patch("core.obsidian_facts.load_facts", return_value=["A", "B", "C"]),
        ):
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
        inputs = iter(["Suggested fact A", ""])  # auto-attached, then re-typed manually
        with patch("core.obsidian_facts.load_facts", return_value=["Suggested fact A"]):
            facts = prompt_key_facts(
                "topic", "tapin", print_fn=lambda *a, **k: None, input_fn=lambda *_: next(inputs)
            )
        self.assertEqual(facts, ["Suggested fact A"])

    def test_manual_facts_prioritized_over_vault_in_prompt_order(self):
        # Vault auto-attached first in UX, but manual facts must sort ahead for the LLM cap.
        inputs = iter(["Manual trade fact", ""])
        with patch("core.obsidian_facts.load_facts", return_value=["Vault suggestion"]):
            facts = prompt_key_facts(
                "topic", "tapin", print_fn=lambda *a, **k: None, input_fn=lambda *_: next(inputs)
            )
        self.assertEqual(facts[0], "Manual trade fact")
        self.assertIn("Vault suggestion", facts)


if __name__ == "__main__":
    unittest.main()
