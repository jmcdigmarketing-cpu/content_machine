"""Wave 9: #716, #723, #722, #721, #158 (core + ops slice).

Every test here was observed failing on unmodified 7c57b82 for the reason named
in its docstring.
"""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


class TestCiPushAndPrShareOneGroup(unittest.TestCase):
    """#716. #715 keyed the group on `github.ref`, which is `refs/heads/<b>` on
    push and `refs/pull/<n>/merge` on pull_request. They never collide, so a
    branch with an open same-repo PR still ran CI twice per push."""

    def test_the_group_line_prefers_head_ref(self):
        text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        groups = [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("group:") and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(groups), 1, f"expected one live concurrency group line: {groups}")
        self.assertIn(
            "github.head_ref || github.ref",
            groups[0],
            "push and pull_request still resolve to different groups",
        )


class TestHeadroomPrintsOncePerProcess(unittest.TestCase):
    """#723. `core/pipeline.py:267` calls `build_registry` once per variant, and
    #590's line printed every time with identical numbers."""

    def setUp(self):
        import core.discovery_headroom as dh

        dh._last_line = None

    @staticmethod
    def _run_registry_twice(lines: list[str]) -> str:
        import apis.register_signals as rs

        class _Pool:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            # #811: build_registry drives the pool explicitly now (its __exit__
            # would join the straggler the deadline is meant to drop).
            def shutdown(self, wait=True):
                pass

        out = io.StringIO()
        feed = iter(lines)
        with (
            patch.object(rs, "_active_signal_sources", return_value=()),
            patch.object(rs, "start_youtube_warmup_background", lambda: None),
            patch("core.discovery_headroom.headroom_line", side_effect=lambda **k: next(feed)),
            patch.object(rs, "ThreadPoolExecutor", _Pool),
            redirect_stdout(out),
        ):
            for _ in lines:
                rs.build_registry("UFC 320 variant", channel_id="tapin")
        return out.getvalue()

    def test_identical_numbers_across_variants_print_once(self):
        printed = self._run_registry_twice(["Headroom: same", "Headroom: same"])
        self.assertEqual(printed.count("Headroom: same"), 1, printed)

    def test_a_number_that_moved_prints_again(self):
        printed = self._run_registry_twice(["Headroom: 800 units", "Headroom: 700 units"])
        self.assertIn("800 units", printed)
        self.assertIn("700 units", printed)


