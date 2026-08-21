"""output/ GB (and optional file-count) cap — temp dirs only."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.artifact_retention import apply_plan, plan, render, run


class TestArtifactRetention(unittest.TestCase):
    def test_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "old.mp4"
            b = root / "new.mp4"
            a.write_bytes(b"x" * 200)
            b.write_bytes(b"y" * 200)
            os.utime(a, (1, 1))
            os.utime(b, (9, 9))
            planned = plan(root, max_bytes=250)
            self.assertTrue(planned.victims)
            self.assertTrue(a.exists() and b.exists())
            deleted = apply_plan(planned, apply=False)
            self.assertEqual(deleted, 0)
            self.assertTrue(a.exists())

    def test_apply_deletes_oldest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "old.mp4"
            b = root / "new.mp4"
            a.write_bytes(b"x" * 200)
            b.write_bytes(b"y" * 200)
            os.utime(a, (1, 1))
            os.utime(b, (9, 9))
            planned = plan(root, max_bytes=250)
            deleted = apply_plan(planned, apply=True)
            self.assertEqual(deleted, 1)
            self.assertFalse(a.exists())
            self.assertTrue(b.exists())

    def test_file_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(3):
                (root / f"{i}.mp4").write_bytes(b"z")
            planned = plan(root, file_cap=1)
            self.assertGreaterEqual(len(planned.victims), 2)

    def test_env_off_means_no_byte_cap(self):
        with patch.dict(os.environ, {"OUTPUT_MAX_GB": "0", "OUTPUT_MAX_FILES": "off"}):
            with tempfile.TemporaryDirectory() as tmp:
                planned = plan(tmp)
        self.assertIsNone(planned.max_bytes)
        self.assertFalse(planned.victims)

    def test_render_mentions_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob = render(plan(tmp))
        self.assertIn("output/", blob)

    def test_run_default_is_dry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run(tmp, apply=False)
        self.assertEqual(out["deleted"], 0)


if __name__ == "__main__":
    unittest.main()
