"""Local whisper caption alignment — backend selection and fail-open behaviour.

This seam supplies word timings for audio with no ElevenLabs `.words.json` sidecar
(local TTS, imported audio). It is OFF by default and must *never* break a render: any
missing backend, missing model or backend error falls back to the proportional caption
path in `video/subtitles.py`.

No models and no network: the backends are mocked (tests/CLAUDE.md). Accuracy is not
asserted here — it is measured against real ElevenLabs ground truth by
`scripts/bench_caption_align.py`, which is a dev script for exactly that reason.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from core import caption_align
from core.providers import STATUS_ERROR, STATUS_NOT_CONFIGURED


class TestConfig(unittest.TestCase):
    def test_model_defaults_to_tiny(self):
        # Chosen from measurement: tiny beat base on line-start error AND speed on
        # clean TTS audio (see the module docstring).
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(caption_align.align_model(), "tiny")

    def test_model_is_env_tunable(self):
        with patch.dict(os.environ, {"CAPTION_ALIGN_MODEL": "small"}, clear=False):
            self.assertEqual(caption_align.align_model(), "small")

    def test_device_falls_back_to_cpu_without_cuda(self):
        with (
            patch.dict(os.environ, {"CAPTION_ALIGN_DEVICE": "auto"}, clear=False),
            patch("torch.cuda.is_available", return_value=False),
        ):
            self.assertEqual(caption_align.align_device(), "cpu")

    def test_device_picks_cuda_when_available(self):
        with (
            patch.dict(os.environ, {"CAPTION_ALIGN_DEVICE": "auto"}, clear=False),
            patch("torch.cuda.is_available", return_value=True),
        ):
            self.assertEqual(caption_align.align_device(), "cuda")

    def test_explicit_device_wins(self):
        with patch.dict(os.environ, {"CAPTION_ALIGN_DEVICE": "cpu"}, clear=False):
            self.assertEqual(caption_align.align_device(), "cpu")

    def test_device_detection_never_raises(self):
        with (
            patch.dict(os.environ, {"CAPTION_ALIGN_DEVICE": "auto"}, clear=False),
            patch("torch.cuda.is_available", side_effect=RuntimeError("no driver")),
        ):
            self.assertEqual(caption_align.align_device(), "cpu")

    def test_compute_type_matches_device(self):
        with patch.dict(os.environ, {"CAPTION_ALIGN_COMPUTE": ""}, clear=False):
            self.assertEqual(caption_align.align_compute_type("cpu"), "int8")
            self.assertEqual(caption_align.align_compute_type("cuda"), "float16")

    def test_explicit_compute_type_wins(self):
        with patch.dict(os.environ, {"CAPTION_ALIGN_COMPUTE": "float32"}, clear=False):
            self.assertEqual(caption_align.align_compute_type("cpu"), "float32")


class TestFailOpen(unittest.TestCase):
    """Every failure mode must fail open — a render must never break on captions."""

    def test_unset_backend(self):
        with patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": ""}, clear=False):
            result = caption_align.transcribe_and_align("a.mp3")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, STATUS_NOT_CONFIGURED)

    def test_unknown_backend_is_named_in_the_detail(self):
        with patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": "wav2vec"}, clear=False):
            result = caption_align.transcribe_and_align("a.mp3")
        self.assertFalse(result.ok)
        self.assertIn("wav2vec", result.detail)
        self.assertIn("faster_whisper", result.detail)  # says what IS accepted

    def test_missing_audio_file(self):
        with patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": "faster_whisper"}, clear=False):
            result = caption_align.transcribe_and_align("does_not_exist.mp3")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, STATUS_NOT_CONFIGURED)

    def test_backend_not_installed(self):
        with (
            patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": "faster_whisper"}, clear=False),
            patch.object(caption_align.os.path, "exists", return_value=True),
            patch.object(
                caption_align, "_words_from_faster_whisper", side_effect=ImportError("no ct2")
            ),
        ):
            result = caption_align.transcribe_and_align("a.mp3")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, STATUS_NOT_CONFIGURED)

    def test_backend_error_is_swallowed(self):
        with (
            patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": "faster_whisper"}, clear=False),
            patch.object(caption_align.os.path, "exists", return_value=True),
            patch.object(
                caption_align, "_words_from_faster_whisper", side_effect=RuntimeError("boom")
            ),
        ):
            result = caption_align.transcribe_and_align("a.mp3")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, STATUS_ERROR)

    def test_empty_transcription_is_a_failure_not_a_success(self):
        # Silent audio returning [] must not be reported as usable timings.
        with (
            patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": "faster_whisper"}, clear=False),
            patch.object(caption_align.os.path, "exists", return_value=True),
            patch.object(caption_align, "_words_from_faster_whisper", return_value=[]),
        ):
            result = caption_align.transcribe_and_align("a.mp3")
        self.assertFalse(result.ok)


class TestFasterWhisperExtraction(unittest.TestCase):
    def _model(self, words):
        word_objs = [MagicMock(word=w, start=s, end=e) for w, s, e in words]
        segment = MagicMock(words=word_objs)
        model = MagicMock()
        model.transcribe.return_value = (iter([segment]), MagicMock())
        return model

    def test_extracts_word_timings(self):
        model = self._model([(" Salkilld", 0.0, 0.44), (" jumps", 0.44, 0.72)])
        with patch.dict(
            "sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **k: model)}
        ):
            words = caption_align._words_from_faster_whisper("a.mp3", "cpu")
        self.assertEqual([w["word"] for w in words], ["Salkilld", "jumps"])
        self.assertEqual(words[0]["start"], 0.0)
        self.assertEqual(words[1]["end"], 0.72)

    def test_blank_words_are_dropped(self):
        model = self._model([("  ", 0.0, 0.1), (" real", 0.1, 0.3)])
        with patch.dict(
            "sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **k: model)}
        ):
            words = caption_align._words_from_faster_whisper("a.mp3", "cpu")
        self.assertEqual([w["word"] for w in words], ["real"])

    def test_word_timestamps_are_requested(self):
        # Without word_timestamps=True there are no per-word times at all.
        model = self._model([(" a", 0.0, 0.1)])
        with patch.dict(
            "sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **k: model)}
        ):
            caption_align._words_from_faster_whisper("a.mp3", "cpu")
        self.assertTrue(model.transcribe.call_args.kwargs.get("word_timestamps"))


class TestCaptionTimingIntegration(unittest.TestCase):
    """The converter downstream must accept what this backend produces."""

    def test_words_convert_to_the_caption_shape(self):
        from video.caption_timing import words_from_caption_align

        payload = [{"word": "hello", "start": 0.0, "end": 0.4}]
        with (
            patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": "faster_whisper"}, clear=False),
            patch(
                "core.caption_align.transcribe_and_align",
                return_value=MagicMock(ok=True, data=payload),
            ),
        ):
            words = words_from_caption_align("a.mp3")
        self.assertEqual(words, [{"word": "hello", "start": 0.0, "end": 0.4}])

    def test_fail_open_yields_none_for_the_proportional_path(self):
        from video.caption_timing import words_from_caption_align

        with patch.dict(os.environ, {"CAPTION_ALIGN_BACKEND": ""}, clear=False):
            self.assertIsNone(words_from_caption_align("a.mp3"))


if __name__ == "__main__":
    unittest.main()
