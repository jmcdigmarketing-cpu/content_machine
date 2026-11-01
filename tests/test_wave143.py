"""Wave 143 (2026-11-01) - the next five (decision 95), S06 the shortfall it takes.

S06 the take detector learns the shapes the scripts' takes are written in - all four public
"recaps" carried one; #1958 a countdown day is compared with its own series on wording only, not
on subject (run 221 was held for sharing GTA 6's words with run 216); #1749 a GTA long video links
both editions; #1741 a long video's description is a 150-250 word summary led by its title;
#1764 no gambling affiliate or sportsbook link, whatever the settings.
"""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

# ---- S06: the shapes a take is written in --------------------------------------------------------

# Each from a stored script the detector read as a recap (live, 2026-11-01).
TAKES = {
    131: "Ten turnovers and the Chargers are 0-4. But here's what nobody's saying - the path back is "
         "real, and it starts Sunday against Denver.",
    132: "Gaethje beat Topuria at UFC Freedom 250. Here's the trap: a grudge fight is the loudest, "
         "easiest path back for Topuria.",
    187: "Jackson scored twice for Aston Villa. That's the part people are sleeping on - City lost "
         "their cushion at the top.",
    220: "GTA 6 has a morality scale and a couple rating. Here's where it bites: every one of those "
         "systems is a patch target for Rockstar.",
    222: "GTA 6's map could be the biggest ever. So the real question is density, not square miles, "
         "for Rockstar.",
    140: "Justin Herbert's deep-ball rate fell again. Watch the next game for the Chargers' line.",
}  # fmt: skip


class TakeShapeTests(unittest.TestCase):
    def test_each_shape_from_a_stored_script_reads_as_a_take(self):
        from core.authenticity import has_insight

        for run_id, script in TAKES.items():
            self.assertTrue(has_insight(script), run_id)

    def test_bigger_does_not_mean_better_is_a_take(self):
        from core.authenticity import has_insight

        self.assertTrue(has_insight("GTA 6's map is the biggest ever, but bigger doesn't mean "
                                    "better for Rockstar's open world."))  # fmt: skip

    def test_a_recap_is_still_a_recap(self):
        from core.authenticity import has_insight

        self.assertFalse(has_insight("The Knicks raised their NBA Cup banner in the Garden, and the "
                                     "Spurs open the tournament on Friday against Denver."))  # fmt: skip


# ---- #1958: a series day against its own series ------------------------------------------------

DAY_216 = (
    "GTA 6 launches in 20 days on November 19 for PS5 and Xbox Series X. Rockstar confirmed a "
    "morality system, a score preorder bonus and no PC date. GTA 6 fans want the PC date and "
    "GTA Online. Rockstar says GTA 6 Online comes later. Watch the first week of streams."
)
DAY_221 = (
    "Eighteen days out, and the GTA 6 community has a wishlist for Rockstar. GTA 6 players want "
    "GTA Online on day one, a PC date, and the PS5 and Xbox Series X versions to match. "
    "Rockstar has said GTA 6 Online comes later. Here's the trap: wishlists set the bar."
)
OTHER = "Nolan's six-fight win streak is on the line against Moicano in Vegas this Saturday night."


class SeriesVariationTests(unittest.TestCase):
    def test_the_series_key_takes_the_day_count_out(self):
        from core.authenticity import series_key

        self.assertEqual(
            series_key("GTA 6: 18 days to launch"), series_key("GTA 6: 20 days to launch")
        )
        self.assertEqual(
            series_key("GTA 6: 1 day to launch"), series_key("GTA 6: 20 days to launch")
        )
        self.assertNotEqual(
            series_key("GTA 5: 18 days to launch"), series_key("GTA 6: 18 days to launch")
        )
        self.assertEqual(series_key(""), "")

    def test_a_sibling_day_is_not_held_for_its_subject(self):
        from core.authenticity import _variation_check

        held = _variation_check(DAY_221, [DAY_216, OTHER])
        self.assertFalse(held.passed)  # today: 'too like a recent video' on subject alone
        self.assertTrue(_variation_check(DAY_221, [DAY_216, OTHER], siblings={0}).passed)

    def test_a_sibling_copied_word_for_word_is_still_held(self):
        from core.authenticity import _variation_check

        self.assertFalse(_variation_check(DAY_216, [DAY_216, OTHER], siblings={0}).passed)

    def test_the_store_marks_the_siblings_by_their_title_stem(self):
        from core import authenticity

        runs = [
            SimpleNamespace(id=216, script_preview=DAY_216,
                            features_json=json.dumps({"best_bet": {"title_stem": "GTA 6: 20 days to launch"}})),
            SimpleNamespace(id=219, script_preview=OTHER, features_json="{}"),
        ]  # fmt: skip
        repo = SimpleNamespace(list_for_channel=lambda channel_id: runs)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            report = authenticity.evaluate_authenticity(
                DAY_221,
                "tapin",
                fact_count=5,
                series=authenticity.series_key("GTA 6: 18 days to launch"),
            )
            plain = authenticity.evaluate_authenticity(DAY_221, "tapin", fact_count=5)
        self.assertTrue(next(c for c in report.checks if c.name == "variation").passed)
        self.assertFalse(next(c for c in plain.checks if c.name == "variation").passed)

    def test_a_held_countdown_is_read_again_against_its_series(self):
        from core import batch_review

        draft = SimpleNamespace(run_id=221, script=DAY_221, meta={
            "series": "countdown", "channel_id": "tapin", "authenticity_verdict": "review",
            "authenticity_failed": ["variation"]})  # fmt: skip
        with patch("core.authenticity.series_variation_passes", return_value=True) as read:
            self.assertEqual(batch_review.authenticity_now(draft), ("ok", ""))
        read.assert_called_once()
        draft.meta["series"] = ""
        with patch("core.authenticity.series_variation_passes", return_value=True):
            self.assertEqual(batch_review.authenticity_now(draft)[0], "review")


