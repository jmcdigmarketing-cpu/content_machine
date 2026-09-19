"""Wave 22: fast-cut backgrounds, franchise playlists, the YouTube timeout.

Operator, 2026-09-18, rejecting drafts 88-90: "the clips need to be much shorter, idk like the
other videos do. more clips per, less time in each." A hybrid background was ONE local clip then
ONE stock clip for the whole video - a 55 s Short held each shot for ~25 s. Call: cut every
~2-3 s. Each test here failed on unmodified 813a826 unless its docstring says it guards
existing behaviour.
"""

from __future__ import annotations

import os
import random
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


class TestCutPoints(unittest.TestCase):
    """The 2-3 s pacing this wave shipped was reversed by the operator on 2026-09-19 (#792,
    planning_log 2026-09-19 wave 24): "between the 3-8s range ... dont cut consistiently".
    These guards moved with the decision; the one thing wave 22 settled that still holds is
    that the background cuts at all, on phrase ends, instead of two shots per video."""

    def test_the_background_is_many_shots_not_two(self):
        from assets.fast_cut import cut_points

        bounds = cut_points(55.0)
        self.assertEqual(bounds[0], 0.0)
        self.assertEqual(bounds[-1], 55.0)
        shots = [b - a for a, b in pairwise(bounds)]
        self.assertGreaterEqual(len(shots), 6, shots)
        for shot in shots:
            self.assertGreaterEqual(shot, 3.0 - 1e-6, shots)
            self.assertLessEqual(shot, 8.0 + 1e-6, shots)

    def test_cuts_land_on_phrase_ends_when_timings_exist(self):
        from assets.fast_cut import cut_points

        text = ("Rockstar sells the map, not the story. " * 12).strip()
        words = _words(text)
        duration = words[-1]["end"] + 0.2
        bounds = cut_points(duration, words)
        phrase_ends = {w["end"] for w in words if w["word"][-1:] in ",.!?;:"}
        inner = bounds[1:-1]
        on_phrase = sum(1 for b in inner if b in phrase_ends)
        self.assertGreaterEqual(on_phrase, len(inner) * 0.6, (inner, sorted(phrase_ends)))

    def test_a_short_video_is_never_one_long_shot(self):
        from assets.fast_cut import cut_points

        self.assertGreaterEqual(len(cut_points(12.0)) - 1, 2)

    def test_the_pace_is_tunable(self):
        from assets.fast_cut import cut_points

        with patch.dict(os.environ, {"BACKGROUND_CUT_MIN": "6", "BACKGROUND_CUT_MAX": "10"}):
            shots = len(cut_points(60.0)) - 1
        self.assertLessEqual(shots, 10)


class TestPlanShots(unittest.TestCase):
    CLIPS = ("gta/a.mp4", "gta/b.mp4", "gta/c.mp4", "gta/d.mp4")

    def test_no_clip_plays_twice_in_a_row_and_every_in_point_fits(self):
        from assets.fast_cut import cut_points, plan_shots

        bounds = cut_points(55.0)
        durations = dict.fromkeys(self.CLIPS, 40.0)
        shots = plan_shots(bounds, list(self.CLIPS), durations=durations, rng=random.Random(7))
        self.assertEqual(len(shots), len(bounds) - 1)
        for (path, _start, _length), (nxt, _s, _l) in pairwise(shots):
            self.assertNotEqual(path, nxt)
        for path, start, length in shots:
            self.assertGreaterEqual(start, 0.0)
            self.assertLessEqual(start + length, durations[path] + 1e-6)

    def test_every_clip_in_the_pool_is_used(self):
        from assets.fast_cut import cut_points, plan_shots

        shots = plan_shots(cut_points(55.0), list(self.CLIPS), rng=random.Random(1))
        self.assertEqual({p for p, _s, _l in shots}, set(self.CLIPS))


