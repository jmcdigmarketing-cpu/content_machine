"""#411: a per-channel music bed from the operator's own tracks, ducked under the voice.

The render already mixed a looped third input under the voice (`video/render_video.py`),
at a fixed 0.2 gain with no ducking, but the only source was MusicGen (torch, off), so
no channel ever had music - "silence under VO is part of why the result looks thin".
A channel's `music` block now names a folder of royalty-free tracks
(`assets/music/<channel>/` by default; `*.mp3` is gitignored). A render picks one, never
the previous run's, and a sidechain compressor dips it under speech. No tracks -> the
VO-only render, byte-identical.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.channels import ChannelProfile


class LibraryCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.folder = root / "music"
        self.folder.mkdir()
        self.state = root / "music_last.json"
        self.music = {"enabled": True, "folder": str(self.folder), "volume": 0.18}
        profile = ChannelProfile(id="tapin", music=self.music)
        self._patches = [
            patch("config.channels.get_channel_profile", return_value=profile),
            patch("core.music.MUSIC_STATE_FILE", self.state),
            patch.dict(os.environ, {"MUSIC_PROVIDER": ""}),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def add(self, *names: str) -> None:
        for name in names:
            (self.folder / name).write_bytes(b"x")


class TrackPickTests(LibraryCase):
    def test_only_audio_files_are_tracks(self):
        from core.music import library_tracks

        self.add("b.mp3", "a.m4a", "notes.txt", "c.wav")
        self.assertEqual([p.name for p in library_tracks("tapin")], ["a.m4a", "b.mp3", "c.wav"])

    def test_the_previous_track_is_never_picked_twice_in_a_row(self):
        from core.music import pick_track

        self.add("a.mp3", "b.mp3", "c.mp3")
        last = None
        for _ in range(12):
            track = pick_track("tapin")
            self.assertIsNotNone(track)
            self.assertNotEqual(track, last)
            last = track

    def test_one_track_is_reused(self):
        from core.music import pick_track

        self.add("only.mp3")
        self.assertEqual(pick_track("tapin").name, "only.mp3")
        self.assertEqual(pick_track("tapin").name, "only.mp3")

    def test_reliability_shows_it(self):
        from core.reliability import render

        text = render({"music": ["Music bed: none - drop royalty-free tracks in x (tapin)"]})
        self.assertIn("drop royalty-free tracks", text)

    def test_the_status_line_says_what_to_do(self):
        from core.music import library_status_line

        self.assertIn("drop royalty-free tracks", library_status_line("tapin"))
        self.add("a.mp3")
        self.assertIn("1 track", library_status_line("tapin"))


class ResolveTests(LibraryCase):
    def _resolve(self):
        from video.render_video import _resolve_music_bed

        return _resolve_music_bed(12.0, lambda *_: None, channel_id="tapin")

    def test_a_channel_with_tracks_gets_a_bed(self):
        self.add("a.mp3")
        self.assertTrue(str(self._resolve()).endswith("a.mp3"))

    def test_an_empty_folder_renders_vo_only(self):
        self.assertIsNone(self._resolve())

    def test_disabled_renders_vo_only(self):
        self.add("a.mp3")
        self.music["enabled"] = False
        self.assertIsNone(self._resolve())

    def test_music_provider_none_turns_it_off(self):
        self.add("a.mp3")
        with patch.dict(os.environ, {"MUSIC_PROVIDER": "none"}):
            self.assertIsNone(self._resolve())


class CommandTests(unittest.TestCase):
    def _cmd(self, **kw):
        from video.render_video import build_render_ffmpeg_command

        return build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="vo.mp3",
            output_path="out.mp4",
            subtitle_path="s.srt",
            duration=10.0,
            **kw,
        )

    def test_the_bed_ducks_under_speech(self):
        cmd = self._cmd(music_path="bed.mp3", music_volume=0.18)
        fc = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("[1:a]asplit=2[vo][sc]", fc)
        self.assertIn("[2:a]volume=0.18[bed]", fc)
        self.assertIn("[bed][sc]sidechaincompress=", fc)
        self.assertIn("[vo][duck]amix=inputs=2:duration=first:normalize=0[aout]", fc)

    def test_no_bed_is_byte_identical(self):
        self.assertEqual(self._cmd(), self._cmd(music_path=None, music_volume=0.18))


class ChannelConfigTests(unittest.TestCase):
    def test_both_channels_have_a_valid_music_block(self):
        from config.channels import get_channel_profile

        for channel in ("tapin", "moneywise"):
            with self.subTest(channel=channel):
                music = get_channel_profile(channel).music
                self.assertTrue(music.get("enabled"))
                self.assertTrue(0.0 < float(music.get("volume", 0)) <= 0.5)

    def test_a_loud_bed_is_rejected(self):
        from config.validate_channels import validate_channel

        errors, _ = validate_channel("tapin", {"music": {"enabled": True, "volume": 0.9}})
        self.assertTrue(any("music.volume" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
