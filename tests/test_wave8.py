"""Wave 8: #590, #378, #407, #717, #684.

Every test here was observed failing on unmodified b99ab81 for the reason named
in its docstring.
"""

from __future__ import annotations

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


class TestDiscoveryHeadroomBeforeThePool(unittest.TestCase):
    """#590. Remaining rate-limit headroom was only visible *after* something hit
    a wall: `has_quota_for_search()` refused the call, or the Apify breaker
    tripped, or `ops reliability` was run by hand afterwards. The operator could
    not see 'you have 1 upload and 300 units left' before a discovery pool of
    eight signals started spending them.
    """

    def test_headroom_line_names_the_actual_remaining_numbers(self):
        from core.discovery_headroom import headroom_line

        summary = {"units_used": 9200, "units_limit": 10000, "date": "2026-09-10"}
        with patch("apis.youtube_quota.get_usage_summary", return_value=summary):
            with patch("apis.youtube_quota.uploads_remaining", return_value=0):
                line = headroom_line(signal_count=8)

        self.assertIn("8", line, "the line must say how many signals are about to run")
        self.assertIn("800", line, "remaining YouTube units are not shown")
        self.assertIn("0 upload", line)

    def test_it_warns_when_a_pool_cannot_finish_on_the_remaining_units(self):
        """The point of showing it early: 8 signals against 60 units left is a
        decision the operator can still make."""
        from core.discovery_headroom import headroom_line

        summary = {"units_used": 9940, "units_limit": 10000, "date": "2026-09-10"}
        with patch("apis.youtube_quota.get_usage_summary", return_value=summary):
            with patch("apis.youtube_quota.uploads_remaining", return_value=0):
                line = headroom_line(signal_count=8)
        self.assertIn("!", line, "a pool that cannot finish must be flagged, not just printed")

    def test_an_unreadable_quota_store_says_unknown_not_zero(self):
        """Absence of a reading is not a reading of zero -- that would look like
        'you are out of quota' on a fresh machine."""
        from core.discovery_headroom import headroom_line

        with patch("apis.youtube_quota.get_usage_summary", side_effect=OSError("no store")):
            line = headroom_line(signal_count=3)
        self.assertIn("unknown", line.lower())
        self.assertNotIn("0 units", line)

    def test_build_registry_emits_the_line_before_the_pool_starts(self):
        """Trace the call, not the helper: a headroom line nobody prints is #590
        unfixed."""
        import apis.register_signals as rs

        seen: list[str] = []
        order: list[str] = []

        def fake_line(**kwargs):
            order.append("headroom")
            return "headroom: fake"

        class _Pool:
            def __init__(self, *a, **k):
                order.append("pool")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def submit(self, *a, **k):
                raise AssertionError("no signal should be submitted in this test")

        with (
            patch.object(rs, "_active_signal_sources", return_value=()),
            patch.object(rs, "start_youtube_warmup_background", lambda: None),
            patch("core.discovery_headroom.headroom_line", side_effect=fake_line),
            patch("core.discovery_headroom.emit_headroom", side_effect=seen.append),
            patch.object(rs, "ThreadPoolExecutor", _Pool),
        ):
            rs.build_registry("UFC 320", channel_id="tapin")

        self.assertEqual(order[:1], ["headroom"], f"pool started before the line: {order}")
        self.assertTrue(seen, "the headroom line was computed but never emitted")


class TestFreeTierExpiryCalendar(unittest.TestCase):
    """#378. A $0 run becomes a paid one the moment a provider's free window
    resets or ends, and nothing tracked when that happens -- the same class as
    #580, where a persisted $0 last-run was re-estimated at $0.1725.
    """

    def test_a_window_closing_inside_the_notice_period_is_surfaced(self):
        from core.free_tier_calendar import expiring_windows

        rows = expiring_windows(
            today="2026-09-10",
            windows=[
                {"provider": "apify", "kind": "monthly_credit", "resets": "2026-09-12"},
                {"provider": "deepseek", "kind": "promo", "ends": "2026-12-01"},
            ],
            notice_days=7,
        )
        names = [r["provider"] for r in rows]
        self.assertIn("apify", names)
        self.assertNotIn("deepseek", names, "a window 82 days out is not due yet")

    def test_an_already_closed_window_is_reported_as_closed_not_hidden(self):
        from core.free_tier_calendar import expiring_windows

        rows = expiring_windows(
            today="2026-09-10",
            windows=[{"provider": "elevenlabs", "kind": "promo", "ends": "2026-08-01"}],
            notice_days=7,
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["closed"], "a lapsed free window must not drop off the calendar")

    def test_a_window_with_no_date_is_unknown_rather_than_safe(self):
        from core.free_tier_calendar import expiring_windows

        rows = expiring_windows(
            today="2026-09-10",
            windows=[{"provider": "openrouter", "kind": "free_models"}],
            notice_days=7,
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["unknown"])

    def test_the_shipped_config_parses_and_every_row_names_a_provider(self):
        """Exercise the file production reads, not a hand-built list."""
        from core.free_tier_calendar import load_windows

        windows = load_windows()
        self.assertTrue(windows, "config/free_tiers.json is missing or empty")
        for row in windows:
            self.assertTrue(str(row.get("provider") or "").strip())
            self.assertTrue(str(row.get("kind") or "").strip())

    def test_the_ops_verb_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("free-tiers", COMMANDS)