class TestFastCutCommands(unittest.TestCase):
    def test_a_shot_seeks_trims_and_fills_the_frame(self):
        from assets.fast_cut import build_shot_command

        argv = build_shot_command("gta/a.mp4", 12.5, 2.4, "out.mp4")
        joined = " ".join(argv)
        self.assertIn("-ss 12.500", joined)
        self.assertIn("-t 2.400", joined)
        self.assertIn("1080:1920", joined)
        self.assertIn("-an", argv)

    def test_the_join_is_a_stream_copy(self):
        from assets.fast_cut import build_concat_command

        argv = build_concat_command("list.txt", "bg.mp4", 55.0)
        self.assertIn("concat", argv)
        self.assertEqual(argv[argv.index("-c") + 1], "copy")


class TestFastCutIsWiredIn(unittest.TestCase):
    def test_default_on_and_switchable(self):
        from assets.fast_cut import fast_cut_enabled

        with patch.dict(os.environ, {"BACKGROUND_FAST_CUT": ""}):
            self.assertTrue(fast_cut_enabled())
        with patch.dict(os.environ, {"BACKGROUND_FAST_CUT": "false"}):
            self.assertFalse(fast_cut_enabled())

    def test_render_tries_it_before_the_two_shot_hybrid(self):
        text = (ROOT / "video" / "render_video.py").read_text(encoding="utf-8")
        self.assertIn("try_fast_cut_background(", text)
        self.assertLess(
            text.index("try_fast_cut_background("), text.index("get_background_asset(topic")
        )

    def test_too_few_clips_falls_back(self):
        """A folder with under three clips cannot cut fast without repeating; keep the old path."""
        from assets import fast_cut

        with patch.object(fast_cut, "_clip_pool", return_value=["only.mp4"]):
            self.assertIsNone(fast_cut.try_fast_cut_background("GTA 6", "tapin", duration=55.0))

    def test_the_local_provider_exposes_its_folder(self):
        from assets.local_provider import LocalAssetProvider

        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp, "gaming", "open world", "GTA V")
            game.mkdir(parents=True)
            for name in ("a.mp4", "b.mp4", "c.mp4", "notes.txt"):
                (game / name).write_bytes(b"x")
            with patch("assets.local_provider.BASE_VIDEO_DIR", tmp):
                clips = LocalAssetProvider().candidate_clips("GTA 6 heists", "gaming")
        self.assertEqual(sorted(os.path.basename(c) for c in clips), ["a.mp4", "b.mp4", "c.mp4"])


class TestRenderLookDefects(unittest.TestCase):
    """Found rendering the first fast-cut preview (2026-09-19), confirmed on run 77 - the
    video live on YouTube - and run 79."""

    def test_the_vignette_is_centred(self):
        """#784: `vignette=PI/4:0.280` - ffmpeg's second positional is x0, the centre's x
        position, so the vignette sat 0.28 px from the left edge and blacked out the right
        third of every frame since 464c71b (2026-09-07)."""
        from video.render_video import look_filter_fragment

        with (
            patch("core.design_tokens.look_grain", return_value=0),
            patch("core.design_tokens.look_vignette", return_value=0.28),
        ):
            fragment = look_filter_fragment("tapin")
        self.assertIn("vignette=angle=", fragment)
        self.assertNotIn(":0.280", fragment)
        self.assertNotIn("x0=", fragment)

    def test_karaoke_captions_keep_their_own_size(self):
        """#783: force_style FontSize=18 was applied to the karaoke ASS too. libass reads 18
        against the SRT default 288-px canvas, but the ASS declares 1920 - so every
        word-timed render (run 77 included) burned captions at a tenth of the size."""
        from video.render_video import build_render_ffmpeg_command

        style = (
            "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00111111&,"
            "BorderStyle=3,Outline=2,Shadow=0,Alignment=2,MarginV=72"
        )
        ass = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="a.mp3",
            output_path="o.mp4",
            subtitle_path="captions.ass",
            duration=55.0,
            caption_force_style=style,
        )
        srt = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="a.mp3",
            output_path="o.mp4",
            subtitle_path="captions.srt",
            duration=55.0,
            caption_force_style=style,
        )
        ass_cmd, srt_cmd = " ".join(ass), " ".join(srt)
        # The skin's box/outline still reach an ASS burn; size, position and font do not.
        for gone in ("FontSize", "MarginV", "Alignment", "FontName", "PrimaryColour"):
            self.assertNotIn(gone, ass_cmd)
        self.assertIn("BorderStyle=3", ass_cmd)
        self.assertIn("FontSize=18", srt_cmd)


