"""Wave 24: irregular 3-8 s shots, parallel shot encodes, per-clip text bands, intake.

Operator, 2026-09-19, after the wave 23 preview: "can it be a bit longer cuts? like between
the 3-8s range? ... dont cut consistiently tbh reverse that decision." That reverses wave 22's
steady ~2.5 s rhythm (#782), so the wave 22 guards move with it. Each test here failed on
unmodified e7e9521 unless its docstring says it guards existing behaviour.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _words(text: str, rate: float = 0.35) -> list[dict]:
    out, t = [], 0.0
    for word in text.split():
        out.append({"word": word, "start": round(t, 3), "end": round(t + rate - 0.05, 3)})
        t += rate
    return out


class TestIrregularCuts(unittest.TestCase):
    """#792: every shot is 3-8 s and the pacing never settles into a beat."""

    def test_shots_are_three_to_eight_seconds(self):
        from assets.fast_cut import cut_points

        bounds = cut_points(120.0, rng=random.Random(7))
        self.assertEqual(bounds[0], 0.0)
        self.assertEqual(bounds[-1], 120.0)
        shots = [b - a for a, b in pairwise(bounds)]
        for shot in shots:
            self.assertGreaterEqual(shot, 3.0 - 1e-6, shots)
            self.assertLessEqual(shot, 8.0 + 1e-6, shots)

    def test_lengths_are_irregular(self):
        from assets.fast_cut import cut_points

        for seed in range(20):
            shots = [b - a for a, b in pairwise(cut_points(200.0, rng=random.Random(seed)))]
            self.assertGreaterEqual(len(shots), 20, shots)
            # Every pair but the last: when what is left over is close to 2x the longest shot,
            # both halves are forced near the maximum and no 1 s gap exists.
            for a, b in pairwise(shots[:-1]):
                self.assertGreaterEqual(abs(a - b), 1.0 - 1e-6, (seed, shots))
            spread = max(shots) - min(shots)
            self.assertGreater(spread, 2.0, (seed, shots))

    def test_cuts_still_land_on_phrase_ends(self):
        from assets.fast_cut import cut_points

        text = ("Rockstar sells the map, not the story. " * 40).strip()
        words = _words(text)
        bounds = cut_points(words[-1]["end"] + 0.2, words, rng=random.Random(3))
        phrase_ends = {w["end"] for w in words if w["word"][-1:] in ",.!?;:"}
        inner = bounds[1:-1]
        on_phrase = sum(1 for b in inner if b in phrase_ends)
        self.assertGreaterEqual(on_phrase, len(inner) * 0.6, (inner, sorted(phrase_ends)))

    def test_range_is_configurable(self):
        from assets.fast_cut import cut_range

        with patch.dict(os.environ, {"BACKGROUND_CUT_MIN": "4", "BACKGROUND_CUT_MAX": "6"}):
            self.assertEqual(cut_range(), (4.0, 6.0))
        # The wave 22 key still works: it becomes the midpoint of a +/-2.5 s spread.
        with patch.dict(
            os.environ,
            {"BACKGROUND_CUT_MIN": "", "BACKGROUND_CUT_MAX": "", "BACKGROUND_CUT_SECONDS": "5"},
        ):
            lo, hi = cut_range()
        self.assertLess(lo, 5.0)
        self.assertGreater(hi, 5.0)
        with patch.dict(
            os.environ,
            {"BACKGROUND_CUT_MIN": "9", "BACKGROUND_CUT_MAX": "2", "BACKGROUND_CUT_SECONDS": ""},
        ):
            lo, hi = cut_range()
        self.assertLessEqual(lo, hi)

    def test_a_short_video_still_gets_more_than_one_shot(self):
        from assets.fast_cut import cut_points

        self.assertGreaterEqual(len(cut_points(12.0, rng=random.Random(1))) - 1, 2)