class TestFreeTierDatesAreDerived(unittest.TestCase):
    """#722. #378's calendar typed every boundary into `config/free_tiers.json`.
    The shipped YouTube row said `resets: 2026-09-11`; on 2026-09-12 the calendar
    reported a *daily* quota as a CLOSED free window. `core/reset_window` already
    encodes both recurring cadences."""

    def test_the_shipped_config_has_no_recurring_window_closed_today(self):
        from core.free_tier_calendar import expiring_windows, load_windows

        rows = expiring_windows(today="2026-09-12", windows=load_windows(), notice_days=7)
        closed = [r["provider"] for r in rows if r.get("closed") and not r.get("ends")]
        self.assertEqual(closed, [], "a recurring window rotted into CLOSED")

    def test_providers_with_a_known_cadence_are_derived_not_typed(self):
        from core.free_tier_calendar import load_windows

        by_provider = {row["provider"]: row for row in load_windows()}
        for provider in ("apify", "youtube_data_api"):
            row = by_provider[provider]
            self.assertTrue(row.get("derive"), f"{provider} is still hand-typed")
            self.assertNotIn("resets", row, f"{provider} carries a typed date that will rot")

    def test_a_derived_daily_window_is_never_closed(self):
        from core.free_tier_calendar import expiring_windows

        for today in ("2026-09-12", "2027-01-31", "2030-06-01"):
            rows = expiring_windows(
                today=today,
                windows=[{"provider": "youtube_data_api", "kind": "daily", "derive": "youtube"}],
                notice_days=7,
            )
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]["closed"])
            self.assertFalse(rows[0]["unknown"])
            self.assertTrue(rows[0]["derived"])
            self.assertEqual(rows[0]["days"], 1)

    def test_the_apify_boundary_follows_the_billing_day(self):
        from core.free_tier_calendar import expiring_windows

        window = [{"provider": "apify", "kind": "monthly_credit", "derive": "apify"}]
        with patch.dict(os.environ, {"APIFY_RESET_DAY": "15"}):
            rows = expiring_windows(today="2026-09-12", windows=window, notice_days=7)
        self.assertEqual([r["days"] for r in rows], [3])
        with patch.dict(os.environ, {"APIFY_RESET_DAY": "1"}):
            rows = expiring_windows(today="2026-09-12", windows=window, notice_days=7)
        self.assertEqual(rows, [], "19 days out is outside the notice period")

    def test_an_underivable_window_is_unknown_not_safe(self):
        from core.free_tier_calendar import expiring_windows

        rows = expiring_windows(
            today="2026-09-12",
            windows=[{"provider": "x", "kind": "k", "derive": "no_such_provider"}],
            notice_days=7,
        )
        self.assertTrue(rows and rows[0]["unknown"])
        with patch.dict(os.environ, {"RESET_WINDOW_AUTO_ENABLE": "false"}):
            rows = expiring_windows(
                today="2026-09-12",
                windows=[{"provider": "youtube_data_api", "kind": "d", "derive": "youtube"}],
                notice_days=7,
            )
        self.assertTrue(rows and rows[0]["unknown"])

    def test_the_render_says_which_dates_are_derived(self):
        from core.free_tier_calendar import expiring_windows, render_calendar

        rows = expiring_windows(
            today="2026-09-12",
            windows=[
                {"provider": "youtube_data_api", "kind": "daily", "derive": "youtube"},
                {"provider": "elevenlabs", "kind": "monthly", "resets": "2026-09-15"},
            ],
            notice_days=7,
        )
        text = render_calendar(rows)
        self.assertIn("derived", text)
        self.assertIn("typed", text)
        self.assertNotIn("A reminder, not a live reading of any provider", text)

    def test_a_recorded_apify_reading_reaches_the_row(self):
        from core.free_tier_calendar import expiring_windows

        with (
            patch.dict(os.environ, {"APIFY_RESET_DAY": "15"}),
            patch("core.quota_governor.apify_get_usage", return_value={"usage": 1.2, "limit": 5.0}),
        ):
            rows = expiring_windows(
                today="2026-09-12",
                windows=[{"provider": "apify", "kind": "m", "derive": "apify"}],
                notice_days=7,
            )
        self.assertIn("$1.20/$5.00", rows[0].get("note", ""))


