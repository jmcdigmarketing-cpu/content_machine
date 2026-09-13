"""Wave 10: #720, #724, #725, #726, #158 (panel).

Every test here was observed failing on unmodified 08700c1 for the reason named in
its docstring, except #720's, which guards a fix that already shipped -- that one was
broken in memory instead, and says so.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


class TestWikipediaTripwireIsLogged(unittest.TestCase):
    """#720. The revision tripwire swallowed failures with no logger in the module
    to report them. Fixed 2026-09-09 with a debug line, but nothing guarded it."""

    def test_a_failed_revision_fetch_is_logged_and_the_signal_survives(self):
        import apis.wikipedia_pageviews_api as wiki

        with (
            patch.object(wiki, "_WIKI_ENABLED", True),
            patch.object(wiki, "get_cached", return_value=None),
            patch.object(wiki, "set_cache"),
            patch.object(wiki, "_article_candidates", return_value=["UFC_320"]),
            patch.object(wiki, "_fetch_pageviews", return_value={"views": [100] * 10}),
            patch.object(wiki, "_fetch_last_revision", side_effect=RuntimeError("boom")),
            self.assertLogs("content_machine.apis.wikipedia_pageviews", level="DEBUG") as logs,
        ):
            signal = wiki.get_wikipedia_pageviews_signal("UFC 320")
        self.assertTrue(any("revision tripwire skipped" in line for line in logs.output))
        self.assertIsInstance(signal, dict)
        self.assertIn("status", signal)


class _CorruptLedger(unittest.TestCase):
    def setUp(self):
        from core import quota_state

        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "q.json")
        self._patch = patch.object(quota_state, "QUOTA_STATE_FILE", self.path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def corrupt(self):
        Path(self.path).write_text("{not json", encoding="utf-8")


class TestUnreadableElevenLabsLedgerIsUnknown(_CorruptLedger):
    """#724. `quota_state._load` swallows a read failure and returns an empty store,
    so a corrupt ledger read as "0 chars used" -- the #590 rule (unknown, never zero)
    broken below every renderer that shows the TTS lane."""

    def test_a_missing_ledger_is_a_real_zero(self):
        from core import quota_governor as qg
        from core import quota_state

        self.assertEqual(qg.elevenlabs_chars_reading(), 0)
        self.assertTrue(quota_state.read_ok())

    def test_a_corrupt_ledger_is_unknown(self):
        from core import quota_governor as qg
        from core import quota_state

        self.corrupt()
        self.assertIsNone(qg.elevenlabs_chars_reading())
        self.assertFalse(quota_state.read_ok())
        self.assertIsNone(qg.snapshot()["elevenlabs"]["chars_used"])

    def test_the_budget_guard_stays_fail_open(self):
        """The render must never be blocked because the ledger is unreadable."""
        from core import quota_governor as qg

        self.corrupt()
        self.assertEqual(qg.elevenlabs_chars_used(), 0)
        self.assertFalse(qg.elevenlabs_would_exceed(10, 100))

    def test_reliability_says_unknown_not_zero(self):
        from core import reliability

        self.corrupt()
        with patch.dict(os.environ, {"ELEVENLABS_MONTHLY_CHAR_BUDGET": "1000"}):
            section = reliability._elevenlabs_section()
            self.assertIsNone(section["chars_used"])
            lines = reliability._utilization_lines({"elevenlabs": section})
            text = reliability.render({"elevenlabs": section})
        self.assertFalse(any("1,000 chars unused" in line for line in lines), lines)
        self.assertIn("unknown", text.lower())
        self.assertNotIn("0/1,000", text)

    def test_the_tts_budget_display_says_unknown(self):
        from core import tts

        self.corrupt()
        with patch.dict(os.environ, {"ELEVENLABS_MONTHLY_CHAR_BUDGET": "1000"}):
            self.assertEqual(tts._elevenlabs_budget_display(), "unknown/1,000 chars")

    def test_the_tray_chip_says_unknown(self):
        """`core/win_notify.quota_chip_lines` printed the whole budget as leftover."""
        from core import win_notify

        snap = {"elevenlabs": {"chars_used": None}, "youtube": {}, "apify": {}}
        with (
            patch.dict(os.environ, {"ELEVENLABS_MONTHLY_CHAR_BUDGET": "1000"}),
            patch.object(win_notify, "last_grade_letter", return_value=""),
            patch.object(win_notify, "last_domain_label", return_value=""),
        ):
            lines = win_notify.quota_chip_lines(snap, channel_id="tapin")
        eleven = [line for line in lines if line.startswith("ElevenLabs")]
        self.assertEqual(len(eleven), 1, lines)
        self.assertIn("unknown", eleven[0])
        self.assertNotIn("1,000 chars leftover", eleven[0])

    def test_the_cost_tower_lane_is_unknown(self):
        from core import cost_tower

        self.corrupt()
        (row,) = cost_tower._tts_rows()
        self.assertEqual(row.state, "unknown")
        self.assertIsNone(row.used)


class TestClockAhead(unittest.TestCase):
    """#725. A test pinned 2026-09-09 while the code read the real clock went red
    three days later. A one-off harness measured the rest (0 of 3,022 change result a
    year ahead); this makes it a command, and fixes the harness's own bug: its
    `date.today()` shifted twice because it called the patched `time.time`."""

    def test_a_clock_bomb_passes_now_and_fails_ahead(self):
        import datetime as dt

        from core.clock_ahead import shifted_clock

        pinned = dt.date.today() + dt.timedelta(days=30)

        class _Bomb(unittest.TestCase):
            def test_before_pinned(self):
                self.assertLess(dt.date.today(), pinned)

        def run() -> bool:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(_Bomb)
            return unittest.TextTestRunner(stream=io.StringIO()).run(suite).wasSuccessful()

        self.assertTrue(run())
        with shifted_clock(365):
            self.assertFalse(run(), "the shifted clock did not reach the test")
        self.assertTrue(run(), "the clock was not restored")

    def test_every_clock_shifts_by_the_same_days(self):
        import datetime as dt
        import time

        from core.clock_ahead import shifted_clock

        real_today, real_now, real_time = dt.date.today(), dt.datetime.now(), time.time()
        with shifted_clock(10):
            self.assertEqual((dt.date.today() - real_today).days, 10)
            self.assertAlmostEqual(
                (dt.datetime.now() - real_now).total_seconds(), 10 * 86400, delta=120
            )
            self.assertAlmostEqual(time.time() - real_time, 10 * 86400, delta=120)

    def test_originals_are_restored(self):
        import datetime as dt
        import time

        from core.clock_ahead import shifted_clock

        before = (dt.datetime, dt.date, time.time)
        with shifted_clock(5):
            pass
        self.assertEqual((dt.datetime, dt.date, time.time), before)

    def test_changed_tests_reports_both_directions(self):
        from core.clock_ahead import changed_tests

        self.assertEqual(
            changed_tests(base_bad={"a", "b"}, ahead_bad={"b", "c"}),
            ["a", "c"],
        )

    def test_the_ops_verb_exits_nonzero_only_when_a_result_changed(self):
        from argparse import Namespace

        from scripts import ops

        self.assertIn("clock-ahead", ops.COMMANDS)
        with patch("core.clock_ahead.compare", return_value=[]), redirect_stdout(io.StringIO()):
            self.assertEqual(ops.cmd_clock_ahead(Namespace(days=365)), 0)
        with (
            patch("core.clock_ahead.compare", return_value=["tests.test_x.T.test_y"]),
            redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(ops.cmd_clock_ahead(Namespace(days=365)), 1)
        self.assertIn("tests.test_x.T.test_y", out.getvalue())


def _wide_frame(*, box: tuple[int, int, int, int] | list | None = None):
    """640x360 (16:9) noise frame; noise differs per call so two frames 'move'.
    `box` is (x0, y0, x1, y1) or a list of them, painted white identically."""
    from PIL import Image, ImageDraw

    img = Image.frombytes("RGB", (640, 360), os.urandom(640 * 360 * 3))
    boxes = box if isinstance(box, list) else [box] if box else []
    draw = ImageDraw.Draw(img)
    for b in boxes:
        draw.rectangle(b, fill=(250, 250, 250))
    return img


# The render keeps the centre 9:16 of a 640x360 frame: x 219..421.
_SIDES_ONLY = [(0, 320, 210, 350), (430, 320, 639, 350)]
_CENTRE = (225, 320, 415, 350)


class TestCaptionPlacementMeasuresTheCroppedFrame(unittest.TestCase):
    """#726. The render cover-scales and centre-crops every background to 1080x1920
    (`video/render_video.py:229-230`), so a 16:9 clip keeps only its middle third. But
    `caption_place` measured the whole source frame: an overlay in the margins the crop
    removes could move captions for something the viewer never sees."""

    def test_render_crop_matches_the_render_geometry(self):
        from video.caption_place import render_crop

        out = render_crop(_wide_frame())
        width, height = out.size
        self.assertAlmostEqual(width / height, 9 / 16, delta=0.01)
        self.assertLessEqual(height, 960)

    def test_an_overlay_only_in_the_cropped_margins_is_not_seen(self):
        from video.caption_place import frames_show_static_overlay, render_crop

        a, b = _wide_frame(box=_SIDES_ONLY), _wide_frame(box=_SIDES_ONLY)
        self.assertFalse(frames_show_static_overlay(render_crop(a), render_crop(b)))

    def test_an_overlay_inside_the_crop_still_is(self):
        from video.caption_place import frames_show_static_overlay, render_crop

        a, b = _wide_frame(box=_CENTRE), _wide_frame(box=_CENTRE)
        self.assertTrue(frames_show_static_overlay(render_crop(a), render_crop(b)))


def _has_ffmpeg() -> bool:
    import shutil

    return bool(shutil.which("ffmpeg")) or os.getenv("CI", "").lower() in ("1", "true", "yes")


@unittest.skipUnless(_has_ffmpeg(), "ffmpeg not installed (required under CI)")
class TestCroppedPlacementOnAnEncodedWideClip(unittest.TestCase):
    """#726 end to end through `_load_frame_at`, on a real h264 16:9 clip."""

    @staticmethod
    def _clip(dest: Path, box) -> str:
        import subprocess

        for i in range(3):
            _wide_frame(box=box).save(dest.parent / f"w{i + 1}.png")
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-framerate", "1",
                "-i", str(dest.parent / "w%d.png"),
                "-vf", "fps=25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                str(dest),
            ],
            check=True, capture_output=True, timeout=60,
        )  # fmt: skip
        return str(dest)

    def test_a_margin_only_overlay_keeps_captions_at_the_bottom(self):
        from video.caption_place import choose_caption_anchor, overlay_reading

        with tempfile.TemporaryDirectory() as tmp:
            clip = self._clip(Path(tmp) / "sides.mp4", _SIDES_ONLY)
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                self.assertEqual(choose_caption_anchor(clip), "bottom", overlay_reading(clip))

    def test_a_centred_overlay_still_moves_captions(self):
        from video.caption_place import choose_caption_anchor, overlay_reading

        with tempfile.TemporaryDirectory() as tmp:
            clip = self._clip(Path(tmp) / "centre.mp4", _CENTRE)
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                self.assertEqual(choose_caption_anchor(clip), "top", overlay_reading(clip))


