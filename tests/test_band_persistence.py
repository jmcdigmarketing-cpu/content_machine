"""#739: a source rule needs the band to be constant. It is not.

The item asked two questions and had been recommended and dropped three times
for want of the measurement: how often does gameplay carry a HUD *across the
whole segment*, and do stock segments ever carry one? #730 sampled frames at 0s
and 1s; `clip_bands._FRAME_FRACTIONS` samples two. Neither answers "is it still
there", which is what a source rule turns on.

Measured 2026-09-20 over 8 fractions per clip, 147 gameplay + 52 stock:

    gameplay  147 clips | ever 92 | ALWAYS 2 | intermittent 90 | median 0.25
    stock      52 clips | ever  6 | ALWAYS 0 | intermittent  6 | median 0.00

Both premises fail. Gameplay HUDs are not near-constant (2 of 147), so
anchoring the whole gameplay segment would cost picture in the ~75% of frames
with no band; and stock is not clean either. The source rule does not ship.
What ships is the measurement, so the answer is re-checkable as the library
grows instead of being re-derived a fifth time.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class _Frame:
    """Stands in for a decoded frame; `_band_share` is patched per test."""

    def __init__(self, tag: str) -> None:
        self.tag = tag


class TestPersistenceIsARateNotABoolean(unittest.TestCase):
    def test_a_band_in_two_of_eight_frames_reads_as_a_quarter(self) -> None:
        from assets.clip_bands import band_persistence

        frames = [_Frame(str(i)) for i in range(8)]
        with (
            patch("core.hud_detect._load_frame_at", side_effect=frames),
            patch("assets.clip_ingest._probe_duration", return_value=40.0),
            patch(
                "assets.clip_bands._band_share",
                side_effect=lambda f, top: 0.1 if (not top and f.tag in ("0", "1")) else 0.0,
            ),
        ):
            reading = band_persistence("clip.mp4")

        self.assertEqual(reading["frames"], 8)
        self.assertEqual(reading["bottom_hits"], 2)
        self.assertEqual(reading["bottom_rate"], 0.25)

    def test_a_constant_band_reads_as_one(self) -> None:
        from assets.clip_bands import band_persistence

        frames = [_Frame(str(i)) for i in range(8)]
        with (
            patch("core.hud_detect._load_frame_at", side_effect=frames),
            patch("assets.clip_ingest._probe_duration", return_value=40.0),
            patch("assets.clip_bands._band_share", side_effect=lambda f, top: 0.0 if top else 0.2),
        ):
            reading = band_persistence("clip.mp4")

        self.assertEqual(reading["bottom_rate"], 1.0)

    def test_an_unreadable_clip_is_not_a_clean_clip(self) -> None:
        """No frames must read as unknown, never as 'no band'."""
        from assets.clip_bands import band_persistence

        with (
            patch("core.hud_detect._load_frame_at", return_value=None),
            patch("assets.clip_ingest._probe_duration", return_value=40.0),
        ):
            reading = band_persistence("clip.mp4")

        self.assertEqual(reading["frames"], 0)
        self.assertIsNone(reading["bottom_rate"])


class TestTheSummarySeparatesConstantFromIntermittent(unittest.TestCase):
    def test_always_and_intermittent_are_counted_apart(self) -> None:
        """The distinction the whole item turns on."""
        from assets.clip_bands import summarize_persistence

        rows = [
            {"frames": 8, "bottom_hits": 8, "bottom_rate": 1.0},
            {"frames": 8, "bottom_hits": 2, "bottom_rate": 0.25},
            {"frames": 8, "bottom_hits": 0, "bottom_rate": 0.0},
            {"frames": 0, "bottom_hits": 0, "bottom_rate": None},  # unreadable, excluded
        ]
        out = summarize_persistence("gameplay", rows)

        self.assertEqual(out["clips"], 3)
        self.assertEqual(out["always"], 1)
        self.assertEqual(out["intermittent"], 1)
        self.assertEqual(out["ever"], 2)
        self.assertEqual(out["median_rate"], 0.25)

    def test_the_render_names_the_verdict(self) -> None:
        from assets.clip_bands import render_persistence, summarize_persistence

        gameplay = summarize_persistence(
            "gameplay", [{"frames": 8, "bottom_hits": 2, "bottom_rate": 0.25}] * 10
        )
        stock = summarize_persistence(
            "stock", [{"frames": 8, "bottom_hits": 0, "bottom_rate": 0.0}] * 10
        )
        text = render_persistence([gameplay, stock])

        self.assertIn("gameplay", text)
        self.assertIn("stock", text)
        # A source rule is only safe when gameplay is constant; say so either way.
        self.assertIn("intermittent", text.lower())


if __name__ == "__main__":
    unittest.main()