class TestCostTower(unittest.TestCase):
    """#158 (core slice). TTS, Apify, YouTube units and LLM spend each had a
    reader, spread across `ops reliability`, `ops economics`, the headroom line
    and `ops free-tiers`. Nothing put them in one place with one rule: an
    unreadable lane is unknown, never zero."""

    def _rows(self, **patches):
        from core import cost_tower

        defaults = {
            "core.discovery_headroom._youtube_units": (800, 1),
            "core.discovery_headroom._llm_spend_today": 0.25,
            "core.reliability._elevenlabs_section": {"budget": None, "chars_used": 1000},
            "core.quota_governor.apify_get_usage": None,
            "core.quota_governor.apify_is_exhausted": (False, ""),
            "core.free_tier_calendar.expiring_windows": [],
        }
        defaults.update(patches)
        ctx = [patch(target, return_value=value) for target, value in defaults.items()]
        for c in ctx:
            c.start()
        try:
            return {(r.lane, r.item): r for r in cost_tower.gather_tower()}
        finally:
            for c in ctx:
                c.stop()

    def test_every_lane_is_present(self):
        rows = self._rows()
        lanes = {lane for lane, _ in rows}
        self.assertTrue({"TTS", "Apify", "YouTube", "LLM"} <= lanes, lanes)

    def test_an_unreadable_youtube_store_is_unknown_not_zero(self):
        rows = self._rows(**{"core.discovery_headroom._youtube_units": (None, None)})
        yt = rows[("YouTube", "daily units")]
        self.assertEqual(yt.state, "unknown")
        self.assertIsNone(yt.used)

    def test_llm_spend_over_the_daily_budget_is_over(self):
        with patch.dict(os.environ, {"LLM_DAILY_BUDGET_USD": "0.20"}):
            rows = self._rows()
        self.assertEqual(rows[("LLM", "spend today")].state, "over")

    def test_an_exhausted_apify_purpose_is_over(self):
        rows = self._rows(**{"core.quota_governor.apify_is_exhausted": (True, "402 monthly limit")})
        self.assertEqual(rows[("Apify", "tiktok_trends")].state, "over")

    def test_a_closed_free_window_is_over(self):
        closed = [{"provider": "apify", "kind": "m", "days": -2, "closed": True, "unknown": False}]
        rows = self._rows(**{"core.free_tier_calendar.expiring_windows": closed})
        self.assertEqual(rows[("Free tier", "apify")].state, "over")

    def test_a_real_zero_renders_as_zero_not_as_no_reading(self):
        """Found running `ops cost-tower`: `$0.0000` LLM spend printed `-`, the same
        as a missing reading, because the renderer tested truthiness."""
        from core.cost_tower import TowerRow, render_tower

        text = render_tower([TowerRow("LLM", "spend today", 0.0, None, "ok")])
        self.assertIn("0.00", text)

    def test_a_recurring_reset_is_not_a_warning(self):
        """Found running `ops cost-tower`: the daily YouTube reset showed as NEAR
        every day. A recurring reset refills quota; only a window that *ends* is a
        $0 run about to become a paid one."""
        recurring = [
            {"provider": "youtube_data_api", "kind": "d", "days": 1, "closed": False,
             "unknown": False, "recurring": True},
            {"provider": "promo", "kind": "p", "days": 3, "closed": False,
             "unknown": False, "recurring": False},
        ]  # fmt: skip
        rows = self._rows(**{"core.free_tier_calendar.expiring_windows": recurring})
        self.assertEqual(rows[("Free tier", "youtube_data_api")].state, "ok")
        self.assertEqual(rows[("Free tier", "promo")].state, "near")

    def test_the_ops_verb_exits_nonzero_only_when_a_lane_is_over(self):
        from core.cost_tower import TowerRow
        from scripts import ops

        self.assertIn("cost-tower", ops.COMMANDS)
        ok = [TowerRow("LLM", "spend today", 0.1, 1.0, "ok")]
        over = [TowerRow("LLM", "spend today", 2.0, 1.0, "over")]
        with patch("core.cost_tower.gather_tower", return_value=ok), redirect_stdout(io.StringIO()):
            self.assertEqual(ops.cmd_cost_tower(None), 0)
        with (
            patch("core.cost_tower.gather_tower", return_value=over),
            redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(ops.cmd_cost_tower(None), 1)
        self.assertIn("OVER", out.getvalue())


def _footage(seed: int, *, sky_above: float | None = None, box: bool = False):
    """256x512 frame. Ground is noise re-rolled per seed, so two seeds a 'second'
    apart move; a flat sky and a composited box are identical in both."""
    import random

    from PIL import Image

    rnd = random.Random(seed)
    img = Image.new("RGB", (256, 512))
    px = img.load()
    horizon = int(512 * sky_above) if sky_above else 0
    for y in range(512):
        for x in range(256):
            if y < horizon:
                px[x, y] = (135, 180, 235)
            else:
                px[x, y] = (rnd.randint(20, 90), rnd.randint(70, 140), rnd.randint(20, 70))
    if box:
        for y in range(462, 505):
            for x in range(12, 150):
                px[x, y] = (250, 250, 250)
    return img


class TestCaptionOverlayNeedsTheBandToStayStill(unittest.TestCase):
    """#721. #717's step detector cannot tell a horizon at 65-90% of frame height
    from a lower-third: both are a full-width luminance step. Which is why
    `CAPTION_AUTO_PLACE` was default-off. A composited overlay is pixel-identical
    between two frames a second apart; footage is not."""

    def test_a_low_horizon_over_moving_ground_is_not_an_overlay(self):
        from video.caption_place import frames_show_static_overlay

        for frac in (0.65, 0.7, 0.8, 0.9):
            a, b = _footage(1, sky_above=frac), _footage(2, sky_above=frac)
            self.assertFalse(frames_show_static_overlay(a, b), f"horizon at {frac:.0%}")

    def test_an_overlay_that_stays_still_over_moving_footage_is(self):
        from video.caption_place import frames_show_static_overlay, temporal_reading

        a, b = _footage(1, box=True), _footage(2, box=True)
        self.assertTrue(frames_show_static_overlay(a, b), temporal_reading(a, b))

    def test_identical_frames_are_no_motion_not_an_overlay(self):
        """A locked-off shot or a still: everything is static, so nothing is proven."""
        from video.caption_place import frames_show_static_overlay, motion_reading

        a = _footage(1, box=True)
        self.assertEqual(motion_reading(a, a)[0], "no_motion")
        self.assertFalse(frames_show_static_overlay(a, a))

    def test_a_still_image_has_no_second_frame(self):
        import tempfile

        from core.hud_detect import _load_frame_at
        from video.caption_place import bottom_band_overlay, overlay_reading

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bug.png"
            _footage(1, box=True).save(path)
            self.assertIsNone(_load_frame_at(str(path), 1.0))
            self.assertEqual(overlay_reading(str(path))["motion"], "no_motion")
            self.assertFalse(bottom_band_overlay(str(path)))

    def test_the_default_follows_the_flag(self):
        """#721 flipped the default on; #727 turned it back off on 2026-09-13 after
        2 of 50 real stock clips moved captions with no overlay. Opt-in still works."""
        from video.caption_place import choose_caption_anchor

        with patch("video.caption_place.bottom_band_overlay", return_value=True):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CAPTION_AUTO_PLACE", None)
                self.assertEqual(choose_caption_anchor("clip.mp4"), "bottom")
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                self.assertEqual(choose_caption_anchor("clip.mp4"), "top")

    def test_ops_caption_anchor_prints_the_motion_reading(self):
        import tempfile
        from argparse import Namespace

        from scripts import ops

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "still.png"
            _footage(1, box=True).save(path)
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(ops.cmd_caption_anchor(Namespace(path=str(path))), 0)
        self.assertIn("motion", out.getvalue())
        self.assertIn("off by default", out.getvalue())


def _has_ffmpeg() -> bool:
    import shutil

    return bool(shutil.which("ffmpeg")) or os.getenv("CI", "").lower() in ("1", "true", "yes")


@unittest.skipUnless(_has_ffmpeg(), "ffmpeg not installed (required under CI)")
class TestCaptionPlacementOnARealEncodedClip(unittest.TestCase):
    """#721 end to end: an h264 clip through `_load_frame_at` and the anchor, so the
    thresholds survive real encoding rather than only PIL arithmetic."""

    @staticmethod
    def _clip(dest: Path, **kw) -> str:
        import subprocess

        for i in range(3):
            _footage(i + 1, **kw).save(dest.parent / f"f{i + 1}.png")
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-framerate", "1",
                "-i", str(dest.parent / "f%d.png"),
                "-vf", "fps=25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                str(dest),
            ],
            check=True, capture_output=True, timeout=60,
        )  # fmt: skip
        return str(dest)

    def test_a_static_overlay_on_moving_footage_moves_captions_when_opted_in(self):
        import tempfile

        from video.caption_place import choose_caption_anchor, overlay_reading

        with tempfile.TemporaryDirectory() as tmp:
            clip = self._clip(Path(tmp) / "overlay.mp4", box=True)
            # Opt-in since #727 (2026-09-13); the detector itself is what this proves.
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                self.assertEqual(choose_caption_anchor(clip), "top", overlay_reading(clip))

    def test_a_low_horizon_clip_keeps_captions_at_the_bottom(self):
        import tempfile

        from video.caption_place import choose_caption_anchor, overlay_reading

        with tempfile.TemporaryDirectory() as tmp:
            clip = self._clip(Path(tmp) / "horizon.mp4", sky_above=0.7)
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                self.assertEqual(choose_caption_anchor(clip), "bottom", overlay_reading(clip))


if __name__ == "__main__":
    unittest.main()