# ---- #1749: both editions ------------------------------------------------------------------------


def _tag(**env):
    base = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AFFILIATE_AMAZON_TAG", "AFFILIATE_AMAZON_TAGS")
    }
    return patch.dict(os.environ, {**base, **env}, clear=True)


class EditionTests(unittest.TestCase):
    def test_a_gta_long_video_links_standard_and_ultimate(self):
        from core.description_extras import affiliate_lines

        with _tag(AFFILIATE_AMAZON_TAG="main-20"):
            lines = affiliate_lines(
                "tapin", "GTA 6 - everything we know before launch", long_form=True
            )
        self.assertEqual(len(lines), 3, lines)  # two links and the FTC line
        self.assertIn("Standard Edition", lines[0])
        self.assertIn("Ultimate Edition", lines[1])
        self.assertTrue(all("tag=main-20" in line for line in lines[:2]))

    def test_another_long_video_still_takes_one(self):
        from core.description_extras import affiliate_lines

        rows = [{"keys": ["ps5"], "url": "https://www.amazon.com/s?k=PS5", "label": "PS5"},
                {"keys": ["ps5"], "url": "https://www.amazon.com/s?k=PS5+Pro", "label": "PS5 Pro"}]  # fmt: skip
        with (
            _tag(AFFILIATE_AMAZON_TAG="main-20"),
            patch("core.description_extras.affiliate_rows", return_value=rows),
        ):
            lines = affiliate_lines("tapin", "The PS5 at six", long_form=True)
        self.assertEqual(len([line for line in lines if "amazon" in line]), 1)


# ---- #1741: the long description -----------------------------------------------------------------


class LongDescriptionTests(unittest.TestCase):
    def _prompt(self, length_choice):
        from core.content_engine import _build_prompts

        return _build_prompts(topic="GTA 6 - everything we know before launch", signals={}, min_words=1400,
                              max_words=1800, today="2026-11-06", channel_id="tapin", script_brief="",
                              seo_block="", signal_facts="", signal_summary="", brief_block="",
                              length_choice=length_choice)[1]  # fmt: skip

    def test_a_long_prompt_asks_a_150_to_250_word_summary(self):
        self.assertIn("150-250 words", self._prompt("4"))
        self.assertNotIn("150-250 words", self._prompt("1"))

    def test_a_long_descriptions_first_line_is_its_title(self):
        from core.description_extras import apply_description_extras

        title = "GTA 6 Release Date: Everything We Know Before Launch"
        body = "Rockstar's biggest launch is 13 days out.\n\nWhat we cover."
        long_text = apply_description_extras(body, "tapin", title=title, length_choice="4")
        short_text = apply_description_extras(body, "tapin", title=title, length_choice="1")
        self.assertEqual(long_text.splitlines()[0], title)
        self.assertEqual(short_text.splitlines()[0], "Rockstar's biggest launch is 13 days out.")


# ---- #1764: no gambling link, ever ------------------------------------------------------------------


class GamblingTests(unittest.TestCase):
    def test_a_sportsbook_row_is_refused_whatever_the_settings(self):
        from core import description_extras

        rows = {"tapin": [
            {"keys": ["nfl"], "url": "https://sportsbook.draftkings.com/?ref=x", "label": "Bet the NFL"},
            {"keys": ["nfl"], "url": "https://www.prizepicks.com/r/x", "label": "Picks app"},
            {"keys": ["nfl"], "url": "https://www.fanatics.com/nfl/jerseys", "label": "NFL jerseys"},
            {"keys": ["nfl"], "url": "https://sportsbook.fanatics.com/", "label": "Fanatics"},
        ]}  # fmt: skip
        with (
            patch.dict(os.environ, {"GAMBLING_SAFE": "false"}),
            patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(rows))),
        ):
            kept = description_extras.affiliate_rows("tapin")
        self.assertEqual([r["label"] for r in kept], ["NFL jerseys"])

    def test_a_sportsbook_link_leaves_the_description(self):
        from core.odds_language import strip_gambling_links

        text = ("Chiefs at Bills preview.\nClaim your bonus: https://www.fanduel.com/promo\n"
                "Sources:\nhttps://www.espn.com/nfl/story")  # fmt: skip
        with patch.dict(os.environ, {"GAMBLING_SAFE": "false"}):
            cleaned, removed = strip_gambling_links(text)
        self.assertEqual(removed, 1)
        self.assertNotIn("fanduel", cleaned)
        self.assertIn("espn.com", cleaned)

    def test_the_description_extras_strip_it(self):
        from core.description_extras import apply_description_extras

        text = apply_description_extras("Chiefs at Bills.\nhttps://sportsbook.draftkings.com/x", "tapin",
                                        title="Chiefs at Bills", length_choice="1")  # fmt: skip
        self.assertNotIn("draftkings", text)

    def test_the_config_holds_no_gambling_row(self):
        from core.description_extras import _AFFILIATES_FILE
        from core.odds_language import is_gambling_link

        with open(_AFFILIATES_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        rows = [r for key, value in data.items() if isinstance(value, list) for r in value]
        self.assertEqual([r for r in rows if is_gambling_link(r["url"], r.get("label", ""))], [])


if __name__ == "__main__":
    unittest.main()
