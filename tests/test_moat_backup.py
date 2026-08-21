"""Moat backup plan — secrets excluded, temp dest only."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.moat_backup import apply_plan, plan, render


class TestMoatBackup(unittest.TestCase):
    def test_excludes_env_and_secrets(self):
        planned = plan("/tmp/backup-dest")
        blob = " ".join(planned.skipped_secrets).replace("\\", "/")
        self.assertIn(".env", blob)
        self.assertIn("secrets", blob)
        self.assertIn("quota_state.json", blob)
        text = render(planned)
        self.assertIn("dry-run", text)
        self.assertIn("excluded", text.lower())

    def test_apply_copies_traces_not_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            traces = Path(tmp) / "traces"
            traces.mkdir()
            (traces / "1.json").write_text("{}", encoding="utf-8")
            dest = Path(tmp) / "dest"
            with patch("core.moat_backup.TRACES_DIR", str(traces)):
                with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": "", "DATABASE_URL": ""}):
                    planned = plan(str(dest))
                    n = apply_plan(planned, apply=True)
            self.assertGreaterEqual(n, 1)
            self.assertTrue((dest / "traces" / "1.json").is_file())
            self.assertFalse((dest / ".env").exists())

    def test_dry_run_copies_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "dest"
            planned = plan(str(dest))
            self.assertEqual(apply_plan(planned, apply=False), 0)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