class TestParallelShots(unittest.TestCase):
    """#796: shots encode in parallel, and the concat list stays in playback order."""

    def _compose(self, duration: float, *, workers: int | None = None):
        import config.paths as paths
        from assets import fast_cut

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        order: list[str] = []

        def fake_render(clip, start, length, path):
            order.append(os.path.basename(path))
            Path(path).write_bytes(b"x")

        written: dict[str, str] = {}

        def fake_concat(list_path, output, _duration):
            written["list"] = Path(list_path).read_text(encoding="utf-8")
            Path(output).write_bytes(b"x")

        keys, windows = fast_cut.expand_pool(["a.mp4", "b.mp4", "c.mp4"], {})
        env = {"BACKGROUND_SHOT_WORKERS": str(workers)} if workers else {}
        with (
            patch.dict(os.environ, env),
            patch.object(paths, "DATA_DIR", tmp),
            patch.object(fast_cut, "_render_shot", side_effect=fake_render),
            patch.object(fast_cut, "_concat", side_effect=fake_concat),
            patch.object(fast_cut, "shot_brightness", return_value=200.0),
        ):
            fast_cut._compose(keys, windows, "GTA", duration, None)
        return order, written["list"]

    def test_concat_list_is_in_order(self):
        _order, listing = self._compose(60.0)
        names = [line.split("/")[-1].rstrip("'") for line in listing.splitlines()]
        self.assertEqual(names, sorted(names), names)

    def test_shots_run_on_more_than_one_worker(self):
        from assets.fast_cut import shot_workers

        with patch.dict(os.environ, {"BACKGROUND_SHOT_WORKERS": "3"}):
            self.assertEqual(shot_workers(), 3)
        with patch.dict(os.environ, {"BACKGROUND_SHOT_WORKERS": ""}):
            self.assertGreaterEqual(shot_workers(), 2)
        with patch.dict(os.environ, {"BACKGROUND_SHOT_WORKERS": "0"}):
            self.assertEqual(shot_workers(), 1)

    def test_a_failing_shot_still_raises(self):
        """Guards existing behaviour: a broken shot must not concat into a short video."""
        import config.paths as paths
        from assets import fast_cut

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        keys, windows = fast_cut.expand_pool(["a.mp4", "b.mp4", "c.mp4"], {})
        with (
            patch.object(paths, "DATA_DIR", tmp),
            patch.object(fast_cut, "_render_shot", side_effect=RuntimeError("ffmpeg died")),
            patch.object(fast_cut, "_concat") as concat,
        ):
            with self.assertRaises(RuntimeError):
                fast_cut._compose(keys, windows, "GTA", 30.0, None)
        self.assertFalse(concat.called)


def _frame(width: int, height: int, *, top: int = 0, bottom: int = 0, seed: int = 0):
    from PIL import Image

    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        for x in range(width):
            px[x, y] = (rng.randint(70, 190),) * 3
    for y in range(top):
        for x in range(width):
            px[x, y] = (8, 8, 8) if x % 7 else (245, 245, 245)
    for y in range(height - bottom, height):
        for x in range(width):
            px[x, y] = (8, 8, 8) if x % 7 else (245, 245, 245)
    return img


class TestClipBands(unittest.TestCase):
    """#788: each clip's own text bands, measured once, instead of one fixed 18% crop."""

    def test_a_flat_clip_has_no_bands(self):
        from assets.clip_bands import bands_from_frames

        frames = [_frame(128, 72, seed=1), _frame(128, 72, seed=2)]
        self.assertEqual(bands_from_frames(frames), {"top": 0.0, "bottom": 0.0})

    def test_a_bottom_strip_is_found(self):
        from assets.clip_bands import bands_from_frames

        frames = [_frame(128, 72, bottom=9, seed=1), _frame(128, 72, bottom=9, seed=2)]
        bands = bands_from_frames(frames)
        self.assertGreater(bands["bottom"], 0.05)
        self.assertEqual(bands["top"], 0.0)

    def test_a_top_strip_is_found(self):
        from assets.clip_bands import bands_from_frames

        frames = [_frame(128, 72, top=9, seed=1), _frame(128, 72, top=9, seed=2)]
        bands = bands_from_frames(frames)
        self.assertGreater(bands["top"], 0.05)
        self.assertEqual(bands["bottom"], 0.0)

    def test_a_band_in_one_frame_only_is_ignored(self):
        """A passing car or a bright sign must not cost the clip a crop."""
        from assets.clip_bands import bands_from_frames

        frames = [_frame(128, 72, bottom=9, seed=1), _frame(128, 72, seed=2)]
        self.assertEqual(bands_from_frames(frames)["bottom"], 0.0)

    def test_crop_for_clip_caps_the_total(self):
        from assets.clip_bands import crop_for_clip

        with patch("assets.clip_bands.stored_bands", return_value={"top": 0.25, "bottom": 0.25}):
            top, bottom = crop_for_clip("x.mp4")
        self.assertLessEqual(top + bottom, 0.30 + 1e-9)
        self.assertGreaterEqual(bottom, top, "the larger band keeps its share")

    def test_a_measured_plate_adds_a_top_crop(self):
        from assets.clip_bands import crop_for_clip

        with (
            patch("assets.clip_bands.stored_bands", return_value={"top": 0.08, "bottom": 0.0}),
            patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": ""}),
        ):
            self.assertEqual(crop_for_clip("x.mp4"), (0.08, 0.18))

    def test_unmeasured_clip_keeps_the_env_default(self):
        from assets.clip_bands import crop_for_clip

        with (
            patch("assets.clip_bands.stored_bands", return_value=None),
            patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": ""}),
        ):
            self.assertEqual(crop_for_clip("x.mp4"), (0.0, 0.18))

    def test_a_measurement_never_removes_the_bottom_floor(self):
        """GTA's mission text is white-on-nothing, not a luminance step: measuring a clip as
        clean must not take away the crop that keeps that text out (#788 stays open)."""
        from assets.clip_bands import crop_for_clip

        with (
            patch("assets.clip_bands.stored_bands", return_value={"top": 0.0, "bottom": 0.02}),
            patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": ""}),
        ):
            self.assertEqual(crop_for_clip("x.mp4"), (0.0, 0.18))


