"""Connected FFmpeg/ffprobe tests for post-render technical QC."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

FFMPEG = shutil.which("ffmpeg")


@unittest.skipUnless(FFMPEG, "ffmpeg is required for technical-QC integration tests")
class TestTechnicalQCOnRealMedia(unittest.TestCase):
    def _make_video(self, dest: str, *, black: bool = False, size: str = "320x568") -> None:
        source = f"color=c=black:s={size}:r=30" if black else f"testsrc2=s={size}:r=30"
        proc = subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                source,
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=880:sample_rate=48000",
                "-t",
                "1.5",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                dest,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_real_av_file_reports_stream_and_loudness_measurements(self):
        from core.technical_qc import inspect_technical_qc

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "healthy.mp4")
            self._make_video(path)
            result = inspect_technical_qc(path, expected_size=(320, 568))

        self.assertEqual(result.status, "evaluated")
        self.assertTrue(result.has_video)
        self.assertTrue(result.has_audio)
        self.assertEqual((result.width, result.height), (320, 568))
        self.assertIsNotNone(result.integrated_lufs)
        self.assertIsNotNone(result.true_peak_dbfs)
        self.assertIsNotNone(result.loudness_range_lu)

    def test_real_black_video_is_not_reported_clean(self):
        from core.technical_qc import inspect_technical_qc

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "black.mp4")
            self._make_video(path, black=True)
            result = inspect_technical_qc(path, expected_size=(320, 568))

        self.assertFalse(result.passed)
        self.assertTrue(any("black" in issue.lower() for issue in result.issues))


class TestTechnicalQCToolFailure(unittest.TestCase):
    def test_missing_probe_is_unavailable_not_a_pass(self):
        from core.technical_qc import inspect_technical_qc

        with patch("core.technical_qc.shutil.which", return_value=None):
            result = inspect_technical_qc("render.mp4")

        self.assertEqual(result.status, "unavailable")
        self.assertFalse(result.passed)
        self.assertIn("ffmpeg", " ".join(result.issues).lower())


@unittest.skipUnless(FFMPEG, "ffmpeg is required for technical-QC integration tests")
class TestTechnicalQCPipelineWiring(unittest.TestCase):
    def test_render_choke_point_persists_the_real_qc_result(self):
        from core import pipeline

        with tempfile.TemporaryDirectory() as tmp:
            mp3 = str(Path(tmp) / "voice.mp3")
            mp4 = str(Path(tmp) / "render.mp4")
            TestTechnicalQCOnRealMedia()._make_video(mp4, size="1080x1920")
            with (
                patch.dict(
                    os.environ,
                    {
                        "THUMBNAIL_MODE": "off",
                        "CONTENT_RENDER_PROGRESS": "0",
                        "LUFS_RANGE_MIN": "0",
                    },
                    clear=False,
                ),
                patch.object(
                    pipeline,
                    "media_paths_for_topic",
                    return_value=(mp3, os.path.basename(mp4), mp4),
                ),
                patch.object(pipeline, "generate_audio"),
                patch.object(
                    pipeline,
                    "render_vertical_video",
                    return_value=(os.path.basename(mp4), "owned"),
                ),
                patch.object(pipeline, "update_content_run_media"),
                patch.object(pipeline, "record_render_assets"),
                patch("core.first_frame.inspect_video", return_value=None),
                patch("scripts.probe_sync.grab_frame", return_value=False),
                patch("core.run_features.load_features", return_value={"cost": {}}),
                patch("core.run_features.merge_features") as merge,
                patch("core.run_trace.update_trace") as trace,
            ):
                pipeline.run_media_only(
                    "topic",
                    "A short script.",
                    channel_id="tapin",
                    content_run_id=414,
                )

        self.assertTrue(merge.call_args[0][1]["technical_qc"]["has_audio"])
        self.assertTrue(trace.call_args[0][1]["technical_qc"]["has_video"])


class TestTechnicalQCReader(unittest.TestCase):
    def test_run_dossier_surfaces_the_persisted_advisory(self):
        from core.run_ledger import render_dossier

        record = MagicMock(
            id=414,
            channel_id="tapin",
            status="rendered",
            selected_topic="topic",
            input_topic="topic",
            title="title",
            composite_score=50.0,
            abort_reason="",
            quality_json="{}",
            timings_json="{}",
            features_json=json.dumps(
                {
                    "technical_qc": {
                        "status": "evaluated",
                        "passed": False,
                        "issues": ["missing audio stream"],
                        "integrated_lufs": None,
                        "true_peak_dbfs": None,
                        "loudness_range_lu": None,
                    }
                }
            ),
        )
        repo = MagicMock()
        repo.get.return_value = record
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch("core.run_ledger._publish_for_run", return_value={}),
            patch("core.run_trace.read_trace", return_value=None),
            patch("core.experiments.assignment_for_run", return_value=None),
        ):
            text = render_dossier(414)

        self.assertIn("Technical QC", text)
        self.assertIn("missing audio stream", text)


@unittest.skipUnless(FFMPEG, "ffmpeg is required for technical-QC integration tests")
class TestTechnicalQCOps(unittest.TestCase):
    def test_ops_command_runs_the_real_check_on_the_committed_fixture(self):
        from scripts import ops

        output = io.StringIO()
        with redirect_stdout(output):
            code = ops.cmd_technical_qc(SimpleNamespace(path=str(FIXTURE_PATH)))

        self.assertEqual(code, 1)
        self.assertIn("missing audio stream", output.getvalue())


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "video" / "intro" / "channel_intro.mp4"


if __name__ == "__main__":
    unittest.main()
