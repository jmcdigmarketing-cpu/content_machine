"""Wave 23: crop the game's own text, long gameplay files, niche footage, the 48h check.

Operator, 2026-09-19, after the fast-cut preview: "like it, i could prob pull copyright free
videos to be cut, woul long form gameplay work? like 20min long and you cut it? ... dont skip
those clips, crop it out". Each test here failed on unmodified acf88ed unless its docstring
says it guards existing behaviour.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class TestCropGameText(unittest.TestCase):
    """#785: the bottom band of the game frame (mission text, HUD) is cropped, never skipped."""

    def test_shot_crops_the_bottom_band_before_scaling(self):
        from assets.fast_cut import build_shot_command

        with patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": ""}):
            vf = build_shot_command("a.mp4", 1.0, 2.5, "o.mp4")
        vf = vf[vf.index("-vf") + 1]
        self.assertTrue(vf.startswith("crop=iw:trunc(ih*0.8200/2)*2:0:0,"), vf)
        self.assertLess(vf.index("crop=iw"), vf.index("scale="))

    def test_crop_is_configurable_and_clamped(self):
        from assets.fast_cut import build_shot_command, crop_bottom

        with patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": "0"}):
            vf = build_shot_command("a.mp4", 0, 2, "o.mp4")
            self.assertEqual(crop_bottom(), 0.0)
        self.assertNotIn("crop=iw:", vf[vf.index("-vf") + 1])
        with patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": "0.9"}):
            self.assertEqual(crop_bottom(), 0.4)
        with patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": "junk"}):
            self.assertEqual(crop_bottom(), 0.18)

    @unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
    def test_text_in_the_bottom_band_is_gone_from_the_shot(self):
        """A white bar across the source's bottom 12% must not reach the rendered shot."""
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        src = os.path.join(work, "src.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                "color=c=black:s=1920x1080:d=2:r=30",
                "-vf", "drawbox=x=0:y=ih*0.88:w=iw:h=ih*0.12:color=white:t=fill",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", src,
            ],
            check=True,
        )  # fmt: skip
        from assets.fast_cut import build_shot_command

        shot = os.path.join(work, "shot.mp4")
        with patch.dict(os.environ, {"BACKGROUND_CROP_BOTTOM": ""}):
            subprocess.run(build_shot_command(src, 0.0, 1.0, shot), check=True)
        out = subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-i", shot, "-vf", "crop=iw:ih*0.2:0:ih*0.8",
                "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-",
            ],
            capture_output=True, check=True,
        )  # fmt: skip
        self.assertTrue(out.stdout)
        ymax = [max(out.stdout)]
        self.assertLess(ymax[0], 60, "the white bar survived the crop")


