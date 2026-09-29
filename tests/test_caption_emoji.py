"""#504: emoji in a caption render in an emoji font instead of vanishing.

libass draws each caption in its style's font (Arial, Impact ...), which has no emoji
glyphs, so an emoji the script carried simply disappeared from the burned captions.
Operator's choice (wave 47): render them. Each emoji run is wrapped in an ASS font switch
- `{\\fnSegoe UI Emoji}...{\\fn<the style's font>}` - so libass draws it from the emoji
font (Segoe UI Emoji ships with Windows 10/11; libass draws its monochrome outlines;
`CAPTION_EMOJI_FONT` names another). Word mode burns an .srt, which cannot switch fonts,
so a word-mode render with emoji takes the .ass path (#503 did the same for entrances).
Text with no emoji is byte-identical.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from tests.test_caption_voice_colour import PAIRED_SHA, SINGLE_VOICE_SHA, WORDS

FIRE = "\U0001f525"
FAMILY = "\U0001f468‍\U0001f469‍\U0001f467"  # one ZWJ sequence


def _words(text):
    return [
        {"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate(text.split())
    ]


class WrapTests(unittest.TestCase):
    def test_a_run_is_switched_and_restored(self):
        from video.caption_emoji import wrap_emoji

        with patch.dict(os.environ, {"CAPTION_EMOJI_FONT": ""}):
            got = wrap_emoji(f"tonight{FIRE}{FIRE}!", "Impact")
        self.assertEqual(got, f"tonight{{\\fnSegoe UI Emoji}}{FIRE}{FIRE}{{\\fnImpact}}!")

    def test_a_zwj_sequence_is_one_run(self):
        from video.caption_emoji import wrap_emoji

        got = wrap_emoji(f"a {FAMILY} b", "Arial")
        self.assertEqual(got.count("\\fn"), 2)
        self.assertIn(FAMILY, got)

    def test_plain_text_is_untouched(self):
        from video.caption_emoji import has_emoji, wrap_emoji

        text = "Topuria -> Holloway (c) 2026 - 100% sure."
        self.assertEqual(wrap_emoji(text, "Arial"), text)
        self.assertFalse(has_emoji(_words(text)))

    def test_the_font_can_be_named(self):
        from video.caption_emoji import wrap_emoji

        with patch.dict(os.environ, {"CAPTION_EMOJI_FONT": "Noto Emoji"}):
            self.assertIn("{\\fnNoto Emoji}", wrap_emoji(FIRE, "Arial"))


class KaraokeTests(unittest.TestCase):
    def test_no_emoji_is_byte_identical(self):
        from video.caption_timing import build_ass_karaoke

        self.assertEqual(
            hashlib.sha256(build_ass_karaoke(WORDS).encode()).hexdigest(), SINGLE_VOICE_SHA
        )
        paired = build_ass_karaoke(WORDS, title_font="Impact", body_font="Arial")
        self.assertEqual(hashlib.sha256(paired.encode()).hexdigest(), PAIRED_SHA)

    def test_each_line_restores_its_own_style_font(self):
        from video.caption_timing import build_ass_karaoke

        words = _words(f"Tonight {FIRE} . Topuria defends {FIRE} the belt in Vegas.")
        ass = build_ass_karaoke(words, title_font="Impact", body_font="Arial", max_words=3)
        dialogue = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
        self.assertIn("{\\fnImpact}", dialogue[0])  # the title line
        self.assertTrue(any("{\\fnArial}" in ln for ln in dialogue[1:]))  # body lines
        self.assertIn(f"{{\\fnSegoe UI Emoji}}{FIRE}", ass)

    def test_the_karaoke_timing_is_kept(self):
        from video.caption_timing import build_ass_karaoke

        ass = build_ass_karaoke(_words(f"go {FIRE} now"))
        self.assertEqual(ass.count("\\k"), 3)


class WordModeTests(unittest.TestCase):
    def _render(self, text):
        from video import subtitles

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(subtitles, "_caption_skin", return_value={"mode": "word"}),
            patch.dict(os.environ, {"CAPTION_STYLE": ""}),
        ):
            path = subtitles.generate_subtitle_file(
                text, 5.0, channel_id="moneywise", output_path=os.path.join(tmp, "s.srt"),
                words=_words(text),
            )  # fmt: skip
            with open(path, encoding="utf-8") as f:
                return os.path.splitext(path)[1], f.read()

    def test_emoji_take_the_ass_path(self):
        ext, body = self._render(f"Rates held {FIRE} again")
        self.assertEqual(ext, ".ass")
        self.assertIn(f"{{\\fnSegoe UI Emoji}}{FIRE}", body)

    def test_without_emoji_it_stays_srt(self):
        ext, _body = self._render("Rates held again")
        self.assertEqual(ext, ".srt")


if __name__ == "__main__":
    unittest.main()