class TestShotCommandUsesBands(unittest.TestCase):
    def test_top_and_bottom_crop_reach_the_filter(self):
        from assets.fast_cut import build_shot_command

        with patch("assets.clip_bands.crop_for_clip", return_value=(0.1, 0.2)):
            vf = build_shot_command("a.mp4", 0.0, 3.0, "o.mp4")
        vf = vf[vf.index("-vf") + 1]
        self.assertTrue(vf.startswith("crop=iw:trunc(ih*0.7000/2)*2:0:trunc(ih*0.1000/2)*2,"), vf)

    def test_no_crop_filter_when_the_clip_is_clean(self):
        from assets.fast_cut import build_shot_command

        with patch("assets.clip_bands.crop_for_clip", return_value=(0.0, 0.0)):
            vf = build_shot_command("a.mp4", 0.0, 3.0, "o.mp4")
        self.assertNotIn("crop=iw:", vf[vf.index("-vf") + 1])

    @unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
    def test_a_top_bar_is_gone_from_the_shot(self):
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        src = os.path.join(work, "src.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                "color=c=black:s=1920x1080:d=2:r=30",
                "-vf", "drawbox=x=0:y=0:w=iw:h=ih*0.1:color=white:t=fill",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", src,
            ],
            check=True,
        )  # fmt: skip
        from assets.fast_cut import build_shot_command

        shot = os.path.join(work, "shot.mp4")
        with patch("assets.clip_bands.crop_for_clip", return_value=(0.12, 0.0)):
            subprocess.run(build_shot_command(src, 0.0, 1.0, shot), check=True)
        out = subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-i", shot, "-vf", "crop=iw:ih*0.2:0:0",
                "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-",
            ],
            capture_output=True, check=True,
        )  # fmt: skip
        self.assertTrue(out.stdout)
        self.assertLess(max(out.stdout), 60, "the white bar survived the crop")


class TestBandsInTheClipIndex(unittest.TestCase):
    def test_ingest_records_bands(self):
        from assets import clip_ingest

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        index = os.path.join(tmp, "clip_index.json")
        with (
            patch.object(clip_ingest, "CLIP_INDEX_FILE", index),
            patch.object(clip_ingest, "_probe_duration", return_value=30.0),
            patch.object(clip_ingest, "_probe_stream", return_value=(1920, 1080, "h264")),
            patch.object(clip_ingest, "_hud_flag", return_value=False),
            patch(
                "assets.clip_bands.measure_bands", return_value={"top": 0.0, "bottom": 0.12}
            ) as measure,
        ):
            clip_ingest._record_index(os.path.join(tmp, "clip.mp4"), "https://example.org/x")
        with open(index, encoding="utf-8") as f:
            meta = next(iter(json.load(f)["clips"].values()))
        self.assertEqual(meta["bands"], {"top": 0.0, "bottom": 0.12})
        measure.assert_called_once()

    def test_stored_bands_reads_the_index(self):
        from assets import clip_bands

        path = os.path.abspath("clip.mp4")
        with patch.object(
            clip_bands, "_index_clips", return_value={path: {"bands": {"top": 0.1, "bottom": 0.0}}}
        ):
            self.assertEqual(clip_bands.stored_bands("clip.mp4"), {"top": 0.1, "bottom": 0.0})
            self.assertIsNone(clip_bands.stored_bands("other.mp4"))