class TestYouTubeTimeoutRetriesOnce(unittest.TestCase):
    """#781: every run this week lost `youtube` + `youtube_comments` to ONE read timeout;
    the same search answered in 0.6 s in isolation (2026-09-18)."""

    def setUp(self):
        from apis import youtube_api

        youtube_api.reset_api_unreachable()
        self.addCleanup(youtube_api.reset_api_unreachable)

    def _client(self, outcomes):
        from unittest.mock import MagicMock

        client = MagicMock()
        client.search.return_value.list.return_value.execute.side_effect = outcomes
        return client

    def test_one_blip_is_retried_on_a_fresh_client_and_the_latch_stays_off(self):
        from apis import youtube_api

        stale = self._client([TimeoutError("The read operation timed out")])
        fresh = self._client([{"items": []}])
        with patch.object(youtube_api, "_fresh_youtube_client", return_value=fresh):
            result = youtube_api._search_videos(stale, "GTA 6")
        self.assertEqual(result, {"items": []})
        self.assertEqual(youtube_api.api_unreachable(), "")

    def test_two_timeouts_still_arm_the_latch(self):
        from apis import youtube_api

        stale = self._client([TimeoutError("The read operation timed out")])
        fresh = self._client([TimeoutError("The read operation timed out")])
        with patch.object(youtube_api, "_fresh_youtube_client", return_value=fresh):
            with self.assertRaises(TimeoutError):
                youtube_api._search_videos(stale, "GTA 6")
        self.assertIn("timed out", youtube_api.api_unreachable())

    def test_a_quota_error_is_not_retried(self):
        """Guard: only a timeout earns the retry; quota/auth keep their own handling."""
        from apis import youtube_api

        stale = self._client([RuntimeError("quotaExceeded")])
        with patch.object(youtube_api, "_fresh_youtube_client") as fresh:
            with self.assertRaises(RuntimeError):
                youtube_api._search_videos(stale, "GTA 6")
        fresh.assert_not_called()
        self.assertEqual(youtube_api.api_unreachable(), "")