class TestOpenerPatternCheck(unittest.TestCase):
    """#407. `score_hook` already prices openers, but nothing *enforced* the
    measured-good shape: a hook could score acceptably while opening on a
    pattern the repo has recorded as weak, and the operator saw only a number.

    Deliberately editorial judgment, not prediction: with n around ten published
    videos there is no basis to claim an opener pattern causes retention, so the
    advisory says which recorded pattern it matches and does not invent a lift.
    """

    def test_a_weak_opener_is_named_as_an_advisory_not_just_scored(self):
        from core.opener_patterns import opener_advisory

        note = opener_advisory("In this video we look at the UFC 320 main event.")
        self.assertTrue(note)
        self.assertIn("opener", note.lower())

    def test_a_measured_good_opener_returns_nothing(self):
        from core.opener_patterns import opener_advisory

        self.assertEqual(opener_advisory("Jones knocked out Pereira in 94 seconds."), "")

    def test_the_advisory_never_claims_a_performance_lift(self):
        """GPT-6's evidence-labelling point: this is a rubric, not a prediction."""
        from core.opener_patterns import opener_advisory

        note = opener_advisory("So basically the thing about UFC 320 is that it happened.")
        for forbidden in ("retention", "% more", "will perform", "predicted", "increase"):
            self.assertNotIn(forbidden, note.lower())

    def test_it_reaches_the_operator_through_the_hook_display(self):
        from core.hook_score import display_hook_score, score_hook

        lines: list[str] = []
        display_hook_score(
            score_hook("In this video we cover the UFC 320 card."), print_fn=lines.append
        )
        joined = " ".join(lines).lower()
        self.assertIn("opener", joined, "the advisory is computed but never shown")