class TestBulkIntake(unittest.TestCase):
    """#793: a folder of downloads is one command."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.drop = os.path.join(self.root, "Minecraft")
        os.makedirs(self.drop)
        for name in ("a.mp4", "b.mov", "notes.txt"):
            Path(self.drop, name).write_bytes(b"v")
        self.lib = os.path.join(self.root, "lib")
        os.makedirs(self.lib)

    def _run(self, **kw):
        from assets import clip_ingest

        def fake_remux(src, dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(src, dest)

        with (
            patch.object(clip_ingest, "_remux_muted_h264", side_effect=fake_remux),
            patch.object(clip_ingest, "_record_index"),
        ):
            return clip_ingest.add_footage_folder(self.drop, library_root=self.lib, **kw)

    def test_every_video_is_imported_and_the_game_defaults_to_the_folder(self):
        rows = self._run(licence="CC0", source_url="https://example.org", apply=True)
        self.assertEqual([r.status for r in rows], ["copied", "copied"])
        folders = {os.path.basename(os.path.dirname(r.dest)) for r in rows}
        self.assertEqual(folders, {"Minecraft"})
        self.assertTrue(all(r.dest.endswith((".mp4", ".mov")) for r in rows))

    def test_dry_run_and_explicit_game(self):
        rows = self._run(game="Roblox", licence="CC0", apply=False)
        self.assertEqual([r.status for r in rows], ["matched", "matched"])
        self.assertEqual({os.path.basename(os.path.dirname(r.dest)) for r in rows}, {"Roblox"})
        self.assertFalse(os.listdir(self.lib))

    def test_a_licence_is_still_required(self):
        rows = self._run(licence="", apply=True)
        self.assertTrue(all(r.status == "failed" for r in rows), rows)


class TestShortPreview(unittest.TestCase):
    """#795: a 30 s look instead of a 140 s render."""

    def test_seconds_trims_the_audio_copy(self):
        from assets import fast_cut

        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        audio = os.path.join(work, "voice.mp3")
        Path(audio).write_bytes(b"mp3")
        Path(audio + ".words.json").write_text(
            json.dumps(
                [
                    {"word": "one", "start": 0.0, "end": 1.0},
                    {"word": "two", "start": 40.0, "end": 41.0},
                ]
            ),
            encoding="utf-8",
        )
        trimmed: list[tuple[str, float]] = []

        def fake_trim(path, seconds):
            trimmed.append((path, seconds))

        def fake_render(copy, topic, name, script, channel_id):
            return os.path.join(os.path.dirname(copy), "..", "video", name), None

        with (
            patch.object(fast_cut, "_trim_audio", side_effect=fake_trim),
            patch("video.render_video.render_vertical_video", side_effect=fake_render),
        ):
            fast_cut.render_preview(audio, "GTA", "tapin", out_dir=work, seconds=30)
        self.assertEqual(len(trimmed), 1)
        self.assertEqual(trimmed[0][1], 30)
        words = json.loads(
            Path(next(Path(work, "audio").glob("*.mp3.words.json"))).read_text(encoding="utf-8")
        )
        self.assertEqual([w["word"] for w in words], ["one"], "words past the trim are dropped")

    def test_full_length_by_default(self):
        """Guards existing behaviour: no --seconds, no trim."""
        from assets import fast_cut

        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        audio = os.path.join(work, "voice.mp3")
        Path(audio).write_bytes(b"mp3")
        with (
            patch.object(fast_cut, "_trim_audio") as trim,
            patch(
                "video.render_video.render_vertical_video",
                side_effect=lambda c, t, n, s, ch: (n, None),
            ),
        ):
            fast_cut.render_preview(audio, "GTA", "tapin", out_dir=work)
        self.assertFalse(trim.called)


class TestTempSweep(unittest.TestCase):
    """#797, found in the wave 24 debug sweep: data/tmp/hybrid_backgrounds had reached 4.2 GB
    of composed backgrounds going back to June - nothing ever deleted them."""

    def test_old_backgrounds_are_swept_and_recent_ones_kept(self):
        import time

        from assets.fast_cut import prune_backgrounds

        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        old = Path(work, "fastcut_old.mp4")
        old.write_bytes(b"x" * (2 * 1024 * 1024))
        os.utime(old, (time.time() - 10 * 86400,) * 2)
        fresh = Path(work, "fastcut_new.mp4")
        fresh.write_bytes(b"x")
        freed = prune_backgrounds(work)
        self.assertEqual(freed, 2)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_a_missing_directory_is_not_an_error(self):
        from assets.fast_cut import prune_backgrounds

        self.assertEqual(prune_backgrounds(os.path.join(tempfile.mkdtemp(), "nope")), 0)


class TestWave24Wiring(unittest.TestCase):
    def test_env_example_documents_the_new_keys(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        for key in ("BACKGROUND_CUT_MIN", "BACKGROUND_CUT_MAX", "BACKGROUND_SHOT_WORKERS"):
            self.assertIn(key, text)

    def test_footage_report_shows_measured_bands(self):
        from assets.clip_ingest import render_coverage

        rows = [
            {"niche": "GTA", "folder": "GTA V", "clips": 25, "bands": {"top": 0.0, "bottom": 0.14}},
            {"niche": "Minecraft", "folder": "", "clips": 0},
        ]
        text = render_coverage(rows)
        self.assertIn("14%", text)
        self.assertIn("Minecraft", text)


if __name__ == "__main__":
    unittest.main()