try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - app extra not installed
    QApplication = None  # type: ignore[misc, assignment]


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestCostPanel(unittest.TestCase):
    """#158 remainder. `gather_tower()` shipped in wave 9 with an ops verb; the
    Windows application had no panel over it."""

    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    @staticmethod
    def _rows():
        from core.cost_tower import TowerRow

        return [
            TowerRow("YouTube", "daily units", None, 10000.0, "unknown", "2026-09-13 07:00 UTC"),
            TowerRow("LLM", "spend today", 2.0, 1.0, "over", None, "budget blown"),
        ]

    def test_rows_render_and_unknown_is_not_zero(self):
        from desktop.cost import CostWindow

        window = CostWindow(rows=self._rows())
        table = window.table
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, 2).text(), "? / 10,000")
        self.assertEqual(table.item(0, 3).text(), "UNKNOWN")
        self.assertEqual(table.item(1, 3).text(), "OVER")
        self.assertIn("budget blown", table.item(1, 1).toolTip())
        window.close()

    def test_refresh_reads_the_tower_again(self):
        from core.cost_tower import TowerRow
        from desktop.cost import CostWindow

        with patch("core.cost_tower.gather_tower", return_value=self._rows()) as gather:
            window = CostWindow()
            self.assertEqual(window.table.rowCount(), 2)
            gather.return_value = [TowerRow("LLM", "spend today", 0.0, None, "ok")]
            window.refresh_button.click()
            self.assertEqual(window.table.rowCount(), 1)
            self.assertEqual(window.table.item(0, 2).text(), "0.00 / ?")
        self.assertEqual(gather.call_count, 2)
        window.close()

    def test_the_panel_is_reachable(self):
        from desktop.launch import desktop_mode
        from scripts.ops import COMMANDS

        self.assertIn("cost-panel", COMMANDS)
        self.assertEqual(desktop_mode(["--cost"]), "cost")


if __name__ == "__main__":
    unittest.main()
