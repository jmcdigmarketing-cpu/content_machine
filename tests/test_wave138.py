"""Wave 138 (2026-10-31) - the next five (decision 90).

#1917 a scheduled video is not crossposted before its slot, even when YouTube cannot be read;
#1916 the booth shows the run's own cover and how it sits beside the last ten; #1921 captions
keep clear of TikTok's right-hand buttons; #1920 one crosspost in eight tries another hour;
#1760 the Black Friday deals long video, drafted Nov 23, with up to three links.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from tests.test_buffer_crosspost import CrosspostCase

NEW_YORK = ZoneInfo("America/New_York")


# ---- #1917: no crosspost before the YouTube slot -------------------------------------------------


class SlotAheadTests(CrosspostCase):
    """Run 199: YouTube holds it private until Nov 1 10:15 UTC, its record carries that slot, and
    the 21:07 round sent its TikTok post anyway - the YouTube read failed, and a failure held
    nothing."""

    def test_a_slot_still_ahead_holds_the_run_with_youtube_unread(self):
        from publishing.crosspost import send_due

        ahead = datetime.now(timezone.utc) + timedelta(days=1)
        with (
            patch("publishing.crosspost._public_times", return_value={113: ahead}),
            patch("publishing.crosspost._held_by_youtube", return_value={}),
        ):
            send_due("tapin")  # the first call records what was already public
            self.public.append((113, "yt113"))
            lines = send_due("tapin")
        self.assertEqual(self.create.call_count, 0)
        self.assertNotIn("113", self._store().get("posts") or {})
        self.assertTrue(any("run 113" in line and "slot" in line for line in lines), lines)

    def test_a_slot_passed_goes_as_before(self):
        from publishing.crosspost import send_due

        passed = datetime.now(timezone.utc) - timedelta(minutes=5)
        with (
            patch("publishing.crosspost._public_times", return_value={113: passed}),
            patch("publishing.crosspost._held_by_youtube", return_value={}),
        ):
            send_due("tapin")
            self.public.append((113, "yt113"))
            send_due("tapin")
        self.assertEqual(self.create.call_count, 2)


# ---- #1916: the booth shows the run's own cover --------------------------------------------------


class BoothCoverTests(unittest.TestCase):
    def test_a_frame_cover_is_recorded_as_a_frame(self):
        from core import asset_recorder

        repo = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            cover = os.path.join(tmp, "fastcut_abc_frame_cover.jpg")
            open(cover, "wb").close()
            with patch.object(asset_recorder, "get_asset_repository", return_value=repo):
                asset_recorder.record_render_assets(channel_id="tapin", content_run_id=219,
                                                    topic="t", title="t", mp4_path="",
                                                    thumbnail_path=cover)  # fmt: skip
        rows = [c.args[0] for c in repo.create.call_args_list]
        self.assertEqual([(r["asset_type"], r["provider"]) for r in rows], [("thumbnail", "frame")])

    def test_the_booth_reads_the_runs_own_thumbnail(self):
        from core import review_booth

        with tempfile.TemporaryDirectory() as tmp:
            mine = os.path.join(tmp, "fastcut_abc_frame_cover.jpg")
            open(mine, "wb").close()
            rows = [
                SimpleNamespace(asset_type="background", path=os.path.join(tmp, "bg.mp4")),
                SimpleNamespace(asset_type="thumbnail", path=os.path.join(tmp, "gone.jpg")),
                SimpleNamespace(asset_type="thumbnail", path=mine),
            ]
            repo = MagicMock()
            repo.list_for_run.return_value = rows
            with patch("storage.repositories.assets.get_asset_repository", return_value=repo):
                self.assertEqual(review_booth.run_thumbnail(219), mine)
                repo.list_for_run.return_value = rows[:2]
                self.assertIsNone(review_booth.run_thumbnail(219))
            self.assertIsNone(review_booth.run_thumbnail(None))

    def test_the_cover_strip_is_shown_for_a_frame_cover(self):
        from core import review_booth

        lines = [
            "Cover: x_frame_cover.jpg",
            "   4 bits from y_frame_cover.jpg  <- the same picture",
        ]
        with patch("assets.cover_frames.strip_lines", return_value=lines):
            html = review_booth.cover_strip_html("C:/t/x_frame_cover.jpg")
        self.assertIn("the same picture", html)
        self.assertIn("4 bits", html)
        self.assertEqual(review_booth.cover_strip_html("C:/t/run219_pillow.jpg"), "")
        page = review_booth.booth_html(cover_strip="<pre class='cover-strip'>X</pre>")
        self.assertIn("<pre class='cover-strip'>X</pre>", page)

    def test_the_booth_context_uses_them(self):
        import inspect

        from core import review_booth

        source = inspect.getsource(review_booth.gather_booth_context)
        self.assertIn("run_thumbnail(", source)
        self.assertIn("cover_strip_html(", source)


# ---- #1921: captions clear of TikTok's right-hand buttons ----------------------------------------

_WORDS = [
    {"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35}
    for i, w in enumerate(["Topuria", "defends", "the", "belt", "tonight", "in", "Vegas"])
]


def _style_fields(ass: str) -> dict[str, dict[str, str]]:
    fields: list[str] = []
    out: dict[str, dict[str, str]] = {}
    for line in ass.splitlines():
        if line.startswith("Format:") and not fields and "MarginL" in line:
            fields = [f.strip() for f in line[len("Format:") :].split(",")]
        elif line.startswith("Style:"):
            values = [v.strip() for v in line[len("Style:") :].split(",")]
            out[values[0]] = dict(zip(fields, values, strict=False))
    return out


class RightButtonsTests(unittest.TestCase):
    def test_every_caption_style_keeps_the_sides_clear(self):
        from video.caption_timing import build_ass_karaoke
        from video.safe_zone import SIDE_PX

        self.assertEqual(SIDE_PX, 130)
        two = [dict(w, role="narrator" if i < 3 else "cohost") for i, w in enumerate(_WORDS)]
        for ass in (build_ass_karaoke(_WORDS), build_ass_karaoke(_WORDS, title_font="Impact",
                                                                  body_font="Arial"),
                    build_ass_karaoke(two)):  # fmt: skip
            for name, style in _style_fields(ass).items():
                self.assertGreaterEqual(int(style["MarginL"]), SIDE_PX, name)
                self.assertGreaterEqual(int(style["MarginR"]), SIDE_PX, name)

    def test_a_line_fits_the_narrower_width(self):
        from video.caption_timing import build_ass_karaoke, karaoke_max_chars

        self.assertEqual(karaoke_max_chars(90), 17)  # 820 px of text
        texts = [line.split(",,", 1)[1] for line in build_ass_karaoke(_WORDS).splitlines()
                 if line.startswith("Dialogue:")]  # fmt: skip
        import re

        for text in texts:
            words = re.sub(r"\{[^}]*\}", "", text.split(",", 4)[-1]).strip()
            self.assertLessEqual(len(words), 17, words)

    def test_the_hook_card_keeps_its_full_width(self):
        from video.caption_timing import karaoke_max_chars
        from video.subtitles import hook_card_lines

        self.assertEqual(karaoke_max_chars(64, width=920), 27)
        size, lines = hook_card_lines(
            "Moicano took this fight because Ortega pulled out twice, and Moicano will cash in on "
            "the chance this Saturday night."
        )
        self.assertEqual((size, len(lines)), (44, 3))


# ---- #1920: one crosspost in eight tries another hour --------------------------------------------


def _rows(hours: dict[int, int]) -> list[dict]:
    return [{"measured": True, "views": 100, "local_hour": h} for h, n in hours.items()
            for _ in range(n)]  # fmt: skip


class ExploreHourTests(unittest.TestCase):
    def test_about_one_in_eight(self):
        from publishing import platform_recommend as pr

        with patch.object(pr, "_measured", return_value=_rows({22: 21})):
            picked = [pr.explore_hour("tapin", "instagram", run) for run in range(1, 801)]
        share = sum(1 for h in picked if h is not None) / len(picked)
        self.assertGreater(share, 0.08)
        self.assertLess(share, 0.17)

    def test_the_same_run_always_gets_the_same_answer(self):
        from publishing import platform_recommend as pr

        with patch.object(pr, "_measured", return_value=_rows({22: 21})):
            first = [pr.explore_hour("tapin", "tiktok", run) for run in range(1, 101)]
            again = [pr.explore_hour("tapin", "tiktok", run) for run in range(1, 101)]
        self.assertEqual(first, again)

    def test_it_picks_the_hour_with_fewest_posts_of_its_own(self):
        from publishing import platform_recommend as pr

        rows = _rows({12: 3, 15: 1, 18: 2, 20: 4, 22: 21})
        with patch.object(pr, "_measured", return_value=rows):
            hours = {pr.explore_hour("tapin", "instagram", run) for run in range(1, 400)}
        self.assertEqual(hours - {None}, {15})

    def test_the_post_goes_at_the_tried_hour_and_a_game_still_comes_first(self):
        from publishing import crosspost

        now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        with (
            patch("publishing.platform_recommend.explore_hour", return_value=15),
            patch("publishing.platform_recommend.hour_choice", return_value=(22, "x")),
            patch.object(crosspost, "_zone", return_value=NEW_YORK),
        ):
            due, note = crosspost._next_due("tapin", "UFC", "tiktok", {}, now, run_id=7)
            self.assertEqual(due, datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc))  # 3 PM EST
            self.assertIn("3 PM", note)
            kickoff = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
            early, why = crosspost._next_due("tapin", "UFC", "tiktok", {}, now, kickoff=kickoff,
                                             run_id=7)  # fmt: skip
        self.assertLessEqual(early, kickoff - timedelta(minutes=30))
        self.assertIn("before its game", why)

    def test_the_round_passes_the_run(self):
        import inspect

        from publishing import crosspost

        self.assertIn("run_id=run_id", inspect.getsource(crosspost.send_due))


# ---- #1760: the Black Friday deals long video ----------------------------------------------------


class BlackFridayTests(unittest.TestCase):
    def test_the_row_is_a_long_video_on_nov_23(self):
        from core.series.countdown import series_rows

        rows = {r["id"]: r for r in series_rows("tapin")}
        row = rows["black-friday-deals"]
        self.assertEqual((row["kind"], row["on"]), ("long", "2026-11-23"))
        self.assertIn("Black Friday", row["names"])

    def test_it_is_drafted_on_the_day_from_that_weeks_deal_headlines(self):
        from core.series import dated

        when = datetime(2026, 11, 22, 14, tzinfo=timezone.utc)
        lines = [{"title": "Black Friday 2026: the best PS5 and Xbox deals so far", "source": "IGN",
                  "published": when}]  # fmt: skip
        with (
            patch.dict(os.environ, {"SERIES_DATED": "true"}),
            patch.object(dated, "channel_day", return_value=date(2026, 11, 23)),
            patch("core.batch_generation.series_drafted", return_value=False),
        ):
            ideas = dated.dated_ideas("tapin", now=datetime(2026, 11, 23, 15, tzinfo=timezone.utc),
                                      headlines=lambda *_a: list(lines))  # fmt: skip
        deals = [i for i in ideas if "Black Friday" in i.topic]
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].draft_kind, "long")
        self.assertIn("IGN reported: Black Friday 2026: the best PS5 and Xbox deals so far",
                      deals[0].facts)  # fmt: skip

    SCRIPT = (
        "GTA 6 is the year's biggest launch, a PS5 bundle is down to its lowest price, the "
        "Xbox Series X drops too, and the Switch 2 has its first discount."
    )

    def test_a_deals_video_carries_up_to_three_links_and_one_ftc_line(self):
        from core.description_extras import affiliate_lines, ftc_affiliate_line

        with patch.dict(os.environ, {"AFFILIATE_AMAZON_TAG": "tapin-20"}):
            got = affiliate_lines("tapin", "Black Friday 2026: the gaming deals worth buying",
                                  "Black Friday 2026 gaming deals worth buying", long_form=True,
                                  script=self.SCRIPT)  # fmt: skip
        links = [line for line in got if "amazon.com" in line]
        self.assertEqual(len(links), 3)
        self.assertTrue(all("tag=tapin-20" in line for line in links))
        self.assertEqual(got[-1], ftc_affiliate_line("tapin", affiliate=True))
        self.assertEqual(sum(1 for line in got if line == got[-1]), 1)

    def test_another_long_video_keeps_one_link_and_no_console_rows(self):
        from core.description_extras import affiliate_lines

        with patch.dict(os.environ, {"AFFILIATE_AMAZON_TAG": "tapin-20"}):
            gta = affiliate_lines("tapin", "GTA 6 Release Date: Everything We Know Before Launch",
                                  "GTA 6 - everything we know before launch", long_form=True,
                                  script=self.SCRIPT)  # fmt: skip
            xbox = affiliate_lines("tapin", "Xbox Game Pass in November", "Xbox Game Pass",
                                   long_form=True, script=self.SCRIPT)  # fmt: skip
        first = next(line for line in gta if "amazon.com" in line)
        # decision 95 (#1749): a GTA long video links both editions - and still no console row
        self.assertEqual(first.split(":")[0], "GTA 6 Standard Edition on Amazon")
        self.assertEqual(sum(1 for line in gta if "amazon.com" in line), 2)
        self.assertEqual(xbox, [])  # a console row is for a deals video only

    def test_no_tag_no_links(self):
        from core.description_extras import affiliate_lines

        with patch.dict(os.environ, {"AFFILIATE_AMAZON_TAG": ""}):
            got = affiliate_lines("tapin", "Black Friday 2026: the gaming deals worth buying", "",
                                  long_form=True, script=self.SCRIPT)  # fmt: skip
        self.assertEqual(got, [])

    def test_the_description_hands_it_the_script(self):
        import inspect

        from core import description_extras

        source = inspect.getsource(description_extras.apply_description_extras)
        self.assertIn("script=script", source)


if __name__ == "__main__":
    unittest.main()
