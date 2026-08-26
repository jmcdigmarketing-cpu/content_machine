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

    def test_known_gap_a_shared_token_without_a_named_franchise_still_matches(self):
        """Documents what the competing-anchor gate does NOT fix.

        Run 71's angle contained 'Wolverine'. A vault bullet that also says
        Wolverine but names no other franchise still shares a distinctive token
        and will attach. Invert this when subject-identity work can tell the
        Insomniac game from a costume mention without a franchise string.
        """
        tmp, env = self._vault(
            ("wolverine.md", f"# Wolverine rage\n- {SHARED_TOKEN_ONLY}"),
        )
        try:
            facts = of.load_facts(GTA_TOPIC, "tapin", require_distinctive=True)
        finally:
            env.stop()
            tmp.cleanup()
        self.assertTrue(any("Wolverine Rage" in f for f in facts))


if __name__ == "__main__":
    unittest.main()