class TestCaptionPlacementDistinguishesAnOverlay(unittest.TestCase):
    """#717. #713 anchors captions by unique chroma in the bottom band, which is
    why a flat sky over textured ground read as a HUD (#718 gated it off).

    The discriminator is *spatial concentration*, not busy-ness: a score bug or a
    dark lower-third occupies a fraction of the band's width, while scenery is
    busy across the whole of it. A dark overlay is the same shape inverted -- a
    sub-region whose luminance variance is far below the band's.
    """

    @staticmethod
    def _scenery(dest: Path) -> Path:
        random.seed(11)
        img = Image.new("RGB", (256, 512))
        px = img.load()
        for y in range(512):
            for x in range(256):
                px[x, y] = (
                    (135, 180, 235)
                    if y < 256
                    else (
                        random.randint(20, 90),
                        random.randint(70, 140),
                        random.randint(20, 70),
                    )
                )
        img.save(dest)
        return dest

    @staticmethod
    def _score_bug(dest: Path) -> Path:
        """A quiet frame with a bright graphic in the bottom-left eighth."""
        img = Image.new("RGB", (256, 512), (30, 34, 42))
        px = img.load()
        for y in range(470, 500):
            for x in range(12, 80):
                px[x, y] = (240, 30, 30) if (x // 6) % 2 else (250, 220, 40)
        img.save(dest)
        return dest

    @staticmethod
    def _dark_lower_third(dest: Path) -> Path:
        """A textured frame with a flat dark box across the lower band."""
        random.seed(5)
        img = Image.new("RGB", (256, 512))
        px = img.load()
        for y in range(512):
            for x in range(256):
                px[x, y] = (
                    random.randint(60, 200),
                    random.randint(60, 200),
                    random.randint(60, 200),
                )
        for y in range(460, 505):
            for x in range(20, 236):
                px[x, y] = (8, 8, 10)
        img.save(dest)
        return dest

    def test_scenery_is_not_mistaken_for_an_overlay(self):
        from video.caption_place import bottom_band_overlay

        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(bottom_band_overlay(str(self._scenery(Path(tmp) / "s.png"))))

    def test_a_bright_score_bug_is_detected(self):
        from video.caption_place import bottom_band_overlay

        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(bottom_band_overlay(str(self._score_bug(Path(tmp) / "b.png"))))

    def test_a_dark_lower_third_is_detected(self):
        """The case #717 names explicitly: low chroma, so #713 could never see it."""
        from video.caption_place import bottom_band_overlay

        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(bottom_band_overlay(str(self._dark_lower_third(Path(tmp) / "d.png"))))

    @staticmethod
    def _strong_gradient(dest: Path) -> Path:
        """High spread, no step: luma ramps 20->200 across the band. This is the
        fixture that proves the step requirement is load-bearing -- drop it and a
        sunset or a vignette starts moving captions."""
        img = Image.new("RGB", (256, 512))
        px = img.load()
        band_top = 512 - max(8, 512 // 8)
        for y in range(512):
            if y < band_top:
                level = 20
            else:
                # Ramp the whole 20->200 range inside the band, so the spread gate
                # is cleared and only the step requirement can reject it.
                level = int(20 + ((y - band_top) / float(512 - band_top - 1)) * 180)
            for x in range(256):
                px[x, y] = (level, level, level)
        img.save(dest)
        return dest

    def test_a_strong_gradient_has_spread_but_no_step_and_is_rejected(self):
        from video.caption_place import band_overlay_metrics, bottom_band_overlay

        with tempfile.TemporaryDirectory() as tmp:
            path = str(self._strong_gradient(Path(tmp) / "grad.png"))
            metrics = band_overlay_metrics(path)
            self.assertIsNotNone(metrics)
            spread_ratio, step_share = metrics
            self.assertGreater(
                spread_ratio, 0.35, "this fixture must clear the spread gate to isolate the step"
            )
            self.assertLess(step_share, 0.5)
            self.assertFalse(bottom_band_overlay(path))

    def test_the_718_false_positives_are_all_rejected(self):
        """The measured regression: every case that made #718 gate this off."""
        from video.caption_place import bottom_band_overlay

        random.seed(3)
        with tempfile.TemporaryDirectory() as tmp:
            for name, fn in (
                (
                    "sky_grass",
                    lambda x, y: (135, 180, 235)
                    if y < 256
                    else (
                        random.randint(20, 90),
                        random.randint(70, 140),
                        random.randint(20, 70),
                    ),
                ),
                (
                    "sky_city",
                    lambda x, y: (120, 170, 225)
                    if y < 230
                    else (
                        random.randint(40, 220),
                        random.randint(30, 200),
                        random.randint(30, 200),
                    ),
                ),
            ):
                img = Image.new("RGB", (256, 512))
                px = img.load()
                for y in range(512):
                    for x in range(256):
                        px[x, y] = fn(x, y)
                path = Path(tmp) / f"{name}.png"
                img.save(path)
                with self.subTest(frame=name):
                    self.assertFalse(bottom_band_overlay(str(path)))

    def test_the_ops_verb_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("caption-anchor", COMMANDS)

    def test_a_flat_black_band_reads_as_no_contrast_not_as_a_broken_frame(self):
        """Found by running `ops caption-anchor` on the one real committed clip:
        its first frame has a pure black bottom band (median luma 0.00), and the
        verb reported 'unreadable' and exited 2 -- the same code a bad path gets.
        They are different answers: a bad path is a usage error, a flat band is a
        measured result whose operational meaning is 'captions stay at the
        bottom'."""
        from video.caption_place import band_reading

        img = Image.new("RGB", (256, 512), (0, 0, 0))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "black.png"
            img.save(path)
            state, metrics = band_reading(str(path))
        self.assertEqual(state, "no_contrast")
        self.assertIsNone(metrics)

    def test_a_missing_file_reads_as_no_frame(self):
        from video.caption_place import band_reading

        state, metrics = band_reading("does_not_exist_9f2.png")
        self.assertEqual(state, "no_frame")
        self.assertIsNone(metrics)

    def test_a_measurable_frame_reads_as_ok(self):
        from video.caption_place import band_reading

        with tempfile.TemporaryDirectory() as tmp:
            state, metrics = band_reading(str(self._score_bug(Path(tmp) / "b.png")))
        self.assertEqual(state, "ok")
        self.assertIsNotNone(metrics)

    def test_the_anchor_uses_the_overlay_test_when_the_flag_is_on(self):
        from video.caption_place import choose_caption_anchor

        with tempfile.TemporaryDirectory() as tmp:
            scenery = str(self._scenery(Path(tmp) / "s.png"))
            bug = str(self._score_bug(Path(tmp) / "b.png"))
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                self.assertEqual(choose_caption_anchor(scenery), "bottom")
                self.assertEqual(choose_caption_anchor(bug), "top")

    def test_a_low_horizon_is_a_known_remaining_false_positive(self):
        """The gap #717 does NOT close, asserted so it cannot be forgotten.

        Widening the window to 3x the band (needed to catch an overlay that fills
        the band edge-to-edge) means a horizon inside the bottom ~37% of the frame
        now lands in the sampled rows and reads as a composited step. Measured:
        a horizon at 50% of frame height is rejected (spread 0.09), but at 65%,
        70%, 80% and 90% it is detected.

        This is why `CAPTION_AUTO_PLACE` stays default-off (#718). What would close
        it is a *temporal* check rather than a spatial one: sample two frames a
        second apart -- a composited overlay is pixel-identical, scenery is not.
        Filed as #721.
        """
        from video.caption_place import bottom_band_overlay

        with tempfile.TemporaryDirectory() as tmp:
            random.seed(11)
            img = Image.new("RGB", (256, 512))
            px = img.load()
            horizon = int(512 * 0.70)
            for y in range(512):
                for x in range(256):
                    px[x, y] = (
                        (135, 180, 235)
                        if y < horizon
                        else (
                            random.randint(20, 90),
                            random.randint(70, 140),
                            random.randint(20, 70),
                        )
                    )
            path = Path(tmp) / "low_horizon.png"
            img.save(path)
            self.assertTrue(
                bottom_band_overlay(str(path)),
                "if this starts returning False the gap closed -- update #721 and "
                "reconsider the CAPTION_AUTO_PLACE default",
            )

    def test_the_flag_still_gates_it(self):
        """#718 stays in force until the operator opts in."""
        from video.caption_place import choose_caption_anchor

        with tempfile.TemporaryDirectory() as tmp:
            bug = str(self._score_bug(Path(tmp) / "b.png"))
            os.environ.pop("CAPTION_AUTO_PLACE", None)
            self.assertEqual(choose_caption_anchor(bug), "bottom")


try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - CI installs [app]
    QApplication = None  # type: ignore[misc, assignment]
    QMediaPlayer = None  # type: ignore[misc, assignment]

FIXTURE = Path("video/intro/channel_intro.mp4")


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
@unittest.skipUnless(FIXTURE.is_file(), "committed intro fixture missing")
class TestReviewWindowPlaysTheLastRun(unittest.TestCase):
    """#684. The last piece: the review room binding a REAL mp4 to a real player.

    #706 covered keyPressEvent with a fake player and #707 decoded the fixture
    through a bare `QMediaPlayer` + `QVideoSink`, deliberately bypassing
    `ReviewWindow`. What stayed operator-smoke is the window itself, because
    `desktop/review.py` built `QAudioOutput()` unconditionally and a machine with
    no audio sink -- any headless runner -- is where that breaks.

    So the production fix is real robustness, not test scaffolding: a review room
    that cannot open an audio device should still show the video.
    """

    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def _window(self):
        from desktop.review import ReviewWindow

        return ReviewWindow(
            context={
                "mp4_path": str(FIXTURE),
                "run_status": "published",
                "run_id": 75,
            }
        )

    def test_a_real_mp4_reaches_LoadedMedia_through_the_window(self):
        window = self._window()
        self.assertIsNotNone(window._player, "no player was built for a real file on disk")

        loop = QEventLoop()
        QTimer.singleShot(8000, loop.quit)
        window._player.mediaStatusChanged.connect(
            lambda status: loop.quit()
            if status
            in (
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
                QMediaPlayer.MediaStatus.InvalidMedia,
            )
            else None
        )
        if window._player.mediaStatus() not in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            loop.exec()

        self.assertEqual(
            window._player.error(),
            QMediaPlayer.Error.NoError,
            f"player error: {window._player.errorString()}",
        )
        self.assertGreater(
            window._player.duration(),
            0,
            "the window never decoded the fixture; duration stayed 0",
        )

    def test_the_window_still_shows_video_with_no_audio_device(self):
        """The headless case. A failing audio sink must not cost the video."""
        import desktop.review as review

        def boom():
            raise RuntimeError("no audio device")

        with patch.object(review, "QAudioOutput", boom):
            window = self._window()

        self.assertIsNotNone(window._player, "a missing audio device killed the player")
        self.assertIsNone(window._audio)

    def test_a_drafted_run_with_no_file_still_refuses(self):
        """The pre-existing guarantee must survive the audio change."""
        from desktop.review import ReviewWindow

        window = ReviewWindow(context={"mp4_path": "", "run_status": "drafted"})
        self.assertIsNone(window._player)
        self.assertIn("No last mp4", window.empty_label.text())


if __name__ == "__main__":
    unittest.main()
