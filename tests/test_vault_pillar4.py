"""Pillar 4 (Obsidian knowledge OS) tests — mtime vault index, run dossiers,
playbook read path. All use temp vaults + patched OBSIDIAN_VAULT_PATH (never the
operator's real vault — tests/CLAUDE.md)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import obsidian_facts as of
from core import vault_dossiers, vault_index


class VaultCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        (self.vault / "tapin").mkdir()
        vault_index.clear_cache()  # per-process cache only — no on-disk index
        self._env = patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(self.vault)}, clear=False)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        vault_index.clear_cache()
        self._tmp.cleanup()

    def _write(self, rel, text):
        path = self.vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class TestVaultIndex(VaultCase):
    def test_index_reflects_edits_via_mtime(self):
        note = self._write(
            "tapin/ufc.md",
            "---\nchannel: tapin\ntags: [facts]\n---\n# UFC\n- Makhachev is the champion\n",
        )
        facts = of.load_facts("Makhachev champion", "tapin")
        self.assertTrue(any("Makhachev" in f for f in facts))

        # Rewrite with a newer mtime — the index must re-parse, not serve stale.
        import os
        import time

        note.write_text(
            "---\nchannel: tapin\ntags: [facts]\n---\n# UFC\n- Topuria is the champion\n",
            encoding="utf-8",
        )
        os.utime(note, (time.time() + 10, time.time() + 10))
        facts = of.load_facts("Topuria champion", "tapin")
        self.assertTrue(any("Topuria" in f for f in facts))
        self.assertFalse(any("Makhachev" in f for f in facts))

    def test_deleted_note_pruned(self):
        note = self._write(
            "tapin/x.md", "---\nchannel: tapin\ntags: [facts]\n---\n# X\n- Fact about Xylophone\n"
        )
        self.assertTrue(of.load_facts("Xylophone", "tapin"))
        note.unlink()
        vault_index.clear_cache()
        self.assertEqual(of.load_facts("Xylophone", "tapin"), [])

    def test_parse_cached_per_process(self):
        self._write(
            "tapin/n.md", "---\nchannel: tapin\ntags: [facts]\n---\n# N\n- Fact about Nebula\n"
        )
        of.load_facts("Nebula", "tapin")  # populates the per-process cache
        cache = vault_index._CACHE.get(str(self.vault)) or {}
        self.assertEqual(len(cache), 1)  # the one note is parsed and cached
        mtime, entry = next(iter(cache.values()))
        self.assertIn("Nebula", " ".join(entry.bullets))


class TestExistingBehaviorPreserved(VaultCase):
    def test_channel_scope_and_relevance(self):
        self._write(
            "tapin/makhachev.md",
            "---\nchannel: tapin\ntags: [facts]\n---\n"
            "# Makhachev\n- Islam Makhachev is the current lightweight champion\n",
        )
        self._write(
            "tapin/unrelated.md", "---\nchannel: tapin\n---\n# Cooking\n- Add salt to taste\n"
        )
        facts = of.load_facts("Makhachev lightweight title", "tapin")
        self.assertTrue(any("Makhachev" in f for f in facts))
        self.assertFalse(any("salt" in f.lower() for f in facts))


class TestPlaybook(VaultCase):
    def test_reads_strategy_notes_excluded_from_facts(self):
        self._write(
            "tapin/playbook.md",
            "---\nchannel: tapin\ntags: [strategy]\n---\n"
            "# Playbook\n- Fraud narratives outperform straight recaps\n"
            "- Lead with the upset angle\n",
        )
        # Not a fact...
        self.assertEqual(of.load_facts("NBA trades", "tapin"), [])
        # ...but IS playbook guidance.
        pb = of.load_playbook("tapin")
        self.assertTrue(any("Fraud narratives" in b for b in pb))

    def test_machine_beliefs_included_in_playbook(self):
        self._write(
            "tapin/_machine-beliefs.md",
            "---\nchannel: tapin\ntags: [machine, beliefs, evergreen]\n---\n"
            "# Beliefs\n- Machine belief: gaming is the strongest domain\n",
        )
        pb = of.load_playbook("tapin")
        self.assertTrue(any("strongest domain" in b for b in pb))

    def test_playbook_block_bounded_and_labeled(self):
        self._write(
            "tapin/playbook.md",
            "---\nchannel: tapin\ntags: [strategy]\n---\n# P\n"
            + "".join(f"- Strategy rule number {i} that is reasonably long\n" for i in range(30)),
        )
        block = of.playbook_block("tapin", char_budget=200)
        self.assertIn("CHANNEL PLAYBOOK", block)
        self.assertIn("NOT facts", block)
        self.assertLessEqual(len(block), 500)  # bounded

    def test_playbook_empty_without_vault(self):
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            self.assertEqual(of.load_playbook("tapin"), [])
            self.assertEqual(of.playbook_block("tapin"), "")


# The operator's real `tapin/playbook.md` in section order: two "Narratives that
# work" sections carrying 12 bullets, and only then the hook and discipline rules.
# `limit=8` in file order therefore reached the prompt as 8/8 narrative heuristics
# and cut 100% of the file's own anti-hallucination rules — the strongest framing
# input in the system was one family of guidance the operator never ranked first.
_REAL_SHAPED_PLAYBOOK = (
    "---\nchannel: tapin\ntags: [facts, evergreen]\n---\n"
    "# TapIn — Channel Playbook\n\n"
    "## Narratives that work (UFC/sports)\n"
    '- "Fraud" / overrated-callout narratives outperform straight recaps\n'
    "- Rankings and tier-list framings outperform highlight reactions\n"
    "- Prediction/analysis angles age better than just-happened news framing\n"
    "- Snubbed / disrespected angles drive comments\n"
    "- Rivalry and beef framing beats neutral previews\n"
    "- Implication hooks invite debate\n"
    "- Underdog/upset stories travel further than favorite-wins stories\n\n"
    "## Narratives that work (gaming)\n"
    '- "Is X dead?" / decline takes drive defensive engagement\n'
    "- Reveal reactions and biggest-reveals-ranked outperform straight news\n"
    "- Meta debates drive comments but only with verified specifics\n"
    "- Nostalgia/legacy framing on returning franchises lands well\n"
    "- Community-sentiment angles are safe when specifics are thin\n\n"
    "## Hook rules (first line under 12 words)\n"
    "- Open with a specific fact, number, or contradiction\n\n"
    "## Hard rules (anti-hallucination)\n"
    "- Never invent a fight result, record, event date, patch number, hero, or season\n"
    "- Prefer reports-suggest over stating an unverified specific as fact\n"
    "- Competitor video titles show what is trending, NOT what is true\n"
)


class TestPlaybookDoesNotTruncateAwayTheDisciplineRules(VaultCase):
    """Selection was file/bullet order with an early return, so a note whose
    narrative sections come first spent the whole budget before reaching the
    rules that keep the script honest."""

    def test_the_block_carries_more_than_one_family_of_guidance(self):
        self._write("tapin/playbook.md", _REAL_SHAPED_PLAYBOOK)
        block = of.playbook_block("tapin", limit=8)

        self.assertIn("CHANNEL PLAYBOOK", block)
        self.assertIn(
            "Never invent a fight result",
            block,
            "the anti-hallucination rules never reach the prompt",
        )

    def test_narrative_guidance_still_survives(self):
        """The fix must rebalance the block, not invert it."""
        self._write("tapin/playbook.md", _REAL_SHAPED_PLAYBOOK)
        block = of.playbook_block("tapin", limit=8)
        self.assertIn("outperform", block)

    def test_a_single_section_note_is_unaffected(self):
        """No sections to balance across — behaviour must be the old one."""
        self._write(
            "tapin/playbook.md",
            "---\nchannel: tapin\ntags: [strategy]\n---\n# P\n"
            + "".join(f"- Strategy rule {i} outperforms the alternative\n" for i in range(12)),
        )
        self.assertEqual(len(of.load_playbook("tapin", limit=5)), 5)

    def test_the_char_budget_skips_an_overlong_bullet_instead_of_stopping(self):
        """`playbook_block` used `break`, so one long bullet ended the block and
        everything after it was lost — the same silent-drop defect run 74 found in
        the fact path."""
        self._write(
            "tapin/playbook.md",
            "---\nchannel: tapin\ntags: [strategy]\n---\n# P\n"
            "- Short rule that outperforms\n"
            f"- {'x' * 400} narratives\n"
            "- Never invent a fight result or record\n",
        )
        block = of.playbook_block("tapin", limit=8, char_budget=200)
        self.assertIn("Short rule", block)
        self.assertIn("Never invent", block, "a long bullet ended the block early")


def _run_record(run_id=5, channel="tapin"):
    r = MagicMock()
    r.id = run_id
    r.channel_id = channel
    r.selected_topic = "Topuria vs Gaethje breakdown"
    r.input_topic = "UFC 350"
    r.title = "Topuria's Toughest Test"
    r.status = "rendered"
    r.composite_score = 78.0
    r.features_json = json.dumps({"domain": "ufc", "angle": "prediction", "cost": {"total": 0.04}})
    r.quality_json = json.dumps({"hook_score": 72, "authenticity_score": 85, "ungrounded_count": 0})
    r.script_preview = "Topuria defends against Gaethje. Here is why it matters."
    r.timings_json = "{}"
    return r


class TestRunDossiers(VaultCase):
    def test_write_dossier_and_excluded_from_facts(self):
        record = _run_record()
        repo = MagicMock()
        repo.get.return_value = record
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = []
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            path = vault_dossiers.write_run_dossier(5)
            self.assertIsNotNone(path)
            body = Path(path).read_text(encoding="utf-8")
            self.assertIn("_runs", str(path))
            self.assertIn("5_", Path(path).name)
            self.assertNotRegex(Path(path).name, r"^\d{4}-\d{2}-\d{2}_")
            self.assertIn("Topuria", body)
            self.assertIn("tags: [run, machine]", body)
            # A dossier is a record, not a fact — it must not surface via load_facts.
            vault_index.clear_cache()
            facts = of.load_facts("Topuria Gaethje breakdown", "tapin")
        self.assertFalse(any("here is why it matters" in f.lower() for f in facts))

    def test_write_dossier_noop_without_run(self):
        self.assertIsNone(vault_dossiers.write_run_dossier(None))

    def test_refresh_same_run_does_not_clone_path(self):
        record = _run_record(5)
        repo = MagicMock()
        repo.get.return_value = record
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = []
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            a = vault_dossiers.write_run_dossier(5)
            b = vault_dossiers.write_run_dossier(5)
        self.assertEqual(a, b)
        runs = list((self.vault / "tapin" / "_runs").glob("*.md"))
        self.assertEqual(len(runs), 1)

    def test_refresh_dossiers_counts_written(self):
        runs = [_run_record(5), _run_record(6)]
        repo = MagicMock()
        repo.list_for_channel.return_value = runs
        repo.get.side_effect = lambda rid: next((r for r in runs if r.id == rid), None)
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = []
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            n = vault_dossiers.refresh_dossiers("tapin")
        self.assertEqual(n, 2)

    def test_weekly_report_note_written(self):
        path = vault_dossiers.write_weekly_report_note("tapin", "Weekly intelligence - tapin\n...")
        self.assertIsNotNone(path)
        self.assertIn("_reports", str(path))
        self.assertIn("Weekly report", Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
