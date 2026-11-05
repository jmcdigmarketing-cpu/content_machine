"""Wave 144 (2026-11-01) - the next 15 (decision 96), S02 the shortfall it takes.

#1943 + #1729 a trending Short ends on its subject's long video, its series or the Monday Week in
Review; #1707 a subscribe link; #1716 the subscriber pace in `ops status`; #1726 keyword chapter
titles; #1733 each long video's drop-off; #1734 a long video's payoff promised early; #1742 its
tags carry the search terms; #1852 the GTA 6 editions video; #1876 the trade-deadline fast lane;
#1878 The Game Awards; #1871 the GTA window's number; #1960 the same fight never drafted twice;
#1858 a leak never titled as fact; #1954 recategorize by run.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

UTC = timezone.utc


def _tag(**env):
    base = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AFFILIATE_AMAZON_TAG", "AFFILIATE_AMAZON_TAGS")
    }
    return patch.dict(os.environ, {**base, **env}, clear=True)


# ---- #1716: the subscriber pace in ops status ----------------------------------------------------


PACE_NUMBERS = {"subscribers": 189, "subs_net_28d": 143, "pace_days": 28, "shorts_paid_90d": 44114,
                "shorts_views_28d": 1430 * 4}  # fmt: skip


class PaceTests(unittest.TestCase):
    def test_the_pace_line_with_the_videos_own_pace(self):
        from core import ypp_readiness

        with (
            patch.object(ypp_readiness, "load_ypp_numbers", return_value=PACE_NUMBERS),
            patch.object(
                ypp_readiness, "_video_subscribers", return_value={"total": 4, "videos": 91}
            ),
        ):
            line = ypp_readiness.subscriber_pace_line("tapin")
        self.assertIn("811 to go is", line)
        self.assertIn("On the videos alone", line)

    def test_nothing_before_the_numbers_are_stored(self):
        from core import ypp_readiness

        with patch.object(ypp_readiness, "load_ypp_numbers", return_value=None):
            self.assertEqual(ypp_readiness.subscriber_pace_line("tapin"), "")


# ---- #1852, #1876, #1878: the calendar ---------------------------------------------------------------


def _ideas(now, headlines=()):
    from core.series.dated import dated_ideas

    notes: list[str] = []
    with (
        patch.dict(os.environ, {"SERIES_DATED": "true"}),  # the suite switches it off
        patch("core.batch_generation.series_drafted", return_value=False),
    ):
        found = dated_ideas(
            "tapin", now=now, headlines=lambda c, r, n: list(headlines), notes=notes
        )
    return found, notes


class CalendarTests(unittest.TestCase):
    def test_the_editions_video_is_drafted_on_nov_9_with_both_links(self):
        from core.description_extras import affiliate_lines

        found, _notes = _ideas(datetime(2026, 11, 9, 15, tzinfo=UTC))
        editions = [b for b in found if "editions" in b.topic.lower()]
        self.assertEqual(len(editions), 1)
        self.assertEqual(editions[0].draft_kind, "long")
        with _tag(AFFILIATE_AMAZON_TAG="main-20"):
            lines = affiliate_lines("tapin", "GTA 6 Editions and Price: Which to Buy", editions[0].topic,
                                    long_form=True)  # fmt: skip
        self.assertEqual(len([line for line in lines if "amazon.com" in line]), 2)

    def test_the_trade_deadline_jumps_the_queue_nov_9_to_11(self):
        from core.series.dated import jump_first, launch_names

        names = launch_names("tapin", "2026-11-10")
        self.assertTrue(any("trade deadline" in n.lower() for n in names), names)
        self.assertFalse(
            any("trade deadline" in n.lower() for n in launch_names("tapin", "2026-11-12"))
        )
        ideas = [SimpleNamespace(topic="Lakers beat Warriors", source="trending", outlets=6),
                 SimpleNamespace(topic="Steelers acquire a receiver: Pickens traded to Dallas at the "
                                       "trade deadline", source="trending", outlets=5)]  # fmt: skip
        self.assertIn("traded to", jump_first(ideas, names)[0].topic)

    def test_the_game_awards_winners_on_dec_11_when_the_week_names_them(self):
        night = datetime(2026, 12, 11, 15, tzinfo=UTC)
        said = [{"title": "The Game Awards 2026 winners: Game of the Year goes to ...", "source": "IGN",
                 "published": night - timedelta(hours=10)}]  # fmt: skip
        found, _notes = _ideas(night, said)
        self.assertTrue([b for b in found if "Game Awards" in b.topic])
        quiet, notes = _ideas(night, [])
        self.assertFalse([b for b in quiet if "Game Awards" in b.topic])
        self.assertTrue([n for n in notes if "Game Awards" in n])


# ---- #1734, #1742, #1726: long videos ------------------------------------------------------------------


def _prompt(length_choice):
    from core.content_engine import _build_prompts

    return _build_prompts(topic="GTA 6 - everything we know before launch", signals={}, min_words=1400,
                          max_words=1800, today="2026-11-06", channel_id="tapin", script_brief="",
                          seo_block="", signal_facts="", signal_summary="", brief_block="",
                          length_choice=length_choice)[1]  # fmt: skip


SCRIPT = " ".join([
    "GTA 6 is the biggest launch of the decade.",
    "Rockstar has been quiet for months.",
    "The release date is November 19 on PS5 and Xbox Series X.",
    "That date has held through two delays.",
    "Pre-orders opened in June.",
    "The map is twice the size of Los Santos.",
    "Vice City is back with the Keys around it.",
    "Fuel and smell systems fill the world.",
    "The price is 79.99 for the Standard Edition.",
    "The Ultimate Edition costs 99.99.",
    "Both include the Vintage Vice City Pack.",
    "Watch the first week of streams.",
])  # fmt: skip


class LongVideoTests(unittest.TestCase):
    def test_a_long_prompt_promises_the_payoff_in_the_first_40_words(self):
        self.assertIn("first 40 words", _prompt("4"))
        self.assertNotIn("first 40 words", _prompt("1"))

    def test_a_long_drafts_tags_carry_the_search_terms(self):
        from core.series.long_form import long_tags

        tags = long_tags("tapin", "GTA 6 - everything we know before launch", ["gta 6", "rockstar"])
        self.assertIn("GTA 6 release date", tags)
        self.assertIn("GTA 6 price", tags)
        self.assertEqual([t.lower() for t in tags].count("gta 6"), 1)
        self.assertEqual(long_tags("tapin", "Lakers beat Warriors", ["nba"]), ["nba"])

    def test_a_chapter_naming_a_search_term_is_titled_by_it(self):
        from core.chapters import chapter_block

        keywords = [("release date", "GTA 6 Release Date"), ("price", "GTA 6 Price")]
        block = chapter_block(SCRIPT, duration=600, length_choice="4", keywords=keywords)
        self.assertIn("GTA 6 Release Date", block)
        self.assertIn("GTA 6 Price", block)
        plain = chapter_block(SCRIPT, duration=600, length_choice="4")
        self.assertNotIn("GTA 6 Release Date", plain)

    def test_the_row_gives_the_keywords_and_the_description_uses_them(self):
        from core.description_extras import apply_description_extras
        from core.series.long_form import chapter_keywords

        pairs = chapter_keywords("tapin", "GTA 6 - everything we know before launch")
        self.assertIn(("release date", "GTA 6 Release Date"), pairs)
        text = apply_description_extras("Everything we know.", "tapin", title="GTA 6 Release Date",
                                        topic="GTA 6 - everything we know before launch",
                                        length_choice="4", script=SCRIPT, duration_s=600)  # fmt: skip
        self.assertIn("GTA 6 Release Date", text.split("0:00", 1)[-1])


# ---- #1733: each long video's drop-off ---------------------------------------------------------------


class LongDropOffTests(unittest.TestCase):
    def _lines(self, metrics):
        from core import retention

        row = SimpleNamespace(content_run_id=202, youtube_video_id="v202")
        run = SimpleNamespace(id=202, title="Week in Review", mp4_path="",
                              features_json=json.dumps({"technical_qc": {"video_duration": 700}}))  # fmt: skip
        with (
            patch("core.success.scorecard._long_rows", return_value=[(row, metrics)]),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(get=lambda run_id: run),
            ),
        ):
            return retention.long_drop_off_lines("tapin")

    def test_a_curve_gives_the_minute(self):
        lines = self._lines({"views": 300, "retention_curve": [[0.0, 1.0], [0.2, 0.7], [0.3, 0.4]]})
        self.assertIn("half gone at 3:30 of 11:40", lines[0])

    def test_no_curve_says_so(self):
        self.assertIn("no retention yet (4 views)", self._lines({"views": 4})[0])


# ---- #1871: the GTA window's number --------------------------------------------------------------


class WindowTests(unittest.TestCase):
    def test_gta_6_against_everything_else(self):
        from core.success import scorecard

        day = datetime(2026, 11, 2, tzinfo=UTC)
        rows = [
            {"title": "GTA 6: 19 days to launch", "published": day, "views": 400, "paid": 0, "run_id": 1},
            {"title": "GTA 6's Massive Map", "published": day, "views": 250, "paid": 50, "run_id": 2},
            {"title": "Lakers beat Warriors", "published": day, "views": 120, "paid": 0, "run_id": 3},
            {"title": "GTA 6 old news", "published": datetime(2026, 10, 1, tzinfo=UTC), "views": 900,
             "paid": 0, "run_id": 4},
        ]  # fmt: skip
        with (
            patch("analytics.growth._rows", return_value=rows),
            patch.object(scorecard, "_long_rows", return_value=[]),
        ):
            line = scorecard.window_line("tapin", now=datetime(2026, 11, 3, tzinfo=UTC))
        self.assertIn("GTA 6 600 organic views from 2 videos", line)
        self.assertIn("everything else 120 from 1", line)


# ---- #1960: the same fight twice ---------------------------------------------------------------------


class MatchupTests(unittest.TestCase):
    def test_the_same_fight_in_other_words_is_drafted(self):
        from core.best_bet import same_matchup

        drafted = ["Main Card Results | UFC Fight Night: Moicano vs Nolan"]
        self.assertEqual(
            same_matchup("UFC Vegas 123 Results: Moicano vs. Nolan", drafted), drafted[0]
        )
        self.assertEqual(same_matchup("Moicano vs Topuria booked for March", drafted), "")
        self.assertTrue(
            same_matchup("Bills vs Chiefs preview", ["Kansas City Chiefs at Buffalo Bills"])
        )

    def test_the_menu_drops_it(self):
        from core.best_bet import BestBetResult, drop_drafted_matchups

        ideas = [BestBetResult(topic="UFC Vegas 123 Results: Moicano vs. Nolan", domain="ufc",
                               avg_engaged_rate=0.0, source="trending", supporting_runs=0, rationale=""),
                 BestBetResult(topic="GTA 6: 18 days to launch", domain="gaming", avg_engaged_rate=0.0,
                               source="countdown", supporting_runs=0, rationale="")]  # fmt: skip
        notes: list[str] = []
        kept = drop_drafted_matchups(ideas, ["Main Card Results | UFC Fight Night: Moicano vs Nolan"],
                                     notes=notes)  # fmt: skip
        self.assertEqual([b.topic for b in kept], ["GTA 6: 18 days to launch"])
        self.assertIn("Moicano", notes[0])


# ---- #1858: a leak never titled as fact -------------------------------------------------------------


class LeakTitleTests(unittest.TestCase):
    LEAK = ("GTA 6 is 18 days out. Leakers say GTA 6 has a smell reaction system for every NPC. "
            "Rockstar has not confirmed it.")  # fmt: skip

    def test_a_leaked_claim_in_the_title_warns(self):
        from core.youtube_meta import leak_as_fact

        self.assertTrue(leak_as_fact("GTA 6 Has a Smell Reaction System for Every NPC", self.LEAK))

    def test_a_title_that_says_leak_or_asks_does_not(self):
        from core.youtube_meta import leak_as_fact

        self.assertEqual(
            leak_as_fact("GTA 6 Leak: A Smell Reaction System for Every NPC", self.LEAK), ""
        )
        self.assertEqual(leak_as_fact("Does GTA 6 Have a Smell Reaction System?", self.LEAK), "")
        self.assertEqual(
            leak_as_fact("GTA 6's Massive Map: Bigger Doesn't Mean Better", self.LEAK), ""
        )


# ---- #1707: a subscribe link ---------------------------------------------------------------------------


class _Channels:
    def __init__(self, answer):
        self.answer = answer
        self.asked: dict = {}

    def channels(self):
        return self

    def list(self, **kw):
        self.asked = kw
        return self

    def execute(self):
        return self.answer


class SubscribeTests(unittest.TestCase):
    def test_the_sync_keeps_the_channels_id(self):
        from analytics import youtube_metrics

        service = _Channels(
            {"items": [{"id": "UCabc123", "statistics": {"subscriberCount": "189"}}]}
        )
        with patch.object(youtube_metrics, "get_youtube_service", return_value=service):
            self.assertEqual(youtube_metrics._subscriber_count("tapin"), 189)
        self.assertIn("id", service.asked["fields"])
        self.assertEqual(youtube_metrics.youtube_channel_id("tapin"), "UCabc123")

    def test_a_long_description_and_the_pages_carry_the_link(self):
        from core.description_extras import apply_description_extras, subscribe_line

        with patch(
            "core.ypp_readiness.load_ypp_numbers", return_value={"youtube_channel_id": "UCabc123"}
        ):
            line = subscribe_line("tapin")
            long_text = apply_description_extras(
                "Body.", "tapin", title="A long one", length_choice="4"
            )
            short_text = apply_description_extras(
                "Body.", "tapin", title="A Short", length_choice="1"
            )
        self.assertEqual(
            line, "Subscribe: https://www.youtube.com/channel/UCabc123?sub_confirmation=1"
        )
        self.assertIn(line, long_text)
        self.assertNotIn("sub_confirmation", short_text)
        with patch("core.ypp_readiness.load_ypp_numbers", return_value={}):
            self.assertEqual(subscribe_line("tapin"), "")

    def test_the_link_pages_lead_with_it(self):
        from publishing import link_page

        empty = SimpleNamespace(list_uploaded_for_channel=lambda channel_id: [])
        with (
            _tag(),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository", return_value=empty
            ),
            patch(
                "core.ypp_readiness.load_ypp_numbers",
                return_value={"youtube_channel_id": "UCabc123"},
            ),
        ):
            page = link_page.links_html("TapIn", **link_page.collect("tapin", page="tiktok"))
        self.assertIn("sub_confirmation=1", page)
        self.assertLess(
            page.index("sub_confirmation"),
            page.index("</main>") if "</main>" in page else len(page),
        )


# ---- #1943 + #1729: a trending Short's reason to follow ----------------------------------------------


def _bet(topic):
    return {"offered": [{"topic": topic, "source": "trending"}], "picked": 1}


class TrendingFollowTests(unittest.TestCase):
    def test_a_public_long_video_on_the_subject_first(self):
        from core.batch_generation import follow_brief

        with patch("core.series.long_form.public_long_subject", return_value="GTA 6"):
            brief = follow_brief(_bet("GTA 6 trailer 3 lands this week"), today=date(2026, 11, 7))
        self.assertIn("The full GTA 6 breakdown is on the channel", brief)

    def test_else_the_subjects_running_countdown(self):
        from core.batch_generation import follow_brief

        with patch("core.series.long_form.public_long_subject", return_value=""):
            brief = follow_brief(_bet("GTA 6 trailer 3 lands this week"), today=date(2026, 11, 7))
        self.assertIn("countdown", brief)

    def test_else_the_weekly_week_in_review(self):
        from core.batch_generation import follow_brief

        with patch("core.series.long_form.public_long_subject", return_value=""):
            brief = follow_brief(
                _bet("Lakers beat Warriors behind Doncic"), today=date(2026, 11, 7)
            )
        self.assertIn("every Sunday", brief)  # #1727 (wave 149)

    def test_an_idea_of_your_own_gets_none(self):
        from core.batch_generation import follow_brief

        self.assertEqual(follow_brief(None, today=date(2026, 11, 7)), "")

    def test_the_subject_of_a_public_long_video(self):
        from core.series import long_form

        row = SimpleNamespace(content_run_id=230, privacy_status="public", youtube_video_id="vL")
        run = SimpleNamespace(id=230, input_topic="GTA 6 - everything we know before launch",
                              features_json=json.dumps({"long_form": True}))  # fmt: skip
        with (
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_uploaded_for_channel=lambda c: [row]),
            ),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(get=lambda run_id: run),
            ),
        ):
            self.assertEqual(
                long_form.public_long_subject("tapin", "GTA 6 trailer 3 lands"), "GTA 6"
            )
            self.assertEqual(long_form.public_long_subject("tapin", "Lakers beat Warriors"), "")


# ---- #1954: recategorize by run ----------------------------------------------------------------------


class RecategorizeTests(unittest.TestCase):
    def test_the_plan_holds_only_the_named_runs(self):
        from publishing import recategorize

        rows = [SimpleNamespace(youtube_video_id=f"v{r}", content_run_id=r) for r in (17, 120, 126)]
        repo = SimpleNamespace(list_uploaded_for_channel=lambda channel_id: rows)
        with patch.object(recategorize, "resolved_run_domain", return_value="gaming"):
            plan = recategorize.plan_recategorize("tapin", repo=repo, run_ids={120, 126})
        self.assertEqual([p.run_id for p in plan], [120, 126])
        self.assertTrue(all(p.category_id == "20" for p in plan))


if __name__ == "__main__":
    unittest.main()
