"""#503: each caption line animates in - TapIn pops, MoneyWise fades (operator's pick).

Every caption line used to appear on its first frame at full size. `caption_skin.entrance`
(`pop` / `fade` / `slide` / `none`) now prefixes each line with an ASS override: pop
scales 85% -> 100% over 120 ms, fade fades in over 150 ms, slide rises 40 px over 150 ms.

Karaoke (TapIn) already burns an .ass. Word mode (MoneyWise) burned an .srt, and
FFmpeg's SRT decoder strips every override tag except `\\an`, so a fade there would
never render: word mode with an entrance now writes an .ass on the SRT canvas (libass's
384x288) with the same style `caption_force_style` applied, line-for-line the same cues,
and the .srt beside it. `none` leaves both builders byte-identical.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unittest
from unittest.mock import patch

from tests.test_caption_voice_colour import PAIRED_SHA, SINGLE_VOICE_SHA, TEXT, WORDS, _two_voices

POP = r"{\fscx85\fscy85\t(0,120,\fscx100\fscy100)}"
FADE = r"{\fad(150,0)}"


def _texts(ass: str) -> list[str]:
    return [ln.split(",,0,0,0,,", 1)[1] for ln in ass.splitlines() if ln.startswith("Dialogue:")]


class KaraokeEntranceTests(unittest.TestCase):
    def test_none_is_byte_identical(self):
        from video.caption_timing import build_ass_karaoke

        plain = build_ass_karaoke(WORDS, entrance="none")
        self.assertEqual(hashlib.sha256(plain.encode()).hexdigest(), SINGLE_VOICE_SHA)
        paired = build_ass_karaoke(WORDS, title_font="Impact", body_font="Arial", entrance="none")
        self.assertEqual(hashlib.sha256(paired.encode()).hexdigest(), PAIRED_SHA)

    def test_pop_leads_every_line_and_keeps_the_karaoke_timing(self):
        from video.caption_timing import build_ass_karaoke

        before = _texts(build_ass_karaoke(WORDS))
        after = _texts(build_ass_karaoke(WORDS, entrance="pop"))
        self.assertEqual(len(after), len(before))
        for old, new in zip(before, after, strict=True):
            self.assertEqual(new, POP + old)

    def test_fade(self):
        from video.caption_timing import build_ass_karaoke

        self.assertTrue(
            all(t.startswith(FADE) for t in _texts(build_ass_karaoke(WORDS, entrance="fade")))
        )

    def test_slide_rises_to_the_captions_own_position(self):
        from video.caption_timing import build_ass_karaoke

        bottom = _texts(build_ass_karaoke(WORDS, entrance="slide"))[0]
        self.assertTrue(bottom.startswith(r"{\move(540,1700,540,1660,0,150)}"), bottom)
        top = _texts(build_ass_karaoke(WORDS, entrance="slide", anchor="top"))[0]
        self.assertTrue(top.startswith(r"{\move(540,300,540,260,0,150)}"), top)

    def test_the_second_voice_enters_the_same_way(self):
        from video.caption_timing import build_ass_karaoke

        ass = build_ass_karaoke(_two_voices(), entrance="pop")
        voice2 = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:") and ",Voice2," in ln]
        self.assertTrue(voice2)
        self.assertTrue(all(POP in ln for ln in voice2))

    def test_an_unknown_entrance_is_none(self):
        from video.caption_timing import build_ass_karaoke

        self.assertEqual(build_ass_karaoke(WORDS, entrance="spin"), build_ass_karaoke(WORDS))


class WordModeTests(unittest.TestCase):
    STYLE = (
        "FontName=Arial,FontSize=18,PrimaryColour=&H00A9E7F7&,OutlineColour=&H0030241B&,"
        "BackColour=&H99000000&,BorderStyle=3,Outline=2,Shadow=0,Alignment=2,MarginV=72"
    )

    def test_the_cues_match_the_srt_line_for_line(self):
        from video.caption_timing import build_ass_from_words, build_srt_from_words

        srt = build_srt_from_words(WORDS, max_words=4)
        ass = build_ass_from_words(WORDS, max_words=4, style=self.STYLE, entrance="fade")
        srt_text = re.findall(r"\n\d\d:\d\d:\d\d,\d{3} --> [^\n]+\n([^\n]+)", "\n" + srt)
        self.assertEqual([t.removeprefix(FADE) for t in _texts(ass)], srt_text)
        self.assertTrue(all(t.startswith(FADE) for t in _texts(ass)))

    def test_it_carries_the_skin_on_the_srt_canvas(self):
        from video.caption_timing import build_ass_from_words

        ass = build_ass_from_words(WORDS, max_words=4, style=self.STYLE, entrance="fade")
        self.assertIn("PlayResX: 384", ass)
        self.assertIn("PlayResY: 288", ass)
        style = next(ln for ln in ass.splitlines() if ln.startswith("Style: Default,"))
        self.assertEqual(
            style,
            "Style: Default,Arial,18,&H00A9E7F7&,&Hffffff,&H0030241B&,&H99000000&,"
            "0,0,0,0,100,100,0,0,3,2,0,2,10,10,72,1",
        )


class ChannelTests(unittest.TestCase):
    def test_the_channels_carry_the_operators_pick(self):
        from config.channels import get_channel_profile

        self.assertEqual(get_channel_profile("tapin").caption_skin["entrance"], "pop")
        self.assertEqual(get_channel_profile("moneywise").caption_skin["entrance"], "fade")

    def test_validation(self):
        from config.validate_channels import validate_channel

        ok, _w = validate_channel("x", {"caption_skin": {"entrance": "slide"}})
        self.assertFalse([e for e in ok if "entrance" in e])
        bad, _w = validate_channel("x", {"caption_skin": {"entrance": "spin"}})
        self.assertTrue([e for e in bad if "entrance" in e])

    def _render(self, channel: str, skin: dict) -> tuple[str, str, bool]:
        from video import subtitles

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(subtitles, "_caption_skin", return_value=skin),
            patch.dict(os.environ, {"CAPTION_STYLE": ""}),
            patch("video.caption_place.choose_caption_anchor", return_value="bottom"),
        ):
            path = subtitles.generate_subtitle_file(
                TEXT, 5.0, channel_id=channel, output_path=os.path.join(tmp, "s.srt"), words=WORDS
            )
            with open(path, encoding="utf-8") as f:
                body = f.read()
            companion = os.path.exists(os.path.splitext(path)[0] + ".srt")
        return os.path.splitext(path)[1], body, companion

    def test_tapin_karaoke_pops(self):
        ext, body, _ = self._render("tapin", {"mode": "karaoke", "entrance": "pop"})
        self.assertEqual(ext, ".ass")
        self.assertIn(POP, body)

    def test_moneywise_word_mode_fades_in_an_ass(self):
        ext, body, companion = self._render(
            "moneywise", {"mode": "word", "entrance": "fade", "fill_color": "#F7E7A9"}
        )
        self.assertEqual(ext, ".ass")
        self.assertIn(FADE, body)
        self.assertIn("&H00A9E7F7&", body)
        self.assertTrue(companion, "the .srt still sits beside it")

    def test_word_mode_without_an_entrance_is_the_srt_it_was(self):
        from video.caption_timing import build_srt_from_words
        from video.subtitles import caption_words_per_line

        ext, body, _ = self._render("moneywise", {"mode": "word"})
        self.assertEqual(ext, ".srt")
        self.assertEqual(body, build_srt_from_words(WORDS, max_words=caption_words_per_line()))


if __name__ == "__main__":
    unittest.main()
