"""Candidate 330: the crossfade must not shorten the background.

`build_hybrid_concat_command` xfades the local segment into the stock segment at the
join (decisions §26 — the operator's complaint was a hard cut from gameplay to
live-action with no transition). Its comment says:

    "Trim the stock clip by the fade so output duration stays the requested length."

It does not. `stock_dur` is `duration - local_dur` with no fade compensation, and an
`xfade` output runs `offset + len(second input)` = `(local_dur - fade) + stock_dur`,
which is `duration - fade`. Measured against real ffmpeg before the fix: a 6.000s
request produced **5.500s** — short by exactly the 0.5s fade.

The render loops the background with `-stream_loop -1`, so a short clip does not
error; it wraps early and shows a visible jump. That is the failure mode this repo
keeps hitting — nothing raises, nothing fails, the output is quietly wrong.

These are arithmetic tests over the emitted filter graph. The real-ffmpeg duration
check is in the commit message; a string test alone would not have caught this, since
the string was always well-formed.
"""

import re
import unittest

from assets.composite import build_hybrid_concat_command


def _graph(duration: float, ratio: float = 0.45) -> str:
    cmd = build_hybrid_concat_command(
        local_path="C:/tmp/local.mp4",
        stock_path="C:/tmp/stock.mp4",
        output_path="C:/tmp/out.mp4",
        duration=duration,
        local_ratio=ratio,
    )
    return cmd[cmd.index("-filter_complex") + 1]


def _parts(duration: float, ratio: float = 0.45) -> tuple[float, float, float, float]:
    """(local trim, stock trim, fade, offset) as the graph actually declares them."""
    g = _graph(duration, ratio)
    trims = [float(m) for m in re.findall(r"trim=duration=([\d.]+)", g)]
    fade = float(re.search(r"xfade=transition=fade:duration=([\d.]+)", g).group(1))
    offset = float(re.search(r":offset=([\d.]+)", g).group(1))
    return trims[0], trims[1], fade, offset


class TestOutputDurationIsPreserved(unittest.TestCase):
    """xfade output = offset + len(second input). That must equal what was asked for."""

    def test_six_seconds(self):
        local, stock, _fade, offset = _parts(6.0)
        self.assertAlmostEqual(offset + stock, 6.0, places=2)
        self.assertGreater(local, 0)

    def test_a_range_of_durations(self):
        for duration in (3.0, 6.0, 12.0, 45.0, 91.0, 227.0):
            local, stock, _fade, offset = _parts(duration)
            self.assertAlmostEqual(offset + stock, duration, places=2, msg=f"at {duration}s")

    def test_a_range_of_ratios(self):
        for ratio in (0.15, 0.3, 0.45, 0.6, 0.85):
            _local, stock, _fade, offset = _parts(30.0, ratio)
            self.assertAlmostEqual(offset + stock, 30.0, places=2, msg=f"at ratio {ratio}")


class TestFadeStaysSane(unittest.TestCase):
    def test_fade_is_positive_and_capped(self):
        for duration in (3.0, 30.0, 227.0):
            _l, _s, fade, _o = _parts(duration)
            self.assertGreater(fade, 0.0)
            self.assertLessEqual(fade, 0.5)

    def test_fade_never_exceeds_either_segment(self):
        # An xfade longer than a segment is a filter error, not a short clip.
        for duration in (2.0, 3.0, 30.0):
            for ratio in (0.15, 0.85):
                local, stock, fade, _o = _parts(duration, ratio)
                self.assertLessEqual(fade, local, msg=f"{duration}s @ {ratio}")
                self.assertLessEqual(fade, stock, msg=f"{duration}s @ {ratio}")

    def test_offset_is_never_negative(self):
        for duration in (2.0, 6.0, 227.0):
            _l, _s, _f, offset = _parts(duration)
            self.assertGreaterEqual(offset, 0.0)


class TestGraphShape(unittest.TestCase):
    def test_it_is_an_xfade_not_a_hard_concat(self):
        self.assertIn("xfade=transition=fade", _graph(10.0))

    def test_both_inputs_are_scaled_and_cropped(self):
        graph = _graph(10.0)
        self.assertEqual(graph.count("force_original_aspect_ratio=increase"), 2)
        self.assertEqual(graph.count("crop="), 2)


if __name__ == "__main__":
    unittest.main()
