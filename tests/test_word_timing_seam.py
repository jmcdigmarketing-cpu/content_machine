"""Real word timings must reach hook motion and lower thirds, not just the captions.

`render_vertical_video` sourced its timings from `_load_word_timings`, which reads only
the ElevenLabs `.words.json` sidecar. The whisper -> `retext_words_from_script` path
lived *inside* `generate_subtitle_file` and its result was never returned.

So on a Piper / Free-mode / imported-audio run there is no sidecar, `word_timings` came
back `None`, and candidate 26 (hook motion) and candidate 24 (lower thirds) both
silently did nothing -- while the captions burned into the very same render *did* carry
real whisper timings. The operator note even misread the cause as "no real first-cue
timing" when the truth was that nothing had asked the aligner.

The $0 local path is where this project has been investing (Piper, caption retext,
decisions.md 23), so two of the five features in that wave were invisible exactly there.
"""

import unittest
from unittest.mock import patch

from video.subtitles import resolve_word_timings

ALIGNED = [
    {"word": "Take", "start": 0.0, "end": 0.30},
    {"word": "Two", "start": 0.30, "end": 0.60},
    {"word": "filed", "start": 0.60, "end": 0.95},
]
SIDECAR = [{"word": "Sidecar", "start": 0.0, "end": 0.5}]


class TestSidecarPathUnchanged(unittest.TestCase):
    def test_sidecar_wins_and_the_aligner_is_not_run(self):
        with patch("video.subtitles._load_word_timings", return_value=SIDECAR):
            with patch("video.caption_timing.words_from_caption_align") as align:
                words = resolve_word_timings("a.mp3", "Take Two filed.")
        self.assertEqual(words, SIDECAR)
        align.assert_not_called()


class TestLocalTtsPath(unittest.TestCase):
    """No sidecar, working aligner -- the case that produced nothing before."""

    def test_aligner_timings_are_returned(self):
        with patch("video.subtitles._load_word_timings", return_value=None):
            with patch("video.caption_timing.words_from_caption_align", return_value=ALIGNED):
                with patch(
                    "video.caption_retext.retext_words_from_script", return_value=ALIGNED
                ) as retext:
                    words = resolve_word_timings("piper.mp3", "Take Two filed.")
        self.assertEqual(words, ALIGNED)
        retext.assert_called_once()

    def test_a_transcript_that_does_not_match_yields_none(self):
        # retext returns None when the transcript is for different audio -- those
        # timings cannot be trusted, so motion and labels must stay off.
        with patch("video.subtitles._load_word_timings", return_value=None):
            with patch("video.caption_timing.words_from_caption_align", return_value=ALIGNED):
                with patch("video.caption_retext.retext_words_from_script", return_value=None):
                    self.assertIsNone(resolve_word_timings("piper.mp3", "unrelated script"))

    def test_no_aligner_result_yields_none(self):
        with patch("video.subtitles._load_word_timings", return_value=None):
            with patch("video.caption_timing.words_from_caption_align", return_value=None):
                self.assertIsNone(resolve_word_timings("piper.mp3", "script"))


class TestFailOpen(unittest.TestCase):
    def test_no_audio_path_is_none(self):
        self.assertIsNone(resolve_word_timings(None, "script"))

    def test_a_raising_aligner_does_not_propagate(self):
        with patch("video.subtitles._load_word_timings", return_value=None):
            with patch(
                "video.caption_timing.words_from_caption_align",
                side_effect=RuntimeError("no torch"),
            ):
                self.assertIsNone(resolve_word_timings("piper.mp3", "script"))

    def test_plain_caption_style_skips_alignment_entirely(self):
        with patch("video.subtitles.caption_style", return_value="plain"):
            with patch("video.caption_timing.words_from_caption_align") as align:
                self.assertIsNone(resolve_word_timings("a.mp3", "script"))
        align.assert_not_called()


class TestGenerateSubtitleFileReusesThem(unittest.TestCase):
    """The resolution must happen once, not once per consumer."""

    def test_supplied_words_are_not_re_resolved(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "v.srt")
            with patch("video.subtitles.resolve_word_timings") as resolver:
                from video.subtitles import generate_subtitle_file

                generate_subtitle_file(
                    "Take Two filed.", 2.0, audio_path="a.mp3", output_path=out, words=ALIGNED
                )
            resolver.assert_not_called()


class TestRenderPassesThemThrough(unittest.TestCase):
    """The seam is only worth having if the render actually uses it."""

    def test_render_video_resolves_once_and_shares_it(self):
        import inspect

        import video.render_video as rv

        source = inspect.getsource(rv.render_vertical_video)
        self.assertIn("resolve_word_timings", source)
        self.assertNotIn(
            "_load_word_timings",
            source,
            "render should use the public seam, not subtitles' private sidecar reader",
        )


if __name__ == "__main__":
    unittest.main()
