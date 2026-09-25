"""Fact-expiry watchdog — temp vault only."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core import fact_expiry as fe
from core import vault_index


class TestFactExpiry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        (self.vault / "tapin").mkdir()
        vault_index.clear_cache()
        self._env = patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(self.vault)})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        vault_index.clear_cache()
        self._tmp.cleanup()

    def _write(self, rel: str, text: str) -> None:
        path = self.vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_expired_note_is_flagged(self):
        self._write(
            "tapin/stale.md",
            "---\nchannel: tapin\nexpires: 2020-01-01\n---\n# Stale\n- old champ\n",
        )
        notes = fe.expired_notes("tapin", today=date(2026, 8, 20))
        self.assertEqual(len(notes), 1)
        self.assertIn("stale.md", notes[0]["path"])
        warns = fe.warning_lines("tapin", today=date(2026, 8, 20))
        self.assertTrue(warns)
        self.assertIn("expired", warns[0])

    def test_fresh_note_not_flagged(self):
        self._write(
            "tapin/fresh.md",
            "---\nchannel: tapin\nexpires: 2099-01-01\n---\n# Fresh\n- still true\n",
        )
        self.assertEqual(fe.expired_notes("tapin", today=date(2026, 8, 20)), [])

    def test_empty_vault_path_is_noop(self):
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}):
            vault_index.clear_cache()
            self.assertEqual(fe.expired_notes("tapin"), [])

    def test_command_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("vault-decay", COMMANDS)

    def test_lists_expired_note_from_a_temp_vault(self):
        import io
        from argparse import Namespace
        from contextlib import redirect_stdout

        from scripts.ops import COMMANDS

        self._write(
            "tapin/stale.md",
            "---\nchannel: tapin\nexpires: 2020-01-01\n---\n# Stale\n- old champ\n",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["vault-decay"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("stale.md", text)
        self.assertIn("2020-01-01", text)

    def test_empty_vault_is_honest_not_a_warning(self):
        import io
        from argparse import Namespace
        from contextlib import redirect_stdout

        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with (
            patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}),
            self.assertNoLogs(level="WARNING"),
            redirect_stdout(buf),
        ):
            vault_index.clear_cache()
            code = COMMANDS["vault-decay"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("no expired", buf.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
