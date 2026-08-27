"""Run-71 vault subject relevance: Marvel Rivals / SEGA must not attach to a GTA topic."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import obsidian_facts as of

# Live-run 71 strings (HANDOFF / debugging.md).
GTA_TOPIC = "GTA 6 Leak and Wolverine Rage Signal a Cultural Backlash"
GTA_FACT = "Take-Two filed subpoenas against Microsoft and Discord over the Grand Theft Auto leak."
MARVEL_FACT = "Marvel Rivals season 9 adds a Wolverine costume from the Horseman of Death era."
SEGA_FACT = "SEGA announced a new Sonic racing title for next spring."
# No franchise name — only the shared distinctive token. Distinctiveness cannot
# tell Insomniac's Wolverine from the Rivals costume.
SHARED_TOKEN_ONLY = "Wolverine Rage is trending after the summer of hate trailer."


class TestVaultSubjectRelevance(unittest.TestCase):
    def _vault(self, *notes: tuple[str, str]):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "vault" / "tapin"
        root.mkdir(parents=True)
        for name, body in notes:
            (root / name).write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n\n" + body + "\n",
                encoding="utf-8",
            )
        env = patch.dict(
            os.environ,
            {"OBSIDIAN_VAULT_PATH": str(Path(tmp.name) / "vault")},
            clear=False,
        )
        env.start()
        return tmp, env

    def test_gta_topic_keeps_take_two_and_drops_marvel_rivals(self):
        tmp, env = self._vault(
            ("gta.md", f"# GTA 6 leak\n- {GTA_FACT}"),
            ("rivals.md", f"# Marvel Rivals\n- {MARVEL_FACT}"),
            ("sega.md", f"# SEGA\n- {SEGA_FACT}"),
        )
        try:
            facts = of.load_facts(GTA_TOPIC, "tapin", require_distinctive=True)
        finally:
            env.stop()
            tmp.cleanup()
        joined = "\n".join(facts)
        self.assertIn("Take-Two", joined)
        self.assertNotIn("Marvel Rivals", joined)
        self.assertNotIn("SEGA", joined)

    def test_competing_character_title_without_franchise_is_uncertain_not_dropped(self):
        """Anchor-less notes are surfaced and flagged, not silently discarded (329 P0).

        This case used to assert the bullet did not attach at all. That was too strong
        for the mechanism behind it: excluding every note with no franchise anchor also
        excluded notes about the *people and companies* in the story — measured, a note
        saying "Rockstar Games confirms the leak investigation is ongoing" vanished from
        a GTA topic that names Rockstar, because `_GAME_ANCHORS` is a hand-kept list of
        games. Both cases produce an empty anchor set, so anchors cannot separate them.

        Until the scoring matrix can (329 P1-P4), such a bullet is returned marked
        `uncertain` and shown to the operator as such. A visible guess they can decline
        beats a silent exclusion they never learn about. Notes naming a *competing*
        franchise — Marvel Rivals, SEGA — are still dropped outright; see the test above.
        """
        tmp, env = self._vault(
            ("wolverine.md", f"# Wolverine rage\n- {SHARED_TOKEN_ONLY}"),
        )
        try:
            records = of.load_fact_records(GTA_TOPIC, "tapin", require_distinctive=True)
        finally:
            env.stop()
            tmp.cleanup()
        matched = [r for r in records if "Wolverine Rage" in r.claim]
        self.assertTrue(matched, "surfaced rather than silently dropped")
        self.assertTrue(matched[0].uncertain, "and flagged, because the subject is unproven")


if __name__ == "__main__":
    unittest.main()