class TestFranchisePlaylists(unittest.TestCase):
    """#601, operator 2026-09-18: football, NFL, basketball, gaming, Marvel Rivals, GTA,
    UFC/MMA, AI development, Twitch, plus the two most popular related niches (Google Trends,
    3 months: Minecraft 76, Roblox 72 among gaming; see planning_log)."""

    def _for(self, title, topic="", tags=()):
        from core.playlists import playlists_for

        return playlists_for("tapin", title, topic=topic, tags=list(tags))

    def test_the_most_specific_playlist_wins_and_games_join_the_umbrella(self):
        self.assertEqual(
            self._for("xQc co-owns NoPixel but can't control GTA RP invites"), ["GTA", "Gaming"]
        )
        self.assertEqual(
            self._for("Cyclops joins Marvel Rivals season 5"), ["Marvel Rivals", "Gaming"]
        )
        self.assertEqual(self._for("Minecraft's biggest update yet"), ["Minecraft", "Gaming"])

    def test_sports_land_in_their_own_league(self):
        self.assertEqual(
            self._for("Khamzat Chimaev eyes the UFC middleweight title"), ["UFC / MMA"]
        )
        self.assertEqual(self._for("Chiefs quarterback carves up the NFL"), ["NFL"])
        self.assertEqual(self._for("Arsenal top the Premier League table"), ["Football"])
        self.assertEqual(
            self._for("LeBron free agency: the one NBA team that fits"), ["Basketball"]
        )

    def test_word_boundaries_hold(self):
        self.assertEqual(self._for("OpenAI ships a new coding model"), ["AI Development"])
        self.assertEqual(self._for("He said the vegetables were fine"), [])

    def test_nothing_is_added_without_the_manage_scope(self):
        from unittest.mock import MagicMock

        from core import playlists

        service = MagicMock()
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youtube.oauth.token_has_scope", return_value=False),
        ):
            note = playlists.add_to_playlists(
                service,
                "tapin",
                "vid1",
                title="GTA 6 trailer",
                store_path=os.path.join(tmp, "p.json"),
            )
        self.assertIn("youtube.oauth_setup", note)
        service.playlistItems.assert_not_called()

    def test_adding_is_idempotent(self):
        import json
        from unittest.mock import MagicMock

        from core import playlists

        service = MagicMock()
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youtube.oauth.token_has_scope", return_value=True),
        ):
            store = os.path.join(tmp, "p.json")
            with open(store, "w", encoding="utf-8") as f:
                json.dump({"ids": {"GTA": "PL1", "Gaming": "PL2"}}, f)
            playlists.add_to_playlists(
                service, "tapin", "vid1", title="GTA 6 trailer", store_path=store
            )
            playlists.add_to_playlists(
                service, "tapin", "vid1", title="GTA 6 trailer", store_path=store
            )
        inserted = [
            c.kwargs["body"]["snippet"]["playlistId"]
            for c in service.playlistItems().insert.call_args_list
        ]
        self.assertEqual(sorted(inserted), ["PL1", "PL2"])

    def test_sync_creates_only_the_missing(self):
        import json
        from unittest.mock import MagicMock

        from core import playlists

        service = MagicMock()
        service.playlists().insert().execute.return_value = {"id": "PLnew"}
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "p.json")
            with open(store, "w", encoding="utf-8") as f:
                json.dump({"ids": {"GTA": "PL1"}}, f)
            created = playlists.sync_playlists(service, "tapin", store_path=store)
            with open(store, encoding="utf-8") as f:
                ids = json.load(f)["ids"]
        self.assertNotIn("GTA", created)
        self.assertIn("Minecraft", created)
        self.assertEqual(ids["GTA"], "PL1")

    def test_the_scope_the_upload_path_and_ops_are_wired(self):
        from scripts import ops
        from youtube.constants import OAUTH_SCOPES_FULL

        self.assertIn("https://www.googleapis.com/auth/youtube", OAUTH_SCOPES_FULL)
        publisher = (ROOT / "publishing" / "youtube_publisher.py").read_text(encoding="utf-8")
        self.assertIn("add_to_playlists(", publisher)
        self.assertIn("playlists", ops.COMMANDS)


class TestPreviewRender(unittest.TestCase):
    """The operator judges pace by watching, before a paid voice renders a new Short."""

    def test_the_preview_renders_a_copy_never_the_original(self):
        import json

        from assets import fast_cut

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp, "short.mp3")
            audio.write_bytes(b"mp3")
            words = [{"word": "Rockstar", "start": 0.0, "end": 0.4}]
            Path(str(audio) + ".words.json").write_text(json.dumps(words), encoding="utf-8")
            out_dir = Path(tmp, "preview")
            calls = []

            def fake_render(mp3, topic, out, script, channel_id=None, **_kw):
                # The real function joins a bare filename under <audio dir>/../video and
                # returns that path; the first preview passed a full path and it nested.
                calls.append((mp3, topic, out, script))
                video_dir = Path(mp3).resolve().parent.parent / "video"
                video_dir.mkdir(parents=True, exist_ok=True)
                target = video_dir / out
                target.write_bytes(b"mp4")
                return str(target), "bg"

            with patch("video.render_video.render_vertical_video", side_effect=fake_render):
                path = fast_cut.render_preview(str(audio), "GTA 6", "tapin", out_dir=str(out_dir))
            self.assertEqual(len(calls), 1)
            mp3, topic, out, script = calls[0]
            self.assertNotEqual(os.path.abspath(mp3), os.path.abspath(audio))
            self.assertTrue(str(mp3).startswith(str(out_dir)))
            self.assertEqual(script, "Rockstar")
            self.assertEqual(audio.read_bytes(), b"mp3")
            self.assertEqual(os.path.basename(out), out, "render wants a bare filename")
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(os.path.abspath(path).startswith(os.path.abspath(out_dir)), path)

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("preview-render", ops.COMMANDS)


if __name__ == "__main__":
    unittest.main()
