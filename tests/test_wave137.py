"""Wave 137 (2026-10-31) - the next five (decision 89).

#1751 the FTC line checked at publish; #1774 a platform's hour needs posts of its own, learned in
local time; #1791 the run's own cover frame sent to Buffer; #1776 TikTok captions open on the hook
with three hashtags, and the caption test records its arm; #1775 one safe zone - every overlay
clear of the apps' buttons, the hook card wrapped.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.test_buffer_crosspost import CrosspostCase

NEW_YORK = ZoneInfo("America/New_York")


# ---- #1751: the FTC line at publish -------------------------------------------------------------


class FtcAtPublishTests(unittest.TestCase):
    LINK = "GTA 6 on Amazon: https://www.amazon.com/s?k=GTA+6&tag=tapin-20"

    def _request(self, text):
        from publishing.base import PublishRequest

        return PublishRequest(file_path="v.mp4", title="t", description=text)

    def _ftc(self):
        from core.description_extras import ftc_affiliate_line

        return ftc_affiliate_line("tapin", affiliate=True)

    def test_a_link_without_its_line_gets_it_after_the_link(self):
        from publishing.prepublish import with_ftc

        text = f"Body.\n\n{self.LINK}\n\nMade with AI-assisted narration and editing."
        request, added = with_ftc(self._request(text), "tapin")
        self.assertTrue(added)
        lines = request.description.split("\n")
        self.assertEqual(lines[lines.index(self.LINK) + 1], self._ftc())

    def test_a_line_already_there_is_left(self):
        from publishing.prepublish import with_ftc

        text = f"Body.\n\n{self.LINK}\n{self._ftc()}"
        request, added = with_ftc(self._request(text), "tapin")
        self.assertEqual((added, request.description), (False, text))

    def test_no_link_no_line(self):
        from publishing.prepublish import with_ftc

        request, added = with_ftc(self._request("Body only."), "tapin")
        self.assertEqual((added, request.description), (False, "Body only."))

    def test_the_layout_still_reads_in_order(self):
        from core.description_extras import layout_problem
        from publishing.prepublish import with_ftc

        text = (f"Body.\n\nMade with AI-assisted narration and editing.\n\n{self.LINK}\n\n"
                "Sources: https://example.com")  # fmt: skip
        request, _added = with_ftc(self._request(text), "tapin")
        self.assertEqual(layout_problem(request.description, "tapin"), "")

    def test_the_checklist_names_it(self):
        from publishing.prepublish import checklist

        with patch("publishing.prepublish._run", return_value=None):
            checks = checklist(self._request(f"Body.\n{self.LINK}"), channel_id="tapin")
        ftc = [c for c in checks if c.name == "ftc"]
        self.assertEqual(len(ftc), 1)
        self.assertFalse(ftc[0].ok)
        self.assertFalse(ftc[0].blocks)

    def test_the_upload_runs_it(self):
        import inspect

        from publishing import youtube_publisher

        self.assertIn("prepublish.with_ftc(", inspect.getsource(youtube_publisher))


# ---- #1774: an hour needs posts of its own, in local time ----------------------------------------


class OwnHourTests(unittest.TestCase):
    def test_a_two_post_hour_does_not_win(self):
        from publishing.platform_recommend import _best

        rows = [{"local_hour": 20, "views": v} for v in (138, 218)]
        rows += [{"local_hour": 22, "views": 111} for _ in range(21)]
        self.assertEqual(_best(rows, "local_hour"), 22)

    def test_no_hour_with_four_posts_keeps_the_evening_slot(self):
        from publishing import platform_recommend as pr

        rows = [{"measured": True, "views": 100, "local_hour": h} for h in (20, 20, 21, 22, 22, 23)]
        with patch.object(pr, "_measured", return_value=rows):
            hour, note = pr.hour_choice("tapin", "instagram")
        self.assertIsNone(hour)
        self.assertIn("4 posts of its own", note)

    def test_the_hour_is_learned_in_local_time(self):
        from publishing import platform_recommend as pr

        store = {"rows": {"301": {"instagram": {"measured": True, "views": 120, "hour": 2}}}}
        posts = {"posts": {"301": {"instagram": {"state": "sent",
                                                 "sent_at": "2026-10-20T02:00:00+00:00"}}}}  # fmt: skip
        with (
            patch("publishing.platform_metrics.load", return_value=store),
            patch("publishing.crosspost._load", return_value=posts),
            patch("publishing.crosspost._zone", return_value=NEW_YORK),
        ):
            rows = pr._measured("tapin", "instagram")
        self.assertEqual(rows[0]["local_hour"], 22)  # 10 PM EDT

    def test_a_local_hour_holds_across_the_clock_change(self):
        from publishing.crosspost import _at_local_hour

        after = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        due = _at_local_hour(22, after, NEW_YORK)
        self.assertEqual(due, datetime(2026, 11, 3, 3, 0, tzinfo=timezone.utc))  # 10 PM EST

    def test_the_post_goes_at_the_local_hour(self):
        from publishing import crosspost

        now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        with (
            patch("publishing.platform_recommend.hour_choice", return_value=(22, "x")),
            patch.object(crosspost, "_zone", return_value=NEW_YORK),
        ):
            due, _note = crosspost._next_due("tapin", "UFC", "instagram", {}, now)
        self.assertEqual(due, datetime(2026, 11, 3, 3, 0, tzinfo=timezone.utc))


# ---- #1791: the run's own cover frame ------------------------------------------------------------


class CoverFrameTests(unittest.TestCase):
    def test_the_runs_cover_moment_is_sent(self):
        from publishing.crosspost import _thumbnail_ms

        run = SimpleNamespace(id=5, quality_json=json.dumps({"cover_ms": 1040}))
        self.assertEqual(_thumbnail_ms("tapin", run), 1040)

    def test_with_no_cover_and_no_intro_one_second(self):
        from publishing.crosspost import _thumbnail_ms

        opened = json.dumps({"opening": {"intro": False, "intro_seconds": 0.0}})
        self.assertEqual(_thumbnail_ms("tapin", SimpleNamespace(id=5, quality_json=opened)), 1000)
        with patch("video.channel_intro.resolve_intro_path", return_value=None):
            self.assertEqual(_thumbnail_ms("tapin", SimpleNamespace(id=6)), 1000)

    def test_an_intro_still_moves_it(self):
        from publishing.crosspost import _thumbnail_ms

        with patch("video.channel_intro.resolve_intro_path", return_value="intro.mp4"):
            self.assertEqual(_thumbnail_ms("tapin", SimpleNamespace(id=6)), 3150)

    def test_the_moment_adds_the_intro(self):
        from assets.cover_frames import cover_ms

        self.assertEqual(cover_ms(1.0, 0.0), 1000)
        self.assertEqual(cover_ms(1.2, 2.15), 3350)

    def _done(self):
        return [(0, ("a.mp4", 5.0, 2.5), "s0.mp4"), (1, ("b.mp4", 1.0, 3.0), "s1.mp4")]

    def test_the_cut_reports_where_the_cover_is(self):
        from assets import fast_cut
        from assets.cover_frames import Cover

        first = Cover(index=0, path="c.jpg", hash=1, score=1.0)
        with (
            patch("assets.cover_frames.choose_cover", return_value=first),
            patch("assets.cover_frames.finish", return_value="v_frame_cover.jpg"),
        ):
            self.assertEqual(fast_cut._cover_and_open(self._done(), "v.mp4"),
                             ("v_frame_cover.jpg", 1.0))  # fmt: skip
        second = Cover(index=1, path="c.jpg", hash=1, score=1.0)
        with (
            patch("assets.cover_frames.choose_cover", return_value=second),
            patch("assets.cover_frames.finish", return_value="v_frame_cover.jpg"),
            patch("assets.cover_frames.frame_at", return_value="c.jpg"),
            patch.object(fast_cut, "_render_shot"),
        ):
            path, at = fast_cut._cover_and_open(self._done(), "v.mp4")
        self.assertEqual(path, "v_frame_cover.jpg")
        self.assertAlmostEqual(at, 1.2)  # 40% of shot 1's 3 s, inside shot 0's 2.5 s

    def test_the_render_records_it_and_the_round_sends_it(self):
        import inspect

        from core import pipeline
        from publishing import crosspost

        self.assertIn("cover_ms(", inspect.getsource(pipeline))
        self.assertIn('"cover_ms"', inspect.getsource(pipeline))
        source = inspect.getsource(crosspost)
        self.assertIn("thumbnail_ms=_thumbnail_ms(channel_id, run)", source)
        self.assertNotIn("thumbnail_ms=_thumbnail_ms(channel_id)", source)


# ---- #1776: TikTok captions, the caption test recorded -------------------------------------------


def _run219(run_id=219):
    return SimpleNamespace(
        id=run_id, channel_id="tapin",
        title="Moicano vs Nolan Fight Preview: Stakes, Form, and What's on the Line in UFC Matchup",
        input_topic="UFC Fight Night Moicano vs Nolan stakes rise for rankings shakeup",
        selected_topic="UFC Fight Night Moicano vs Nolan stakes rise for rankings shakeup",
        description=(
            "Moicano took this fight because Ortega pulled out twice - that's not a rankings "
            "shakeup. Renato Moicano (21-7-1) meets Tom Nolan (11-1) in the UFC Vegas 123 main "
            "event Saturday. Subscribe for daily UFC takes.\n\nMade with AI-assisted narration "
            "and editing."
        ),
        tags_json=json.dumps(["UFC", "MoicanoVsNolan", "RenatoMoicano", "TomNolan",
                              "UFCFightNight", "shorts", "TapIn"]),
    )  # fmt: skip


class TikTokCaptionTests(unittest.TestCase):
    def test_the_hook_opens_it_with_three_hashtags(self):
        from publishing.platform_captions import tiktok_caption

        text = tiktok_caption("tapin", _run219())
        first = text.split("\n")[0]
        self.assertTrue(first.startswith("Moicano took this fight"))
        self.assertLessEqual(len(first), 100)
        self.assertEqual(re.findall(r"#\w+", text), ["#MoicanoVsNolan", "#RenatoMoicano", "#UFC"])
        self.assertIn("Follow for daily UFC takes.", text)
        self.assertNotIn("Subscribe", text)

    def test_the_briefs_fixture(self):
        from publishing.platform_captions import tiktok_caption

        title = "Seahawks defense stifles Chiefs offense in 20-3 Sunday Night Football win"
        run = SimpleNamespace(
            id=7, title=title, input_topic=title, selected_topic=title,
            description="Seattle held Kansas City to three points. Subscribe for daily NFL takes.",
            tags_json=json.dumps(["NFL", "Seahawks", "Chiefs", "SundayNightFootball", "shorts"]),
        )  # fmt: skip
        text = tiktok_caption("tapin", run)
        self.assertLess(len(text.split("\n")[0]), 100)
        self.assertEqual(len(re.findall(r"#\w+", text)), 3)
        self.assertTrue(text.split("\n\n")[-2].endswith("#NFL"))

    def test_a_long_hook_leaves_the_title_first(self):
        from publishing.platform_captions import tiktok_caption

        run = _run219()
        run.description = ("Moicano took this fight because Ortega pulled out twice and the "
                           "promotion needed a main event on short notice in Las Vegas this week. "
                           "More.")  # fmt: skip
        self.assertEqual(tiktok_caption("tapin", run).split("\n")[0], run.title)

    def test_tiktok_gets_it_and_instagram_keeps_testing(self):
        from publishing.platform_captions import choose_caption, tiktok_caption

        run = _run219()
        self.assertEqual(choose_caption("tapin", run, "tiktok"),
                         ("hook_first", tiktok_caption("tapin", run)))  # fmt: skip
        self.assertIn(choose_caption("tapin", run, "instagram")[0], ("caption", "first_line"))

    def test_off_youtube_follow_not_subscribe_and_no_shorts_tag(self):
        from publishing.crosspost import caption, hashtags

        self.assertEqual(hashtags(["shorts", "NFL", "Shorts"]), ["#NFL"])
        text = caption(_run219())
        self.assertIn("Follow for daily UFC takes.", text)
        self.assertNotIn("Subscribe", text)
        self.assertNotIn("#shorts", text)


class CaptionArmKeptTests(CrosspostCase):
    def test_the_scheduled_post_keeps_its_arm(self):
        self._first_then((113, "yt113"))
        posts = self._store()["posts"]["113"]
        self.assertEqual(posts["tiktok"]["arm"], "hook_first")
        self.assertIn(posts["instagram"]["arm"], ("caption", "first_line"))


class CaptionReplayTests(unittest.TestCase):
    def test_a_post_without_its_arm_is_replayed_only_when_its_opening_matches(self):
        from core.experiments import random_arm
        from publishing import platform_captions as pc

        texts = pc.caption_texts(_run219())
        self.assertNotEqual(texts["caption"], texts["first_line"])
        arm = random_arm("tapin", "caption_instagram", 219)
        posts = {"posts": {
            "219": {"instagram": {"state": "sent", "text_start": texts[arm][:60]}},
            "220": {"instagram": {"state": "sent", "text_start": "something else entirely"}},
            "221": {"instagram": {"state": "manual"}},
            "222": {"instagram": {"state": "sent", "arm": "caption"}},
        }}  # fmt: skip
        with (
            patch("publishing.crosspost._load", return_value=posts),
            patch("publishing.crosspost._content_run", side_effect=_run219),
            patch("publishing.platform_metrics.get_row",
                  return_value={"measured": True, "views": 100}),
        ):  # fmt: skip
            outcomes = pc.caption_outcomes("tapin", "instagram")
        expected = {"caption": [100.0], "first_line": []}
        expected[arm].append(100.0)
        self.assertEqual(outcomes, expected)


# ---- #1775: one safe zone ------------------------------------------------------------------------

_WORDS = [
    {"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25}
    for i, w in enumerate(
        [
            "Renato",
            "Moicano",
            "took",
            "this",
            "fight",
            "because",
            "Ortega",
            "pulled",
            "out",
            "twice",
        ]
    )
]
_HOOK = ("Moicano took this fight because Ortega pulled out twice, and Moicano will cash in on "
         "the chance this Saturday night. Then the rest.")  # fmt: skip


def _styles(ass: str) -> dict[str, dict[str, str]]:
    fields: list[str] = []
    out: dict[str, dict[str, str]] = {}
    for line in ass.splitlines():
        if line.startswith("Format:") and not fields and "Fontsize" in line:
            fields = [f.strip() for f in line[len("Format:") :].split(",")]
        elif line.startswith("Style:"):
            values = [v.strip() for v in line[len("Style:") :].split(",")]
            out[values[0]] = dict(zip(fields, values, strict=False))
    return out


class SafeZoneTests(unittest.TestCase):
    def test_captions_end_above_the_bottom_fifth(self):
        from video.caption_timing import build_ass_karaoke
        from video.safe_zone import outside

        for margin in (260, 10):
            ass = build_ass_karaoke(_WORDS, title_font="Impact", body_font="Arial", margin=margin)
            for name in ("Title", "Body"):
                self.assertGreaterEqual(int(_styles(ass)[name]["MarginV"]), 384)
            self.assertEqual(outside(ass), [])

    def test_top_anchored_captions_sit_below_the_top_cards(self):
        from video.caption_timing import build_ass_karaoke
        from video.safe_zone import HOOK_CARD_MARGIN

        ass = build_ass_karaoke(_WORDS, anchor="top", margin=260)
        self.assertGreater(int(_styles(ass)["Default"]["MarginV"]), HOOK_CARD_MARGIN + 3 * 64)

    def test_the_hook_card_wraps_inside_the_frame(self):
        from video.caption_timing import FULL_TEXT_WIDTH, build_ass_karaoke, karaoke_max_chars
        from video.subtitles import _with_hook_card

        ass = _with_hook_card(build_ass_karaoke(_WORDS), _HOOK, "tapin")
        hook = _styles(ass)["Hook"]
        self.assertGreaterEqual(int(hook["MarginV"]), 192)  # the brief: at or below 10%
        self.assertEqual(hook["Alignment"], "8")
        event = next(line for line in ass.splitlines() if ",Hook," in line)
        lines = event.split(",,", 1)[1].split(",", 4)[-1].split("\\N")
        self.assertGreater(len(lines), 1)
        self.assertLessEqual(len(lines), 3)
        size = int(hook["Fontsize"])
        for line in lines:
            self.assertLessEqual(len(line), karaoke_max_chars(size, width=FULL_TEXT_WIDTH))  # #1921
        self.assertEqual(" ".join(lines), _HOOK.split(". ")[0] + ".")

    def test_the_hook_card_is_below_the_ai_line(self):
        from video.caption_timing import build_ass_karaoke
        from video.policy_overlays import build_policy_overlays_ass
        from video.subtitles import _with_hook_card

        hook = _styles(_with_hook_card(build_ass_karaoke(_WORDS), _HOOK, "tapin"))["Hook"]
        line = _styles(build_policy_overlays_ass("tapin", None, duration=30.0))["Disclosure"]
        bottom = int(line["MarginV"]) + 1.3 * int(line["Fontsize"]) + 2 * int(line["Outline"])
        self.assertLess(bottom, int(hook["MarginV"]))
        self.assertGreaterEqual(int(line["MarginV"]), 231)

    def test_name_tags_and_the_policy_lines_sit_inside(self):
        from video.lower_thirds import build_lower_thirds_ass
        from video.policy_overlays import build_policy_overlays_ass
        from video.safe_zone import outside

        lower = build_lower_thirds_ass(["Renato Moicano"], _WORDS)
        self.assertTrue(lower)
        self.assertEqual(outside(lower), [])
        self.assertEqual(outside(build_policy_overlays_ass("tapin", None, duration=30.0)), [])
        with patch("core.description_extras.finance_disclaimer_line", return_value="Not advice."):
            self.assertEqual(outside(build_policy_overlays_ass("moneywise", None)), [])

    def test_a_style_in_the_chrome_is_named(self):
        from video.safe_zone import outside

        ass = ("[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
               "Format: Name, Fontname, Fontsize, Alignment, MarginV\n"
               "Style: Low,Arial,90,2,260\nStyle: High,Arial,64,8,120\nStyle: Ok,Arial,64,8,300\n")  # fmt: skip
        self.assertEqual(outside(ass), ["Low", "High"])

    def test_the_scrim_and_the_contrast_check_read_the_caption_band(self):
        from PIL import Image

        from core.caption_contrast import inspect_caption_band
        from video.render_video import _scrim_filter
        from video.safe_zone import CAPTION_BAND

        self.assertEqual(CAPTION_BAND, (0.68, 0.80))
        self.assertIn("y=ih*0.68:w=iw:h=ih*0.12", _scrim_filter(0.4))
        self.assertEqual(_scrim_filter(0.0), "")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f.png")
            image = Image.new("RGB", (108, 192), (5, 5, 5))  # dark chrome below
            for y in range(int(192 * 0.68), int(192 * 0.80)):
                for x in range(108):
                    image.putpixel((x, y), (240, 240, 240))  # light where the captions are
            image.save(path)
            self.assertFalse(inspect_caption_band(path, fill_hex="#FFFFFF").passed)

    def test_the_end_card_and_the_draft_guides_share_the_zone(self):
        from video import channel_outro, safe_zone

        self.assertEqual((channel_outro._SAFE_TOP, channel_outro._SAFE_BOTTOM),
                         (safe_zone.SAFE_TOP, safe_zone.SAFE_BOTTOM))  # fmt: skip

    def test_the_srt_path_already_ends_above_the_bottom_fifth(self):
        from video.subtitles import caption_force_style

        margin = int(re.search(r"MarginV=(\d+)", caption_force_style("tapin")).group(1))
        self.assertGreaterEqual(margin / 288, 0.20)  # libass's default SRT canvas is 288 tall

    def test_the_render_warns_on_a_style_outside(self):
        import inspect

        from video import render_video

        self.assertIn("outside(", inspect.getsource(render_video))


if __name__ == "__main__":
    unittest.main()