class TestLongSourceWindows(unittest.TestCase):
    """A single 20-minute gameplay file must feed a whole fast-cut Short on its own."""

    def test_a_long_file_becomes_many_windows(self):
        from assets.fast_cut import expand_pool

        keys, windows = expand_pool(["long.mp4", "short.mp4"], {"long.mp4": 1200, "short.mp4": 20})
        long_keys = [k for k in keys if windows[k][0] == "long.mp4"]
        self.assertEqual(len(long_keys), 40)
        self.assertEqual(len([k for k in keys if windows[k][0] == "short.mp4"]), 1)
        offsets = sorted(windows[k][1] for k in long_keys)
        self.assertEqual(offsets[0], 0.0)
        self.assertTrue(all(b - a >= 30.0 - 1e-6 for a, b in pairwise(offsets)))

    def test_unprobed_clip_is_one_window(self):
        from assets.fast_cut import expand_pool

        keys, windows = expand_pool(["x.mp4"], {})
        self.assertEqual(keys, ["x.mp4"])
        self.assertEqual(windows["x.mp4"], ("x.mp4", 0.0, None))

    def test_one_long_file_makes_a_short_with_spread_out_shots(self):
        from assets.fast_cut import cut_points, expand_pool, plan_windowed_shots

        keys, windows = expand_pool(["long.mp4"], {"long.mp4": 1200})
        for seed in range(40):
            shots = plan_windowed_shots(cut_points(55.0), keys, windows, rng=random.Random(seed))
            self.assertGreaterEqual(len(shots), 18)
            self.assertTrue(all(clip == "long.mp4" for clip, _s, _l in shots))
            starts = [s for _c, s, _l in shots]
            self.assertEqual(len(set(starts)), len(starts))
            for a, b in pairwise(starts):
                self.assertGreaterEqual(abs(a - b), 15.0, (seed, starts))
            for _c, start, length in shots:
                self.assertLessEqual(start + length, 1200.0)

    def test_the_pool_gate_counts_windows_not_files(self):
        from assets import fast_cut

        with (
            patch.dict(os.environ, {"BACKGROUND_FAST_CUT": "true"}),
            patch.object(fast_cut, "_clip_pool", return_value=["long.mp4"]),
            patch.object(fast_cut, "_probe", return_value=1200.0),
            patch.object(fast_cut, "_compose", return_value="ok") as compose,
        ):
            self.assertEqual(fast_cut.try_fast_cut_background("GTA", "tapin", duration=55), "ok")
        self.assertTrue(compose.called)
        with (
            patch.dict(os.environ, {"BACKGROUND_FAST_CUT": "true"}),
            patch.object(fast_cut, "_clip_pool", return_value=["a.mp4"]),
            patch.object(fast_cut, "_probe", return_value=20.0),
            patch.object(fast_cut, "_compose", return_value="ok") as compose,
        ):
            self.assertIsNone(fast_cut.try_fast_cut_background("GTA", "tapin", duration=55))
        self.assertFalse(compose.called)


class TestDarkShots(unittest.TestCase):
    """Found in the wave 23 preview: 2 of 18 sampled frames were near-black night-driving shots.
    A shot that renders nearly black is re-drawn from elsewhere in the pool (twice at most)."""

    @unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
    def test_brightness_of_black_and_grey(self):
        from assets.fast_cut import shot_brightness

        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        out = {}
        for name, colour in (("black", "black"), ("grey", "gray")):
            path = os.path.join(work, f"{name}.mp4")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c={colour}:s=1080x1920:d=1:r=30", "-pix_fmt", "yuv420p", path,
                ],
                check=True,
            )  # fmt: skip
            out[name] = shot_brightness(path, 1.0)
        self.assertLess(out["black"], 25)
        self.assertGreater(out["grey"], 100)

    def test_a_dark_shot_is_redrawn_from_another_window(self):
        import config.paths as paths
        from assets import fast_cut

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        rendered: list[tuple[str, float]] = []

        def fake_render(clip, start, length, path):
            rendered.append((clip, start))
            Path(path).write_bytes(b"x")

        def fake_concat(list_path, output, duration):
            Path(output).write_bytes(b"x")

        keys, windows = fast_cut.expand_pool(["a.mp4", "b.mp4", "c.mp4"], {})
        lumas = iter([5.0] + [120.0] * 200)
        with (
            patch.object(paths, "DATA_DIR", tmp),
            patch.object(fast_cut, "_render_shot", side_effect=fake_render),
            patch.object(fast_cut, "_concat", side_effect=fake_concat),
            patch.object(fast_cut, "shot_brightness", side_effect=lambda *_a: next(lumas)),
        ):
            result = fast_cut._compose(keys, windows, "GTA", 12.0, None)
        shots = len(fast_cut.cut_points(12.0)) - 1
        self.assertEqual(len(rendered), shots + 1, rendered)
        self.assertNotEqual(rendered[0][0], rendered[1][0], "the redraw used another clip")
        self.assertIn(f"{shots} shots", result.attribution)

    def test_gives_up_after_two_redraws(self):
        import config.paths as paths
        from assets import fast_cut

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        count = {"n": 0}

        def fake_render(clip, start, length, path):
            count["n"] += 1
            Path(path).write_bytes(b"x")

        keys, windows = fast_cut.expand_pool(["a.mp4", "b.mp4", "c.mp4"], {})
        with (
            patch.object(paths, "DATA_DIR", tmp),
            patch.object(fast_cut, "_render_shot", side_effect=fake_render),
            patch.object(
                fast_cut, "_concat", side_effect=lambda _l, o, _d: Path(o).write_bytes(b"")
            ),
            patch.object(fast_cut, "shot_brightness", return_value=1.0),
        ):
            fast_cut._compose(keys, windows, "GTA", 2.0, None)
        self.assertEqual(count["n"], 3)


