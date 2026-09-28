"""#558: a vault line previewing an event stops feeding the prompt once the event is over.

Only a note-level `expires:` retired anything (`core/fact_expiry`), and nobody writes one
on a quick preview note. "Topuria vs Holloway is set for Oct 4" was still handed to the
script as a current fact in November - the model would then preview a fight that has
already happened. `fact_recency.stale_preview` recognises a preview line whose every date
is past; `obsidian_facts.load_fact_records` skips it. The vault file is not edited (the
operator's notes stay theirs); `ops vault-decay` lists what stopped being used.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core.vault import index as vault_index

NOTE_DAY = date(2026, 9, 20)
PREVIEW = "Topuria vs Holloway is set for Oct 4 in Abu Dhabi."
RESULT = "Topuria knocked out Holloway on Oct 4 in Abu Dhabi."


class StalePreviewTests(unittest.TestCase):
    def test_a_preview_whose_date_has_passed(self):
        from core.fact_recency import stale_preview

        self.assertTrue(stale_preview(PREVIEW, NOTE_DAY, date(2026, 10, 10)))

    def test_before_the_event_it_is_kept(self):
        from core.fact_recency import stale_preview

        self.assertFalse(stale_preview(PREVIEW, NOTE_DAY, date(2026, 10, 1)))
        self.assertFalse(stale_preview(PREVIEW, NOTE_DAY, date(2026, 10, 4)))  # fight day

    def test_a_result_line_is_never_touched(self):
        from core.fact_recency import stale_preview

        self.assertFalse(stale_preview(RESULT, NOTE_DAY, date(2026, 11, 10)))

    def test_a_line_with_no_date_is_kept(self):
        from core.fact_recency import stale_preview

        line = "Topuria will defend the belt next."
        self.assertFalse(stale_preview(line, NOTE_DAY, date(2027, 5, 1)))

    def test_a_yearless_date_rolls_into_the_next_year(self):
        from core.fact_recency import stale_preview

        line = "The rematch is scheduled for Jan 12."
        december = date(2026, 12, 15)
        self.assertFalse(stale_preview(line, december, date(2026, 12, 20)))
        self.assertFalse(stale_preview(line, december, date(2027, 1, 5)))
        self.assertTrue(stale_preview(line, december, date(2027, 1, 20)))

    def test_one_future_date_keeps_the_line(self):
        from core.fact_recency import stale_preview

        line = "After the Oct 4 card, the next event is set for November 15."
        self.assertFalse(stale_preview(line, NOTE_DAY, date(2026, 10, 10)))

    def test_explicit_years_and_iso_dates(self):
        from core.fact_recency import stale_preview

        self.assertTrue(stale_preview("GTA VI will launch on 2026-05-26.", None, date(2026, 9, 1)))
        self.assertTrue(
            stale_preview("The patch is slated for March 3, 2026.", None, date(2026, 9, 1))
        )

    def test_without_a_note_date_a_yearless_date_is_judged_conservatively(self):
        from core.fact_recency import stale_preview

        # No `date:` in the note: "Oct 4" resolves to the current year only.
        self.assertTrue(stale_preview(PREVIEW, None, date(2026, 10, 10)))
        self.assertFalse(stale_preview(PREVIEW, None, date(2027, 9, 1)))


class _VaultCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        vault_index.clear_cache()
        self._env = patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(self.vault)})
        self._env.start()
        note = self.vault / "tapin" / "topuria-holloway.md"
        note.parent.mkdir(parents=True)
        note.write_text(
            "---\nchannel: tapin\ndate: 2026-09-20\n---\n# Topuria Holloway\n"
            f"- {PREVIEW}\n- Topuria is the featherweight champion.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._env.stop()
        vault_index.clear_cache()
        self._tmp.cleanup()


class LoaderTests(_VaultCase):
    def _claims(self, today: date) -> list[str]:
        from core.obsidian_facts import load_fact_records

        return [r.claim for r in load_fact_records("Topuria Holloway", "tapin", today=today)]

    def test_after_the_event_the_preview_is_not_loaded(self):
        claims = self._claims(date(2026, 10, 10))
        self.assertNotIn(PREVIEW, claims)
        self.assertIn("Topuria is the featherweight champion.", claims)

    def test_before_the_event_it_is(self):
        self.assertIn(PREVIEW, self._claims(date(2026, 10, 1)))


class VaultDecayTests(_VaultCase):
    def test_the_report_names_the_retired_previews(self):
        from core.fact_expiry import stale_previews

        found = stale_previews("tapin", today=date(2026, 10, 10))
        self.assertEqual([f["line"] for f in found], [PREVIEW])

    def test_ops_vault_decay_prints_them(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with (
            redirect_stdout(buf),
            patch("core.fact_expiry.date") as fake,
        ):
            fake.today.return_value = date(2026, 10, 10)
            COMMANDS["vault-decay"][1](Namespace(channel="tapin"))
        text = buf.getvalue()
        self.assertIn("1 preview line(s) about events that have happened", text)
        self.assertIn("Oct 4", text)


if __name__ == "__main__":
    unittest.main()
