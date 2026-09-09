"""#153 caption choreography timeline.

Fail-then-fix: karaoke beats vs SRT cues from real word timings, not proportional
estimates, and a sidecar the next burn actually reads.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Two sentences, eight words. Karaoke (max 4) splits the second sentence;
# SRT (max 5) does not. That difference is the point of the panel.
WORDS = [
    {"word": "Take", "start": 0.0, "end": 0.3},
    {"word": "Two", "start": 0.3, "end": 0.55},
    {"word": "filed.", "start": 0.55, "end": 1.0},
    {"word": "The", "start": 1.1, "end": 1.25},
    {"word": "earnings", "start": 1.25, "end": 1.7},
    {"word": "beat", "start": 1.7, "end": 2.0},
    {"word": "landed", "start": 2.0, "end": 2.4},
    {"word": "hard.", "start": 2.4, "end": 2.9},
]


class TestCaptionTimelineModel(unittest.TestCase):
    def test_karaoke_and_srt_lanes_differ_on_real_word_timings(self):
        from core.caption_timeline import timeline_from_words

        tl = timeline_from_words(WORDS)
        self.assertEqual(tl.source, "word_timing")
        self.assertEqual(len(tl.karaoke), 3)
        self.assertEqual(len(tl.srt), 2)
        self.assertEqual(tl.karaoke[0].text, "Take Two filed.")
        self.assertEqual(tl.karaoke[0].start, 0.0)
        self.assertEqual(tl.karaoke[0].end, 1.0)
        self.assertEqual(tl.srt[1].text, "The earnings beat landed hard.")
        self.assertEqual(tl.srt[1].start, 1.1)
        self.assertEqual(tl.srt[1].end, 2.9)
        self.assertEqual(tl.karaoke[1].text, "The earnings beat")
        self.assertNotEqual(len(tl.karaoke), len(tl.srt))

    def test_missing_words_do_not_invent_proportional_cues(self):
        from core.caption_timeline import timeline_from_words

        tl = timeline_from_words([])
        self.assertEqual(tl.source, "missing")
        self.assertEqual(tl.karaoke, [])
        self.assertEqual(tl.srt, [])
        self.assertIn("word timing", tl.reason.lower())

    def test_cue_rect_maps_time_to_x_and_keeps_lanes_apart(self):
        from core.caption_timeline import cue_rect, timeline_from_words

        tl = timeline_from_words(WORDS)
        x, y, w, h = cue_rect(tl.karaoke[0], px_per_sec=100)
        self.assertEqual((x, w), (0, 100))
        self.assertGreater(h, 0)
        _sx, srt_y, _sw, _sh = cue_rect(tl.srt[0], px_per_sec=100)
        self.assertGreater(srt_y, y)

    def test_clamp_cue_time_does_not_run_off_the_duration(self):
        from core.caption_timeline import clamp_cue_time

        start, end = clamp_cue_time(-1.0, 0.4, duration=10.0)
        self.assertEqual((start, end), (0.0, 1.4))
        start, end = clamp_cue_time(9.8, 11.0, duration=10.0)
        self.assertEqual(end, 10.0)
        self.assertGreater(end, start)


class TestCaptionEditsSidecar(unittest.TestCase):
    def test_timing_edit_shifts_only_that_cues_words(self):
        from core.caption_timeline import apply_caption_edits, timeline_from_words

        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "vo.mp3")
            Path(audio + ".captions.json").write_text(
                json.dumps(
                    {"edits": [{"lane": "karaoke", "index": 0, "dt": 0.25, "margin_v": 400}]}
                ),
                encoding="utf-8",
            )
            shifted, margins = apply_caption_edits(audio, WORDS, lane="karaoke")
        self.assertEqual(shifted[0]["start"], 0.25)
        self.assertEqual(shifted[0]["end"], 0.55)
        self.assertEqual(shifted[2]["end"], 1.25)
        self.assertEqual(shifted[3]["start"], 1.1)
        self.assertEqual(margins, [400, None, None])
        rebuilt = timeline_from_words(shifted)
        self.assertAlmostEqual(rebuilt.karaoke[0].start, 0.25)

    def test_no_sidecar_leaves_words_and_ass_byte_identical(self):
        from core.caption_timeline import apply_caption_edits
        from video.caption_timing import build_ass_karaoke

        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "vo.mp3")
            shifted, margins = apply_caption_edits(audio, WORDS, lane="karaoke")
        self.assertIs(shifted, WORDS)
        self.assertIsNone(margins)
        self.assertEqual(build_ass_karaoke(WORDS), build_ass_karaoke(shifted))

    def test_next_karaoke_burn_reads_the_sidecar(self):
        from video.subtitles import generate_subtitle_file

        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "vo.mp3")
            Path(audio).write_bytes(b"not-audio")
            Path(audio + ".words.json").write_text(json.dumps(WORDS), encoding="utf-8")
            Path(audio + ".captions.json").write_text(
                json.dumps(
                    {"edits": [{"lane": "karaoke", "index": 0, "dt": 0.5, "margin_v": 400}]}
                ),
                encoding="utf-8",
            )
            out = os.path.join(tmp, "captions.ass")
            with patch.dict("os.environ", {"CAPTION_STYLE": "karaoke"}, clear=False):
                path = generate_subtitle_file(
                    "Take Two filed. The earnings beat landed hard.",
                    5.0,
                    audio_path=audio,
                    output_path=out,
                )
            text = Path(path).read_text(encoding="utf-8")
        self.assertTrue(path.endswith(".ass"))
        self.assertIn("0:00:00.50", text)
        self.assertIn(",0,0,400,,", text)
        self.assertNotIn("0:00:00.00", text.split("[Events]", 1)[1])

    def test_known_gap_srt_margin_does_not_change_srt_text(self):
        """SRT has no per-cue vertical. Placement is the karaoke/ASS path.
        A similarity-style SRT override would close this."""
        from core.caption_timeline import apply_caption_edits
        from video.caption_timing import build_srt_from_words

        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "vo.mp3")
            Path(audio + ".captions.json").write_text(
                json.dumps({"edits": [{"lane": "srt", "index": 0, "dt": 0.0, "margin_v": 500}]}),
                encoding="utf-8",
            )
            shifted, margins = apply_caption_edits(audio, WORDS, lane="srt")
        self.assertIsNone(margins)
        self.assertEqual(build_srt_from_words(shifted), build_srt_from_words(WORDS))


class TestCaptionTimelineSurface(unittest.TestCase):
    def test_ops_and_desktop_flag_are_registered(self):
        from desktop.launch import desktop_mode
        from scripts.ops import COMMANDS

        self.assertIn("captions", COMMANDS)
        self.assertIn("caption-timeline", COMMANDS)
        self.assertEqual(desktop_mode(["--captions"]), "captions")

    def test_ops_captions_prints_real_cues_from_a_sidecar(self):
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "vo.mp3")
            Path(audio + ".words.json").write_text(json.dumps(WORDS), encoding="utf-8")
            fn = COMMANDS["captions"][1]
            args = type("A", (), {"path": audio, "channel": "tapin", "html": False})()
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = fn(args)
        self.assertEqual(code, 0)
        printed = buf.getvalue()
        self.assertIn("karaoke: 3", printed)
        self.assertIn("srt: 2", printed)
        self.assertIn("Take Two filed.", printed)

    def test_font_pick_is_not_this_panel(self):
        from core.caption_timeline import timeline_report

        report = "\n".join(timeline_report(WORDS, audio_path="x.mp3"))
        self.assertNotIn("Impact", report)
        self.assertNotIn("fill_color", report)


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None  # type: ignore[misc, assignment]


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestCaptionTimelineWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_window_draws_one_item_per_cue(self):
        from desktop.captions import CaptionTimelineWindow

        window = CaptionTimelineWindow(
            context={"words": WORDS, "channel_id": "tapin", "mp3_path": ""}
        )
        items = [item for item in window.scene.items() if item.data(0) == "cue"]
        self.assertEqual(len(items), 5)
        self.assertIn("karaoke", window.status.text().lower())
        window.close()

    def test_missing_timings_say_so_instead_of_drawing_fake_cues(self):
        from desktop.captions import CaptionTimelineWindow

        window = CaptionTimelineWindow(context={"words": [], "channel_id": "tapin", "mp3_path": ""})
        items = [item for item in window.scene.items() if item.data(0) == "cue"]
        self.assertEqual(items, [])
        self.assertIn("word timing", window.empty_label.text().lower())
        window.close()


if __name__ == "__main__":
    unittest.main()