def _library(root: str, folders: dict[str, int]) -> None:
    for rel, n in folders.items():
        path = os.path.join(root, rel)
        os.makedirs(path, exist_ok=True)
        for i in range(n):
            Path(path, f"clip_{i}.mp4").write_bytes(b"x")


class TestNicheFolderAliases(unittest.TestCase):
    """#786: NFL/NBA/soccer topics pick the Madden/2K/FC footage the library already has."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        _library(
            self.root,
            {
                "gaming/sports/Madden 26": 3,
                "gaming/sports/2k26": 3,
                "gaming/sports/EA Sports FC": 3,
                "gaming/sports/UFC 5": 3,
                "gaming/open world/GTA V": 3,
            },
        )

    def _pick(self, topic: str) -> str:
        from assets import local_provider

        with (
            patch.object(local_provider, "BASE_VIDEO_DIR", self.root),
            patch.object(local_provider, "_ai_choose_folder", return_value=None),
            patch("assets.background_query.resolve_background_query", return_value=topic),
            patch.object(local_provider.random, "choice", side_effect=AssertionError("random")),
        ):
            clips = local_provider.LocalAssetProvider().candidate_clips(topic, "sports", "tapin")
        return os.path.basename(os.path.dirname(clips[0]))

    def test_nfl_topic_uses_madden(self):
        self.assertEqual(self._pick("NFL draft night shock trade"), "Madden 26")

    def test_nba_topic_uses_2k(self):
        self.assertEqual(self._pick("NBA trade deadline winners"), "2k26")

    def test_soccer_topic_uses_fc(self):
        self.assertEqual(self._pick("Premier League title race goes to the wire"), "EA Sports FC")

    def test_folder_name_still_wins(self):
        """Guards existing behaviour: a topic naming the folder picks it."""
        self.assertEqual(self._pick("UFC 5 patch notes"), "UFC 5")


class TestFootageImport(unittest.TestCase):
    """`ops footage-add`: a downloaded gameplay file lands in its game folder with its licence."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.src = os.path.join(self.root, "download.mp4")
        Path(self.src).write_bytes(b"video")
        self.lib = os.path.join(self.root, "lib")
        _library(self.lib, {"gaming/sports/Madden 26": 2})

    def _add(self, **kw):
        from assets import clip_ingest

        def fake_remux(src, dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(src, dest)

        with (
            patch.object(clip_ingest, "_remux_muted_h264", side_effect=fake_remux),
            patch.object(clip_ingest, "_record_index") as record,
        ):
            row = clip_ingest.add_footage(self.src, library_root=self.lib, **kw)
        return row, record

    def test_new_game_gets_a_folder_and_a_licence_file(self):
        row, record = self._add(
            game="Minecraft",
            source_url="https://example.org/parkour",
            licence="no-copyright gameplay (creator permits reuse)",
            apply=True,
        )
        self.assertEqual(row.status, "copied", row)
        folder = os.path.join(self.lib, "gaming", "other", "Minecraft")
        self.assertTrue(os.path.isfile(row.dest))
        self.assertEqual(os.path.dirname(row.dest), folder)
        with open(os.path.join(folder, "license.yaml"), encoding="utf-8") as f:
            lic = json.load(f)
        self.assertEqual(lic["license"], "no-copyright gameplay (creator permits reuse)")
        self.assertIn("https://example.org/parkour", lic["sources"])
        record.assert_called_once()

    def test_existing_game_folder_is_reused(self):
        row, _ = self._add(game="madden 26", source_url="u", licence="CC0", apply=True)
        self.assertEqual(os.path.basename(os.path.dirname(row.dest)), "Madden 26")

    def test_no_licence_no_import(self):
        row, _ = self._add(game="Roblox", source_url="u", licence="", apply=True)
        self.assertEqual(row.status, "failed")
        self.assertIn("licence", row.reason)
        self.assertFalse(os.path.exists(os.path.join(self.lib, "gaming", "other", "Roblox")))

    def test_dry_run_writes_nothing(self):
        row, record = self._add(game="Roblox", source_url="u", licence="CC0", apply=False)
        self.assertEqual(row.status, "matched")
        self.assertFalse(os.path.exists(os.path.join(self.lib, "gaming", "other", "Roblox")))
        record.assert_not_called()


class TestFootageCoverage(unittest.TestCase):
    def test_every_playlist_niche_says_what_footage_it_uses(self):
        from assets import local_provider
        from assets.clip_ingest import footage_coverage

        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        _library(root, {"gaming/sports/Madden 26": 11, "gaming/open world/GTA V": 25})
        with patch.object(local_provider, "BASE_VIDEO_DIR", root):
            rows = {r["niche"]: r for r in footage_coverage("tapin", library_root=root)}
        self.assertEqual(rows["NFL"]["folder"], "Madden 26")
        self.assertEqual(rows["NFL"]["clips"], 11)
        self.assertEqual(rows["GTA"]["clips"], 25)
        self.assertEqual(rows["Minecraft"]["clips"], 0)
        self.assertEqual(rows["Minecraft"]["folder"], "")
        self.assertTrue(rows["Gaming"].get("umbrella"), "Gaming is a parent, not a gap")
        self.assertFalse(rows["Minecraft"].get("umbrella"))


def _record(rid: int, vid: str, hours_ago: float, now: datetime):
    from storage.repositories.publish_log import PublishLogRecord

    return PublishLogRecord(
        id=rid,
        content_run_id=rid,
        channel_id="tapin",
        youtube_video_id=vid,
        status="uploaded",
        published_at=now - timedelta(hours=hours_ago),
    )


class _FakeVideos:
    def __init__(self, items):
        self.items = items
        self.calls: list[dict] = []

    def list(self, **kw):
        self.calls.append(kw)
        ids = kw["id"].split(",")
        items = [i for i in self.items if i["id"] in ids]

        class _Req:
            def execute(_self):
                return {"items": items}

        return _Req()


class _FakeService:
    def __init__(self, items):
        self._videos = _FakeVideos(items)

    def videos(self):
        return self._videos


class TestPostPublishCheck(unittest.TestCase):
    """#600: 48h after publish, look again - removed, blocked, age-restricted, made for kids."""

    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    def test_only_videos_past_48h_and_unchecked_are_due(self):
        from core.post_publish_check import due

        rows = [
            _record(1, "old", 50, self.now),
            _record(2, "fresh", 10, self.now),
            _record(3, "done", 90, self.now),
            _record(4, "", 90, self.now),
        ]
        picked = due(rows, now=self.now, checked={"done"})
        self.assertEqual([r.youtube_video_id for r in picked], ["old"])

    def test_assess_flags(self):
        from core.post_publish_check import assess

        self.assertEqual(assess(None), ["removed from YouTube"])
        ok = {"status": {"uploadStatus": "processed", "privacyStatus": "public"}}
        self.assertEqual(assess(ok), [])
        flags = assess(
            {
                "status": {
                    "uploadStatus": "rejected",
                    "rejectionReason": "copyright",
                    "privacyStatus": "public",
                    "madeForKids": True,
                },
                "contentDetails": {
                    "regionRestriction": {"blocked": ["DE", "FR"]},
                    "contentRating": {"ytRating": "ytAgeRestricted"},
                },
            }
        )
        text = " | ".join(flags)
        for needle in ("rejected: copyright", "blocked in 2", "age-restricted", "made for kids"):
            self.assertIn(needle, text)

    def test_run_checks_one_call_records_and_never_rechecks(self):
        from core.post_publish_check import run_post_publish_checks

        rows = [_record(1, "v1", 50, self.now), _record(2, "v2", 60, self.now)]
        service = _FakeService(
            [
                {"id": "v1", "status": {"uploadStatus": "processed", "privacyStatus": "public"}},
            ]
        )
        store = os.path.join(tempfile.mkdtemp(), "ppc.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(store), True)
        report = run_post_publish_checks(
            "tapin", service=service, rows=rows, now=self.now, store_path=store
        )
        self.assertEqual(len(service._videos.calls), 1)
        self.assertEqual(report["checked"], 2)
        self.assertEqual(report["flagged"], {"v2": ["removed from YouTube"]})
        again = run_post_publish_checks(
            "tapin", service=service, rows=rows, now=self.now, store_path=store
        )
        self.assertEqual(again["checked"], 0)
        self.assertEqual(len(service._videos.calls), 1)

    def test_overnight_reports_the_check(self):
        from core import overnight

        with (
            patch.dict(os.environ, {"POST_PUBLISH_CHECK": "true"}),
            patch(
                "core.post_publish_check.post_publish_line",
                return_value="48h check: 1 video flagged",
            ),
        ):
            result = overnight.OvernightResult(channel_id="tapin")
            overnight._post_publish(result)
        self.assertEqual(result.post_publish_line, "48h check: 1 video flagged")
        result.requested = 0
        self.assertIn("48h check: 1 video flagged", overnight.render_overnight(result))

    def test_suite_pins_it_off(self):
        """No test may reach YouTube through the nightly hook."""
        from core.post_publish_check import post_publish_line

        self.assertEqual(os.environ.get("POST_PUBLISH_CHECK"), "false")
        self.assertEqual(post_publish_line("tapin"), "")


def _timed(text: str) -> list[dict]:
    out, t = [], 0.0
    for word in text.split():
        out.append({"word": word, "start": round(t, 2), "end": round(t + 0.3, 2)})
        t += 0.35
    return out


class TestCaptionFit(unittest.TestCase):
    """Found in the wave 23 preview: at the restored 90 px (#783), 4-word karaoke lines ran off
    both edges of the frame - "ach-it was social engineeri", "aunts Rockstar because they" -
    because WrapStyle 2 never wraps. Hidden while #783 burned captions at a tenth of the size."""

    def test_no_karaoke_line_is_wider_than_the_frame(self):
        import re

        from video.caption_timing import build_ass_karaoke

        words = _timed(
            "The leaker literally taunts Rockstar because they know the breach was social "
            "engineering against an employee's Slack account. Rockstar's security flaw."
        )
        ass = build_ass_karaoke(words, max_words=4, size=90)
        lines = [
            re.sub(r"\{[^}]*\}", "", row.split(",,0,0,0,,", 1)[1])
            for row in ass.splitlines()
            if row.startswith("Dialogue:")
        ]
        self.assertTrue(lines)
        for line in lines:
            if " " in line:
                self.assertLessEqual(len(line), 19, lines)
        spoken = " ".join(lines).split()
        self.assertEqual(spoken, [w["word"] for w in words], "no word lost or reordered")

    def test_smaller_font_fits_more(self):
        from video.caption_timing import karaoke_max_chars

        self.assertEqual(karaoke_max_chars(90), 19)
        self.assertGreater(karaoke_max_chars(60), karaoke_max_chars(90))


class TestDisclosureClearsCaptions(unittest.TestCase):
    """Found in the wave 23 preview: the AI disclosure (bottom, MarginV 280) was drawn over the
    opening caption (bottom, MarginV 260) for the first 3 s. It moves to the top."""

    def test_disclosure_is_top_centre(self):
        from video.policy_overlays import build_policy_overlays_ass

        with patch(
            "core.description_extras.ai_disclosure_line",
            return_value="Made with AI-assisted narration and editing.",
        ):
            ass = build_policy_overlays_ass("tapin", None, duration=10.0)
        style = next(ln for ln in ass.splitlines() if ln.startswith("Style: Disclosure,"))
        fields = style.split(",")
        self.assertEqual(fields[18], "8", style)


class TestOpsVerbs(unittest.TestCase):
    def test_new_verbs_are_registered_and_documented(self):
        from scripts.ops import COMMANDS

        doc = (ROOT / "docs" / "ops_commands.md").read_text(encoding="utf-8")
        for verb in ("footage", "footage-add", "post-publish-check"):
            self.assertIn(verb, COMMANDS)
            self.assertIn(f"`{verb}`", doc)

    def test_env_example_documents_the_new_keys(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        for key in ("BACKGROUND_CROP_BOTTOM", "POST_PUBLISH_CHECK"):
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main()
