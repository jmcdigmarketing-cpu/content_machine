"""Every path in one filter graph must be escaped the same way.

`build_render_ffmpeg_command` emits two `subtitles=` entries. The main caption line
quotes manually and produces the form ffmpeg wants; the lower-thirds line went through
`{...!r}`, and Python's repr escapes the backslash that `_escape_subtitle_path`
deliberately inserted before the drive-letter colon:

    subtitles='C\\\\:/dev/out/lt.ass'      <- repr, two backslashes
    subtitles='C\\:/dev/out/sub.srt'      <- manual, one backslash

ffmpeg reads `\\\\` as a literal backslash, leaving the colon unescaped, so the
lower-thirds filter fails to parse on Windows — the only platform this runs on.

CI stayed green because the one test reaching this code passed `lower_thirds_path=None`
(`tests/test_roadmap_23_27.py`), switching off the feature it was covering. The wave's
own font-path assertion already pins the correct single-backslash convention.
"""

import re
import unittest

from video.render_video import _escape_subtitle_path, build_render_ffmpeg_command

WIN_SUB = "C:/dev/out/sub.srt"
WIN_LT = "C:/dev/out/lt.ass"


def _graph(**kwargs) -> str:
    cmd = build_render_ffmpeg_command(
        background_path="C:/dev/bg.mp4",
        mp3_path="C:/dev/a.mp3",
        output_path="C:/dev/out/v.mp4",
        subtitle_path=WIN_SUB,
        duration=30.0,
        **kwargs,
    )
    return cmd[cmd.index("-filter_complex") + 1]


class TestBothSubtitlePathsEscapeIdentically(unittest.TestCase):
    def test_lower_thirds_uses_the_same_form_as_the_captions(self):
        graph = _graph(lower_thirds_path=WIN_LT)
        self.assertIn(f"subtitles='{_escape_subtitle_path(WIN_SUB)}'", graph)
        self.assertIn(f"subtitles='{_escape_subtitle_path(WIN_LT)}'", graph)

    def test_no_doubled_backslash_reaches_ffmpeg(self):
        graph = _graph(lower_thirds_path=WIN_LT)
        self.assertNotIn("\\\\", graph, "a doubled backslash means repr escaped our escape")

    def test_the_drive_colon_is_escaped_exactly_once_in_both(self):
        graph = _graph(lower_thirds_path=WIN_LT)
        drive_refs = re.findall(r"subtitles='([^']*)'", graph)
        self.assertEqual(len(drive_refs), 2, graph)
        for path in drive_refs:
            self.assertIn(r"C\:", path)
            self.assertNotIn(r"C\\:", path)

    def test_lower_thirds_precedes_the_captions(self):
        # Captions must burn on top of the lower third, not under it.
        graph = _graph(lower_thirds_path=WIN_LT)
        self.assertLess(graph.index(_escape_subtitle_path(WIN_LT)), graph.index("sub.srt"))

    def test_absent_lower_thirds_leaves_one_subtitles_entry(self):
        graph = _graph(lower_thirds_path=None)
        self.assertEqual(graph.count("subtitles="), 1)


class TestForceStyleEscaping(unittest.TestCase):
    """Same `!r` mistake, latent: the apostrophe is already escaped before repr runs."""

    def test_plain_style_is_passed_through_quoted(self):
        graph = _graph(caption_force_style="FontName=Arial,Outline=2")
        self.assertIn("force_style='FontName=Arial,Outline=2'", graph)

    def test_apostrophe_is_escaped_once(self):
        graph = _graph(caption_force_style="FontName=Bob's Font")
        self.assertIn(r"\'", graph)
        self.assertNotIn(r"\\'", graph, "repr re-escaped an already-escaped apostrophe")

    def test_no_style_emits_no_force_style(self):
        self.assertNotIn("force_style", _graph(caption_force_style=""))


if __name__ == "__main__":
    unittest.main()
