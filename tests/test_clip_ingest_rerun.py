"""#960: `ops ingest-clips --apply` is safe to stop and run again (operator, 2026-10-04).

The operator's first `--apply` re-encoded long Xbox captures with no progress line, looked hung,
and was stopped with Ctrl+C. That left a half-written mp4 in the game folder - ffmpeg wrote
straight to the clip's final name, and the renderer picks any .mp4 there - and a second run would
have imported every finished capture again as `<name>_2.mp4`: nothing remembered which captures
were in. "Grand Theft Auto Online" captures matched no folder, and `ops footage` still said an
empty niche "falls back to a random game", which #955 ended.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

CAPTURE = "UFC® 5-2026_06_16-00_17_00.mp4"


def _library(tmp: Path) -> tuple[Path, Path, Path]:
    library = tmp / "library"
    ufc = library / "gaming" / "sports" / "UFC 5"
    ufc.mkdir(parents=True)
    (ufc / "existing.mp4").write_bytes(b"clip")
    source = tmp / "captures"
    source.mkdir()
    (source / CAPTURE).write_bytes(b"src")
    return library, ufc, source


def _fake_run(cmd, **kwargs):
    if "ffprobe" in cmd[0]:
        if "duration" in " ".join(cmd):
            return MagicMock(returncode=0, stdout="3.0\n", stderr="")
        return MagicMock(returncode=0, stdout="1920|1080|h264\n", stderr="")
    Path(cmd[-1]).write_bytes(b"remuxed")
    return MagicMock(returncode=0, stdout="", stderr="")


class RerunTests(unittest.TestCase):
    def _ingest(self, tmp, library, source, *, apply=True, run=_fake_run, progress=None):
        from assets.clip_ingest import ingest_clips

        with (
            patch("assets.clip_ingest.CLIP_INDEX_FILE", str(tmp / "clip_index.json")),
            patch("assets.clip_ingest.subprocess.run", side_effect=run),
        ):
            return ingest_clips(
                source_dirs=[str(source)],
                library_root=str(library),
                apply=apply,
                progress=progress,
            )

    def test_a_second_run_does_not_import_the_same_capture_again(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            library, ufc, source = _library(tmp)
            first = self._ingest(tmp, library, source)
            second = self._ingest(tmp, library, source)
            self.assertEqual([r.status for r in first.rows], ["copied"])
            self.assertEqual([r.status for r in second.rows], ["imported"])
            self.assertEqual(sorted(p.name for p in ufc.iterdir()),
                             ["UFC® 5-2026_06_16-00_17_00.mp4", "existing.mp4"])  # fmt: skip

    def test_an_interrupted_remux_leaves_no_clip_behind(self):
        def interrupted(cmd, **kwargs):
            if "ffprobe" in cmd[0]:
                return _fake_run(cmd, **kwargs)
            Path(cmd[-1]).write_bytes(b"half a file")
            raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            library, ufc, source = _library(tmp)
            with self.assertRaises(KeyboardInterrupt):
                self._ingest(tmp, library, source, run=interrupted)
            self.assertEqual([p.name for p in ufc.iterdir()], ["existing.mp4"])

    def test_a_half_written_clip_from_an_old_run_is_replaced_not_duplicated(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            library, ufc, source = _library(tmp)
            (ufc / "UFC® 5-2026_06_16-00_17_00.mp4").write_bytes(b"half")  # in no index
            result = self._ingest(tmp, library, source)
            self.assertEqual([r.status for r in result.rows], ["copied"])
            self.assertEqual(sorted(p.name for p in ufc.iterdir()),
                             ["UFC® 5-2026_06_16-00_17_00.mp4", "existing.mp4"])  # fmt: skip
            self.assertEqual((ufc / CAPTURE).read_bytes(), b"remuxed")

    def test_each_file_reports_progress(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            library, _ufc, source = _library(tmp)
            self._ingest(tmp, library, source, progress=seen.append)
        self.assertEqual(len(seen), 1)
        self.assertIn("1/1", seen[0])
        self.assertIn("UFC 5", seen[0])


class MatchTests(unittest.TestCase):
    def test_gta_online_captures_go_to_gta_v(self):
        from assets.clip_ingest import match_folder

        folders = ["/lib/gaming/open world/GTA V", "/lib/gaming/sports/UFC 5"]
        name = "Grand Theft Auto Online (Xbox Series X_S)-2026_06_23-01_11_15.mp4"
        self.assertEqual(match_folder(name, folders), "/lib/gaming/open world/GTA V")


class CoverageTextTests(unittest.TestCase):
    def test_an_empty_niche_no_longer_promises_a_random_game(self):
        from assets.clip_ingest import render_coverage

        text = render_coverage([{"niche": "Football", "folder": "", "clips": 0}])
        self.assertNotIn("random game", text)
        self.assertIn("stock", text)


class CommandTests(unittest.TestCase):
    def test_apply_prints_as_it_goes(self):
        import io
        from argparse import Namespace
        from contextlib import redirect_stdout

        from scripts.ops import cmd_ingest_clips

        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            library, _ufc, source = _library(tmp)
            buf = io.StringIO()
            with (
                patch("assets.clip_ingest.default_source_dirs", return_value=[str(source)]),
                patch("assets.clip_ingest.BASE_VIDEO_DIR", str(library)),
                patch("assets.clip_ingest.CLIP_INDEX_FILE", str(tmp / "clip_index.json")),
                patch("assets.clip_ingest.subprocess.run", side_effect=_fake_run),
                redirect_stdout(buf),
            ):
                code = cmd_ingest_clips(Namespace(apply=True, move=False))
            index = json.loads((tmp / "clip_index.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertIn("1/1", buf.getvalue())
        self.assertEqual(len(index["clips"]), 1)


if __name__ == "__main__":
    unittest.main()
