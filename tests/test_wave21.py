"""Wave 21: get Shorts published.

Operator calls 2026-09-17: enable the base Whisper aligner (#771), aim the wave at getting
Shorts out (0 uploads in 10 days), install the nightly drafts task, run 77 "deleted in
Studio". The first real overnight run then saved 0 of 3 drafts. Each test here failed on
unmodified 914687d unless its docstring says it guards existing behaviour.
"""

from __future__ import annotations

import unittest
import unittest.mock
from types import SimpleNamespace
from unittest.mock import patch


def _pipeline_result(**overrides):
    """What `run_pipeline(proceed_video=False)` really returns for a finished draft."""
    base = {
        "aborted": True,
        "abort_reason": "proceed_video=False",
        "script": "Rockstar is selling the skip button. " * 20,
        "title": "GTA 6 Online sells the skip button",
        "description": "desc",
        "tags": ["gta6"],
        "run_id": 91,
        "features": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestADraftIsNotAFailure(unittest.TestCase):
    """#779, overnight 2026-09-17: "FAIL GTA week 2 - proceed_video=False", 0/3 saved.

    The pipeline marks every script-only run aborted with that reason (and records it as
    "drafted"); batch_generation treated any abort as a failure, so the nightly task would
    have paid for three scripts a night and kept none. Its own tests mocked a result that
    was never aborted."""

    def _draft(self, result):
        import tempfile

        from core import batch_generation

        discovery = SimpleNamespace(
            evaluated=[("GTA 6 angle", 70.0, {})], raw_scores=[], angle_scores=[]
        )
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("core.pipeline.run_discovery", return_value=discovery),
                patch("core.pipeline.best_variant_index", return_value=0),
                patch("core.pipeline.run_pipeline", return_value=result),
                patch("core.experiments.next_arm", return_value=None),
                patch("core.vault_relevance.build_relevance_corpus", return_value=None),
                patch("core.fact_enrichment.enrich_facts", return_value=""),
                patch.object(batch_generation, "_drafts_dir", return_value=tmp),
                patch.object(batch_generation, "_length_choice", return_value="2"),
            ):
                return batch_generation.generate_draft("GTA 6", "tapin")

    def test_a_script_only_run_is_saved(self):
        outcome = self._draft(_pipeline_result())
        self.assertTrue(outcome.ok, outcome.error)
        self.assertEqual(outcome.run_id, 91)
        self.assertTrue(outcome.path)

    def test_a_real_abort_is_still_a_failure(self):
        """Guard: a run that stopped for a reason is not a draft."""
        outcome = self._draft(_pipeline_result(abort_reason="thin facts", script=""))
        self.assertFalse(outcome.ok)
        self.assertIn("thin facts", outcome.error)


class TestPiperShortsGetRealWordTimings(unittest.TestCase):
    """#771: 1 in 6 Shorts are piper (#775) and shipped proportional caption timing because
    the aligner that already existed defaulted to `none`. Operator 2026-09-17: switch it on,
    model tiny (the code's measured default)."""

    def test_the_backend_defaults_on(self):
        import os

        from core.caption_align import align_backend

        env = {k: v for k, v in os.environ.items() if k != "CAPTION_ALIGN_BACKEND"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(align_backend(), "faster_whisper")
        with patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": "none"}):
            self.assertEqual(align_backend(), "none")

    def test_the_suite_keeps_it_off(self):
        """Guard: no test loads a Whisper model."""
        import os

        self.assertEqual(os.environ.get("CAPTION_ALIGN_BACKEND"), "none")

    def test_aligned_words_are_written_to_the_sidecar(self):
        import json
        import os
        import tempfile

        from video import subtitles

        words = [{"word": "Rockstar", "start": 0.0, "end": 0.4}]
        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "a.mp3")
            open(audio, "wb").close()
            with (
                patch.object(subtitles, "caption_style", return_value="karaoke"),
                patch("video.caption_timing.words_from_caption_align", return_value=words),
                patch("video.caption_retext.retext_words_from_script", return_value=words),
            ):
                got = subtitles.resolve_word_timings(audio, "Rockstar.", channel_id="tapin")
            self.assertEqual(got, words)
            with open(audio + ".words.json", encoding="utf-8") as f:
                self.assertEqual(json.load(f), words)

    def test_no_sidecar_is_written_for_audio_that_does_not_exist(self):
        """The first #771 commit left `piper.mp3.words.json` in the repo root: a suite test
        passes a bare "piper.mp3" with the aligner mocked, and the writer followed it."""
        import os
        import tempfile

        from video import subtitles

        words = [{"word": "Take", "start": 0.0, "end": 0.3}]
        with tempfile.TemporaryDirectory() as tmp:
            ghost = os.path.join(tmp, "piper.mp3")
            subtitles._write_aligned_sidecar(ghost, words)
            self.assertFalse(os.path.exists(ghost + ".words.json"))

    def test_an_existing_sidecar_is_never_overwritten(self):
        import json
        import os
        import tempfile

        from video import subtitles

        real = [{"word": "Real", "start": 0.0, "end": 0.3}]
        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "a.mp3")
            open(audio, "wb").close()
            with open(audio + ".words.json", "w", encoding="utf-8") as f:
                json.dump(real, f)
            with (
                patch.object(subtitles, "caption_style", return_value="karaoke"),
                patch("video.caption_timing.words_from_caption_align") as align,
            ):
                self.assertEqual(subtitles.resolve_word_timings(audio, "Real."), real)
            align.assert_not_called()


class TestStudioDeletedSaysWhatItChecked(unittest.TestCase):
    """#780, 2026-09-17: the operator deleted run 77 in Studio, `ops studio-deleted` said
    "none", and "none" could mean "12 checked, all live" or "never reached YouTube".
    YouTube still had the video (acu0Ekz-G5k, unlisted); the report has to say that."""

    def _rows(self):
        return [
            SimpleNamespace(id=1316, youtube_video_id="acu0Ekz-G5k", status="uploaded", detail=""),
            SimpleNamespace(id=869, youtube_video_id="n74FopOIvNk", status="uploaded", detail=""),
        ]

    def test_a_live_video_is_reported_as_still_there(self):
        from youtube.studio_deleted import detect_studio_deleted

        items = {"items": [{"id": "acu0Ekz-G5k"}, {"id": "n74FopOIvNk"}]}
        service = unittest.mock.MagicMock()
        service.videos.return_value.list.return_value.execute.return_value = items
        repo = SimpleNamespace(list_uploaded_for_channel=lambda ch: self._rows(), update=None)
        report: dict = {}
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            cancelled = detect_studio_deleted("tapin", service=service, report=report)
        self.assertEqual(cancelled, [])
        self.assertEqual(report["checked"], 2)
        self.assertIn("acu0Ekz-G5k", report["still_live"])
        self.assertEqual(report.get("error", ""), "")

    def test_an_unreachable_api_is_reported_not_hidden(self):
        from youtube.studio_deleted import detect_studio_deleted

        service = unittest.mock.MagicMock()
        service.videos.return_value.list.return_value.execute.side_effect = TimeoutError("read")
        repo = SimpleNamespace(list_uploaded_for_channel=lambda ch: self._rows(), update=None)
        report: dict = {}
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            detect_studio_deleted("tapin", service=service, report=report)
        self.assertIn("read", report["error"])

    def test_ops_prints_the_report(self):
        from pathlib import Path

        ops = Path(__file__).resolve().parents[1].joinpath("scripts", "ops.py").read_text("utf-8")
        self.assertIn("report=report", ops)


if __name__ == "__main__":
    unittest.main()
