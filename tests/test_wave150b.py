"""Wave 150b (2026-11-05) - #1995, a music bed generated with ffmpeg under the long videos.

The operator chose "Generate one with ffmpeg": no track was ever in assets/music/tapin, so no render
had a bed. A pad made from sines, a 64 s loop with no seam, six variants taken in turn, only under a
render longer than three minutes; a Short is unchanged.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Imported before any patch below (wave 145's reversed-suite failure).
import core.music
import video.render_video


class SynthBedTests(unittest.TestCase):
    def test_every_note_completes_whole_cycles_in_the_loop(self):
        chords = core.music.SYNTH_PROGRESSIONS[0]
        cycle = core.music.SYNTH_SLOT * len(chords)
        self.assertEqual(cycle, 64.0)
        for transpose in core.music.SYNTH_KEYS:
            expr = core.music.synth_expr(chords, transpose=transpose)
            freqs = [float(f) for f in re.findall(r"sin\(\d\*PI\*([\d.]+)\*t\)", expr)]
            self.assertGreater(len(freqs), 60)
            for freq in freqs:
                self.assertAlmostEqual(freq * cycle, round(freq * cycle), places=6)

    def test_much_quieter_than_the_first_cut(self):
        # the operator, 11-05: "much much quieter" - 12 dB under the first cut's +4 dB
        self.assertLessEqual(core.music.SYNTH_GAIN_DB, -8.0)
        graph = core.music.synth_bed_argv("pad.flac", 0)
        self.assertIn(
            f"volume={core.music.SYNTH_GAIN_DB:g}dB", graph[graph.index("-filter_complex") + 1]
        )

    def test_the_loop_is_the_second_cycle_at_its_own_rate(self):
        argv = core.music.synth_bed_argv("pad.flac", 0)
        graph = argv[argv.index("-filter_complex") + 1]
        self.assertIn("d=128", graph)
        self.assertIn("atrim=start=64:end=128", graph)
        self.assertNotIn("aresample", graph)  # it broke the period (0.006 between cycles)
        self.assertEqual(argv[argv.index("-c:a") + 1], "flac")  # no AAC priming at the join
        self.assertEqual(core.music.synth_variants(), 6)

    def _bed(self, tmp, **kwargs):
        def ffmpeg(argv, **_kw):
            Path(argv[-1]).write_bytes(b"flac")

        with (
            patch("config.paths.DATA_DIR", tmp),
            patch.object(core.music, "MUSIC_STATE_FILE", os.path.join(tmp, "music_last.json")),
            patch("subprocess.run", side_effect=ffmpeg) as run,
        ):
            return core.music.synth_bed("tapin", **kwargs), run.call_count

    def test_the_variants_are_taken_in_turn_and_made_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, made = self._bed(tmp)
            second, _ = self._bed(tmp)
            self.assertTrue(first.endswith(os.path.join("music_beds", "pad0_-8dB.flac")), first)
            self.assertTrue(second.endswith("pad1_-8dB.flac"))
            self.assertEqual(made, 1)
            again, made_again = self._bed(tmp, variant=0)
            self.assertEqual((again, made_again), (first, 0))  # kept, not made again
            state = json.loads(Path(tmp, "music_last.json").read_text(encoding="utf-8"))
            self.assertEqual(state["tapin:synth"], 0)

    def test_nothing_written_is_no_bed(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("config.paths.DATA_DIR", tmp),
            patch.object(core.music, "MUSIC_STATE_FILE", os.path.join(tmp, "m.json")),
            patch("subprocess.run"),
        ):
            self.assertEqual(core.music.synth_bed("tapin"), "")


class LongRenderBedTests(unittest.TestCase):
    def _resolve(self, duration, *, track=None, synth="true"):
        stages = []
        with (
            patch.dict(os.environ, {"MUSIC_PROVIDER": "", "MUSIC_SYNTH_LONG": synth}),
            patch("core.music.music_config", return_value={"enabled": True, "folder": "f",
                                                           "volume": 0.18}),
            patch("core.music.pick_track", return_value=track),
            patch("core.music.synth_bed", return_value="C:/data/music_beds/pad2.flac") as synth_bed,
        ):  # fmt: skip
            path = video.render_video._resolve_music_bed(
                duration, stages.append, channel_id="tapin"
            )
        return path, synth_bed.call_count, stages

    def test_a_long_render_gets_the_pad(self):
        path, made, stages = self._resolve(600.0)
        self.assertTrue(path.endswith("music_beds/pad2.flac"), path)
        self.assertEqual(made, 1)
        self.assertIn("generated pad", stages[0])

    def test_a_short_is_unchanged(self):
        self.assertEqual(self._resolve(62.0)[:2], (None, 0))

    def test_your_own_track_comes_first_and_the_switch_stops_it(self):
        path, made, _ = self._resolve(600.0, track=Path("assets/music/tapin/mine.mp3"))
        self.assertTrue(path.endswith("mine.mp3"))
        self.assertEqual(made, 0)
        self.assertEqual(self._resolve(600.0, synth="false")[:2], (None, 0))

    def test_the_status_line_says_so(self):
        with (
            patch.dict(os.environ, {"MUSIC_SYNTH_LONG": "true"}),
            patch("core.music.music_config", return_value={"enabled": True, "folder": "f",
                                                           "volume": 0.18}),
            patch("core.music.library_tracks", return_value=[]),
        ):  # fmt: skip
            self.assertIn("long videos: the generated pad", core.music.library_status_line("tapin"))


if __name__ == "__main__":
    unittest.main()
