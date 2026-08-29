"""ops ingest-clips — match capture filenames to the local library, dry-run first.

Never touches OneDrive. Library and source dirs are temp folders. ffmpeg is mocked
on --apply so CI does not need a real remux.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from argparse import Namespace
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

GTA_CAPTURE = "Grand Theft Auto V 2026.08.28 - 16.37.42.01.mp4"
UNMATCHED = "RandomPhoneClip 2026.01.01.mp4"


class TestClipIngestMatch(unittest.TestCase):
    def test_gta_capture_name_plans_dest_under_gta_v_folder(self):
        from assets.clip_ingest import plan_ingest

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "library"
            gta = library / "gaming" / "open world" / "GTA V"
            gta.mkdir(parents=True)
            (gta / "existing.mp4").write_bytes(b"clip")
            source = Path(tmp) / "captures"
            source.mkdir()
            (source / GTA_CAPTURE).write_bytes(b"src")

            rows = plan_ingest(source_dirs=[str(source)], library_root=str(library))

        matched = [r for r in rows if r.status == "matched"]
        self.assertEqual(len(matched), 1, rows)
        dest = Path(matched[0].dest)
        self.assertEqual(dest.parent.name, "GTA V")
        self.assertTrue(str(dest).lower().endswith(".mp4"))

    def test_unmatched_filename_is_listed_not_dumped_into_gaming(self):
        from assets.clip_ingest import plan_ingest

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "library"
            gaming = library / "gaming"
            gaming.mkdir(parents=True)
            (gaming / "filler.mp4").write_bytes(b"clip")
            source = Path(tmp) / "captures"
            source.mkdir()
            (source / UNMATCHED).write_bytes(b"src")

            rows = plan_ingest(source_dirs=[str(source)], library_root=str(library))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "unmatched")
        self.assertIsNone(rows[0].dest)
        self.assertNotIn(os.path.join("gaming", UNMATCHED), rows[0].source)

    def test_dry_run_does_not_copy(self):
        from assets.clip_ingest import ingest_clips

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "library"
            gta = library / "gaming" / "open world" / "GTA V"
            gta.mkdir(parents=True)
            (gta / "existing.mp4").write_bytes(b"clip")
            source = Path(tmp) / "captures"
            source.mkdir()
            src_file = source / GTA_CAPTURE
            src_file.write_bytes(b"src")
            index = Path(tmp) / "clip_index.json"

            with patch("assets.clip_ingest.CLIP_INDEX_FILE", str(index)):
                result = ingest_clips(
                    source_dirs=[str(source)],
                    library_root=str(library),
                    apply=False,
                )

            dests = [r.dest for r in result.rows if r.dest]
            self.assertTrue(dests)
            self.assertFalse(Path(dests[0]).exists())
            self.assertTrue(src_file.exists())
            self.assertFalse(index.exists())

    def test_apply_remuxes_to_dest_and_records_hud_null(self):
        """HUD is unknown: we do not invent a detector. duration/size come from ffprobe."""
        from assets.clip_ingest import ingest_clips

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "library"
            gta = library / "gaming" / "open world" / "GTA V"
            gta.mkdir(parents=True)
            (gta / "existing.mp4").write_bytes(b"clip")
            source = Path(tmp) / "captures"
            source.mkdir()
            (source / GTA_CAPTURE).write_bytes(b"src")
            index = Path(tmp) / "clip_index.json"

            def _fake_run(cmd, **kwargs):
                # ffmpeg ... output_path  OR  ffprobe
                if "ffprobe" in cmd[0] or cmd[0].endswith("ffprobe"):
                    if "duration" in " ".join(cmd):
                        return MagicMock(returncode=0, stdout="3.0\n", stderr="")
                    return MagicMock(
                        returncode=0,
                        stdout="1920|1080|h264\n",
                        stderr="",
                    )
                out = cmd[-1]
                Path(out).write_bytes(b"remuxed")
                return MagicMock(returncode=0, stdout="", stderr="")

            with (
                patch("assets.clip_ingest.CLIP_INDEX_FILE", str(index)),
                patch("assets.clip_ingest.subprocess.run", side_effect=_fake_run),
            ):
                result = ingest_clips(
                    source_dirs=[str(source)],
                    library_root=str(library),
                    apply=True,
                )

            copied = [r for r in result.rows if r.status == "copied"]
            self.assertEqual(len(copied), 1, result.rows)
            self.assertTrue(Path(copied[0].dest).is_file())
            payload = json.loads(index.read_text(encoding="utf-8"))
            meta = payload["clips"][copied[0].dest]
            self.assertIsNone(meta.get("hud"))
            self.assertEqual(meta.get("duration_s"), 3.0)
            self.assertEqual(meta.get("width"), 1920)
            self.assertEqual(meta.get("height"), 1080)


class TestIngestClipsCommand(unittest.TestCase):
    def test_command_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("ingest-clips", COMMANDS)

    def test_ops_dry_run_prints_matched_line(self):
        from scripts.ops import cmd_ingest_clips

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "library"
            gta = library / "gaming" / "open world" / "GTA V"
            gta.mkdir(parents=True)
            (gta / "existing.mp4").write_bytes(b"clip")
            source = Path(tmp) / "captures"
            source.mkdir()
            (source / GTA_CAPTURE).write_bytes(b"src")

            args = Namespace(apply=False, move=False)
            buf = StringIO()
            with (
                patch("assets.clip_ingest.default_source_dirs", return_value=[str(source)]),
                patch("assets.clip_ingest.BASE_VIDEO_DIR", str(library)),
                patch("sys.stdout", buf),
            ):
                code = cmd_ingest_clips(args)
        self.assertEqual(code, 0)
        blob = buf.getvalue()
        self.assertIn("DRY RUN", blob)
        self.assertIn("GTA V", blob)
        self.assertIn("matched", blob.lower())
