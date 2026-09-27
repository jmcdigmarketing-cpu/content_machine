"""#506: in a two-voice render, the second voice's words light up in their own colour.

Wave 39 gave debate and quotes renders a second voice, but the captions could not tell
the viewer who was speaking: `core/tts._write_concat_word_sidecar` merged every
segment's word timings and dropped which voice spoke them, and
`video/caption_timing.build_ass_karaoke` had one highlight colour. The sidecar now
carries each word's role when a render has more than one, a caption line never mixes
voices, and a non-narrator line uses a `Voice2` style whose highlight is the channel's
`caption_skin.second_voice_color`. A single-voice render is byte-identical.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

TEXT = "The card is set. Topuria defends the belt tonight in Vegas."
WORDS = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate(TEXT.split())]
# build_ass_karaoke(WORDS) and (WORDS, title_font="Impact", body_font="Arial") on
# unmodified code, wave 43 (367428b).
SINGLE_VOICE_SHA = "d7c260404a41fec259f4fa0422f966955bbd792a8713744c20fea0d5e9049d99"
PAIRED_SHA = "e48879e4da510063a762764d89d016a13316e109324e9c163097f62a2c33e5b1"


def _two_voices() -> list[dict]:
    # "The card is set." by the narrator; the rest by the co-host.
    return [dict(w, role="narrator" if i < 4 else "cohost") for i, w in enumerate(WORDS)]


def _dialogue(ass: str) -> list[str]:
    return [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]


class KaraokeTests(unittest.TestCase):
    def test_a_single_voice_render_is_byte_identical(self):
        from video.caption_timing import build_ass_karaoke

        sha = hashlib.sha256(build_ass_karaoke(WORDS).encode()).hexdigest()
        self.assertEqual(sha, SINGLE_VOICE_SHA)
        paired = build_ass_karaoke(WORDS, title_font="Impact", body_font="Arial")
        self.assertEqual(hashlib.sha256(paired.encode()).hexdigest(), PAIRED_SHA)

    def test_narrator_roles_alone_change_nothing(self):
        from video.caption_timing import build_ass_karaoke

        tagged = [dict(w, role="narrator") for w in WORDS]
        self.assertEqual(build_ass_karaoke(tagged), build_ass_karaoke(WORDS))

    def test_the_second_voice_gets_its_own_style(self):
        from video.caption_timing import build_ass_karaoke

        ass = build_ass_karaoke(_two_voices(), voice2_primary="&H00F7C34F&")
        self.assertIn("Style: Voice2,", ass)
        self.assertIn("&H00F7C34F&", ass.split("Style: Voice2,")[1].splitlines()[0])
        styles = [ln.split(",")[3] for ln in _dialogue(ass)]
        self.assertIn("Voice2", styles)
        self.assertNotEqual(styles[0], "Voice2")

    def test_no_line_mixes_voices(self):
        from video.caption_timing import build_ass_karaoke

        ass = build_ass_karaoke(_two_voices(), max_words=6)
        for line in _dialogue(ass):
            text = line.split(",,0,0,0,,", 1)[1]
            if "Topuria" in text:
                self.assertNotIn("set.", text)
                self.assertIn(",Voice2,", line)


class SidecarTests(unittest.TestCase):
    def _merge(self, roles):
        from core import tts

        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i, chunk in enumerate((WORDS[:4], [dict(w) for w in WORDS[4:]])):
                seg = os.path.join(tmp, f"seg{i}.mp3")
                with open(seg + ".words.json", "w", encoding="utf-8") as f:
                    json.dump(chunk, f)
                paths.append(seg)
            dest = os.path.join(tmp, "out.mp3")
            with patch.object(tts, "segment_audio_duration", return_value=0.0):
                tts._write_concat_word_sidecar(paths, dest, roles=roles)
            with open(dest + ".words.json", encoding="utf-8") as f:
                return json.load(f)

    def test_two_voices_are_recorded_per_word(self):
        merged = self._merge(["narrator", "cohost"])
        self.assertEqual({w["role"] for w in merged[:4]}, {"narrator"})
        self.assertEqual({w["role"] for w in merged[4:]}, {"cohost"})

    def test_one_voice_writes_no_role(self):
        for roles in (None, ["narrator", "narrator"]):
            with self.subTest(roles=roles):
                self.assertTrue(all("role" not in w for w in self._merge(roles)))


class ChannelColourTests(unittest.TestCase):
    def test_the_channel_colour_reaches_the_captions(self):
        from video import subtitles

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(subtitles, "caption_style", return_value="karaoke"),
            patch.object(
                subtitles, "_caption_skin", return_value={"second_voice_color": "#4FC3F7"}
            ),
            patch("video.caption_place.choose_caption_anchor", return_value="bottom"),
        ):
            path = subtitles.generate_subtitle_file(
                TEXT,
                5.0,
                channel_id="tapin",
                output_path=os.path.join(tmp, "s.ass"),
                words=_two_voices(),
            )
            with open(path, encoding="utf-8") as f:
                ass = f.read()
        self.assertIn("&H00F7C34F&", ass)

    def test_both_channels_name_a_second_colour(self):
        from config.channels import get_channel_profile

        for channel in ("tapin", "moneywise"):
            with self.subTest(channel=channel):
                skin = get_channel_profile(channel).caption_skin or {}
                self.assertRegex(str(skin.get("second_voice_color") or ""), r"^#[0-9A-Fa-f]{6}$")


if __name__ == "__main__":
    unittest.main()
