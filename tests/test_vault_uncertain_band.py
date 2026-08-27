"""Candidate 329 P0: an anchor-less note must not vanish silently.

The competing-franchise fix closed the run-71 gap correctly — Marvel Rivals and SEGA no
longer attach to a GTA topic. But it required every note to share a *franchise anchor*
with the topic, and the anchor list is hand-kept (`_GAME_ANCHORS`). Measured:

    note "Rockstar investigation"
    bullet "Rockstar Games confirms the leak investigation is ongoing."
    topic  "GTA 6 leak forces Rockstar's parent to subpoena Microsoft and Discord"
    -> DROPPED, because "Rockstar" is not a franchise anchor

A note about the company at the centre of the story, dropped from a topic that names
that company — and dropped *silently*, so the operator never learns their own note was
excluded. That is worse than a visible false positive, which they can decline with `n`.

P0 keeps such notes and marks them **uncertain** rather than discarding them. The real
fix is the scoring matrix (P1-P4); this only stops the silent loss in the meantime.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.obsidian_facts import load_fact_records

TOPIC = "GTA 6 leak forces Rockstar's parent to subpoena Microsoft and Discord"
HDR = "---\nchannel: tapin\ntags: [facts]\n---\n\n"


class _Vault:
    def __init__(self, *notes: tuple[str, str]):
        self.notes = notes

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "vault" / "tapin"
        root.mkdir(parents=True)
        for name, body in self.notes:
            (root / name).write_text(HDR + body + "\n", encoding="utf-8")
        self.env = patch.dict(
            os.environ,
            {"OBSIDIAN_VAULT_PATH": str(Path(self.tmp.name) / "vault")},
            clear=False,
        )
        self.env.start()
        return self

    def __exit__(self, *exc):
        self.env.stop()
        self.tmp.cleanup()
        return False


def _records(*notes):
    with _Vault(*notes):
        return load_fact_records(TOPIC, "tapin", require_distinctive=True)


class TestAnchorLessNotesSurvive(unittest.TestCase):
    def test_the_rockstar_note_is_not_dropped(self):
        recs = _records(
            (
                "rockstar.md",
                "# Rockstar investigation\n- Rockstar Games confirms the leak "
                "investigation is ongoing.",
            ),
        )
        self.assertTrue(recs, "a note about the company in the topic must reach the operator")

    def test_it_is_marked_uncertain_rather_than_asserted(self):
        recs = _records(
            (
                "rockstar.md",
                "# Rockstar investigation\n- Rockstar Games confirms the leak "
                "investigation is ongoing.",
            ),
        )
        self.assertTrue(getattr(recs[0], "uncertain", False), "kept, but flagged for review")


class TestTheGapStaysClosed(unittest.TestCase):
    """P0 must not undo what the competing-franchise fix got right."""

    def test_marvel_rivals_still_excluded(self):
        recs = _records(
            (
                "rivals.md",
                "# Marvel Rivals\n- Marvel Rivals season 9 adds a Wolverine "
                "costume from the Horseman of Death era.",
            ),
        )
        self.assertEqual(recs, [])

    def test_a_matching_franchise_note_is_confident(self):
        recs = _records(
            ("gta.md", "# GTA 6 leak\n- Grand Theft Auto 6 leak footage spread across Discord."),
        )
        self.assertTrue(recs)
        self.assertFalse(getattr(recs[0], "uncertain", False), "a franchise match is not a guess")


class TestOperatorSeesTheSplit(unittest.TestCase):
    def test_prompt_reports_confident_and_uncertain_counts(self):
        from core.ui import format_vault_scan_line

        line = format_vault_scan_line(confident=3, uncertain=1)
        self.assertIn("3", line)
        self.assertIn("1", line)
        self.assertIn("uncertain", line.lower())

    def test_no_uncertain_reads_cleanly(self):
        from core.ui import format_vault_scan_line

        self.assertNotIn("uncertain", format_vault_scan_line(confident=2, uncertain=0).lower())


if __name__ == "__main__":
    unittest.main()
