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


class TestPublishedPathsAreExempt(unittest.TestCase):
    def test_an_old_published_file_is_not_a_victim(self) -> None:
        """#812. Unmodified plan() has no skip_paths; TypeError is the fail-first."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            published = root / "kept.mp4"
            unpublished = root / "draft.mp4"
            published.write_bytes(b"p" * 300)
            unpublished.write_bytes(b"d" * 300)
            os.utime(published, (1, 1))
            os.utime(unpublished, (2, 2))
            sidecar = root / "kept.srt"
            sidecar.write_text("1", encoding="utf-8")
            os.utime(sidecar, (1, 1))
            planned = plan(root, max_bytes=100, skip_paths=[str(published)])
            victims = {Path(v).name for v in planned.victims}
            self.assertIn("draft.mp4", victims)
            self.assertNotIn("kept.mp4", victims)
            self.assertNotIn("kept.srt", victims)
            deleted = apply_plan(planned, apply=True)
            self.assertGreaterEqual(deleted, 1)
            self.assertTrue(published.exists())
            self.assertFalse(unpublished.exists())
            self.assertTrue(sidecar.exists())


class TestOvernightRetentionIsDryByDefault(unittest.TestCase):
    def test_apply_env_off_does_not_delete(self) -> None:
        from core.artifact_retention import format_retention_line, retention_apply_enabled

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.mp4"
            old.write_bytes(b"x" * 200)
            os.utime(old, (1, 1))
            with patch.dict(
                os.environ,
                {
                    "OUTPUT_MAX_GB": "0.0000001",
                    "ARTIFACT_RETENTION_APPLY": "",
                    "OUTPUT_MAX_FILES": "",
                },
                clear=False,
            ):
                self.assertFalse(retention_apply_enabled())
                line = format_retention_line(root)
            self.assertTrue(old.exists())
            self.assertIn("retention", line.lower())

    def test_overnight_skip_path_prints_the_retention_line(self) -> None:
        from core.overnight import OvernightResult, render_overnight

        with patch.dict(os.environ, {"OUTPUT_MAX_GB": "", "OUTPUT_MAX_FILES": ""}, clear=False):
            text = render_overnight(
                OvernightResult(channel_id="tapin", quota_line="gated", requested=0)
            )
        self.assertIn("retention", text.lower())


if __name__ == "__main__":
    unittest.main()
