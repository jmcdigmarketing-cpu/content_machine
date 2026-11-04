"""Wave 147 (2026-11-04) - the next five, S01 (long-form hours) the shortfall it takes.

#1982 a name keeps its number ("GTA 6", not "GTA") in a compilation title and a hashtag; #1983 an
older video's synced window is refreshed in turn (run 170's views froze at 325 of 37,602); #1746
the hours lane's number, YouTube's own qualified hours a week; #1736 playlists play newest first
and long videos play into each other; #1722 a numbered UFC card's recap the night after, from
ESPN's results.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Imported before any patch below: a module first imported under a patch of a name it imports
# binds the mock for the rest of the process (wave 145's reversed-suite failure).
import analytics.sync_metrics
import analytics.youtube_metrics
import apis.topic_tokens
import assets.clip_ingest
import core.batch_generation
import core.best_bet
import core.playlists
import core.series.countdown
import core.series.dated
import core.success.bridge
import core.ypp_readiness
import publishing.platform_captions
import publishing.youtube_publisher
import sports.espn
import video.week_compile

UTC = timezone.utc
RUN191 = "GTA 6 online mode may repeat GTA Online's early mistakes"


# ---- #1982: a name keeps its number ----------------------------------------------------------------


class NameNumberTests(unittest.TestCase):
    def test_a_franchise_keeps_its_number(self):
        from apis.topic_tokens import phrase_with_number

        self.assertEqual(phrase_with_number("GTA", RUN191), "GTA 6")
        self.assertEqual(phrase_with_number("UFC", "UFC 334: Gane vs. Hokit"), "UFC 334")
        self.assertEqual(phrase_with_number("Chiefs", "Chiefs 2026 schedule leaks"), "Chiefs")
        self.assertEqual(phrase_with_number("Knicks", "Knicks beat the Heat"), "Knicks")

    def test_run191s_title_names_gta_6(self):
        from video.week_compile import compilation_title, subject_name

        self.assertEqual(subject_name(RUN191, []), "GTA 6")
        items = [{"title": RUN191, "names": [], "views": 1091}]
        self.assertTrue(
            compilation_title("TapIn", items, "", label="Best of October 2026").startswith(
                "GTA 6 -"
            )
        )

    def test_the_hashtag_keeps_it_too(self):
        run = SimpleNamespace(title=RUN191, input_topic=RUN191, selected_topic="", tags_json="[]")
        self.assertIn("#GTA6", publishing.platform_captions.tiktok_tags("tapin", run))


# ---- #1983: an older video's window refreshed in turn -----------------------------------------------


def _video(i: int, days_ago: float, synced_days_ago: float | None, privacy: str = "public"):
    now = datetime.now(UTC)
    metrics = {}
    if synced_days_ago is not None:
        metrics["period_end"] = (now - timedelta(days=synced_days_ago)).date().isoformat()
    return SimpleNamespace(id=i, content_run_id=i, published_at=now - timedelta(days=days_ago),
                           metrics_json=json.dumps(metrics), privacy_status=privacy)  # fmt: skip


class StaleWindowTests(unittest.TestCase):
    def test_a_stale_older_video_is_refreshed(self):
        rows = [_video(1, 2, 0), _video(2, 20, 12), _video(3, 25, 3), _video(4, 40, None),
                _video(5, 30, 15, privacy="gone")]  # fmt: skip
        with patch.dict(os.environ, {"SYNC_YOUNG_DAYS": "", "SYNC_STALE_PER_RUN": ""}):
            picked = [r.id for r in analytics.sync_metrics._to_sync(rows, 1)]
        self.assertEqual(picked, [1, 2])  # not the fresh one, the never-synced or the deleted

    def test_the_newest_stale_first_and_a_cap(self):
        rows = [_video(1, 1, 0), *(_video(10 + d, 10 + d, 9) for d in range(6))]
        with patch.dict(os.environ, {"SYNC_YOUNG_DAYS": "", "SYNC_STALE_PER_RUN": "3"}):
            picked = [r.id for r in analytics.sync_metrics._to_sync(rows, 1)]
        self.assertEqual(picked, [1, 10, 11, 12])

    def test_it_can_be_switched_off(self):
        rows = [_video(1, 1, 0), _video(2, 20, 12)]
        with patch.dict(os.environ, {"SYNC_YOUNG_DAYS": "", "SYNC_STALE_PER_RUN": "0"}):
            self.assertEqual([r.id for r in analytics.sync_metrics._to_sync(rows, 1)], [1])


# ---- #1746: the hours lane's number -----------------------------------------------------------------


class HoursLaneTests(unittest.TestCase):
    def test_the_sync_asks_the_last_7_days_without_ads(self):
        def by_source(_service, start, end, metric):
            days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
            if metric == "estimatedMinutesWatched" and days == 7:
                return {("YT_SEARCH", "videoondemand"): 3.0, ("ADVERTISING", "videoondemand"): 600.0,
                        ("SHORTS", "shorts"): 900.0}  # fmt: skip
            return {}

        ym = analytics.youtube_metrics
        with (
            patch.object(ym, "_analytics_enabled", return_value=True),
            patch.object(ym, "get_youtube_analytics_service", return_value=object()),
            patch.object(ym, "_by_source_and_type", side_effect=by_source),
            patch.object(ym, "_subscriber_count", return_value=189),
            patch.object(ym, "youtube_channel_id", return_value=""),
            patch.object(ym, "_subscriber_change", return_value=None),
            patch.object(ym, "_subscriber_flow", return_value=None),
        ):
            numbers = ym.fetch_ypp_numbers(channel_id="tapin", today=datetime(2026, 11, 4).date())
        self.assertEqual(numbers["long_hours_7d"], 0.05)

    def test_each_week_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ypp_{channel}.json")
            with patch.object(core.ypp_readiness, "YPP_TEMPLATE", path):
                core.ypp_readiness.save_ypp_numbers(
                    "tapin", {"as_of": "2026-11-04", "long_hours_7d": 0.05}
                )
                core.ypp_readiness.save_ypp_numbers(
                    "tapin", {"as_of": "2026-11-12", "long_hours_7d": 2.5}
                )
                core.ypp_readiness.save_ypp_numbers(
                    "tapin", {"as_of": "2026-11-13", "long_hours_7d": 3.0}
                )
                stored = core.ypp_readiness.load_ypp_numbers("tapin")
        self.assertEqual(stored["weeks"], {"2026-W45": 0.05, "2026-W46": 3.0})
        self.assertIn("2026-11", stored["history"])

    def test_done_at_ten_a_week_for_four_weeks_running(self):
        from core.ypp_readiness import hours_lane

        weeks = {"2026-W44": 11, "2026-W45": 9, "2026-W46": 12, "2026-W47": 12.4}
        self.assertEqual(hours_lane({"long_hours_7d": 12.4, "weeks": weeks})["run"], 2)
        weeks["2026-W45"] = 10
        lane = hours_lane({"long_hours_7d": 12.4, "weeks": weeks})
        self.assertEqual((lane["run"], lane["done"]), (4, True))
        self.assertIsNone(hours_lane({"long_hours_365d": 10.7}))

    def test_the_line_in_ops_ypp_and_the_scoreboard(self):
        from core.ypp_readiness import hours_lane_line, path_lines

        numbers = {"long_hours_7d": 0.05, "long_hours_365d": 10.7, "shorts_views_28d": 7000,
                   "pace_days": 28}  # fmt: skip
        line = hours_lane_line(numbers)
        self.assertIn("0.05 qualified long-form hours in the last 7 days", line)
        self.assertIn("0 of 4 weeks running at 10", line)
        self.assertIn(f"  {line}", path_lines(numbers))
        board = core.success.bridge.scoreboard_lines("tapin", numbers=numbers, entries=[])
        self.assertIn(f"  {line}", board)
        self.assertEqual(hours_lane_line({}), "")


# ---- #1736: playlists for binge-watching ------------------------------------------------------------


class BingePlaylistTests(unittest.TestCase):
    def _add(self, service, title: str, **kwargs) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "playlists.json")
            with open(store, "w", encoding="utf-8") as handle:
                json.dump({"ids": {"GTA": "PL1", "Gaming": "PL2", "Full Videos": "PL3"}}, handle)
            with patch("youtube.oauth.token_has_scope", return_value=True):
                note = core.playlists.add_to_playlists(service, "tapin", "vid", title=title,
                                                       store_path=store, **kwargs)  # fmt: skip
            with open(store, encoding="utf-8") as handle:
                self.stored = json.load(handle)
        return note

    @staticmethod
    def _bodies(service) -> list[dict]:
        return [c.kwargs["body"]["snippet"] for c in service.playlistItems().insert.call_args_list]

    def test_a_new_video_goes_in_at_the_top(self):
        service = MagicMock()
        self._add(service, "GTA 6 leaks a map")
        self.assertEqual([(b["playlistId"], b["position"]) for b in self._bodies(service)],
                         [("PL1", 0), ("PL2", 0)])  # fmt: skip

    def test_a_long_video_joins_the_long_videos_at_the_top(self):
        service = MagicMock()
        note = self._add(service, "GTA 6 editions explained", long_form=True)
        self.assertEqual([b["playlistId"] for b in self._bodies(service)], ["PL3", "PL1", "PL2"])
        self.assertIn("added to Full Videos", note)
        self.assertEqual(self.stored["added"]["vid"], ["Full Videos", "GTA", "Gaming"])

    def test_a_playlist_that_refuses_the_top_takes_it_at_the_end(self):
        service = MagicMock()
        service.playlistItems().insert().execute.side_effect = [RuntimeError("manualSortRequired"),
                                                                {}, {}]  # fmt: skip
        service.playlistItems().insert.reset_mock()
        note = self._add(service, "GTA 6 leaks a map")
        bodies = self._bodies(service)
        self.assertEqual(len(bodies), 3)
        self.assertNotIn("position", bodies[1])  # the retry: no position
        self.assertEqual(note, "added to GTA; added to Gaming")

    def test_the_long_videos_row_is_not_a_niche(self):
        self.assertEqual(core.playlists.long_playlists("tapin"), ["Full Videos"])
        self.assertEqual(core.playlists.playlists_for("tapin", "Full Videos of the week"), [])
        with tempfile.TemporaryDirectory() as tmp:
            niches = [
                r["niche"] for r in assets.clip_ingest.footage_coverage("tapin", library_root=tmp)
            ]
        self.assertNotIn("Full Videos", niches)

    def test_a_long_video_is_told_by_its_length(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name
        try:
            with patch("video.channel_intro._probe_duration", return_value=394.0):
                self.assertTrue(core.playlists.is_long_video(path))
            with patch("video.channel_intro._probe_duration", return_value=58.0):
                self.assertFalse(core.playlists.is_long_video(path))
        finally:
            os.remove(path)
        self.assertFalse(core.playlists.is_long_video("missing.mp4"))

    def test_the_publisher_says_which_it_is(self):
        request = SimpleNamespace(title="GTA 6 editions explained", tags=[], file_path="long.mp4",
                                  caption_path=None)  # fmt: skip
        with (
            patch("core.playlists.is_long_video", return_value=True),
            patch("core.playlists.add_to_playlists", return_value="") as add,
            patch("youtube.captions.maybe_upload_captions"),
            patch("youtube.pin_comment.maybe_pin_top_answer"),
        ):
            publishing.youtube_publisher._post_upload_extras(
                MagicMock(), "vid", request, channel_id="tapin"
            )
        self.assertTrue(add.call_args.kwargs["long_form"])


# ---- #1722: the UFC recap ---------------------------------------------------------------------------

CARD_START = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)  # UFC 334: Sat Nov 14, 8 PM ET
CALENDAR = [{"label": "UFC Fight Night: Cortes Acosta vs. Walker", "startDate": "2026-11-07T22:00Z"},
            {"label": "UFC 334: Gane vs. Hokit", "startDate": "2026-11-15T01:00Z"}]  # fmt: skip
BOARD = {"leagues": [{"calendar": CALENDAR}], "events": []}


def _bout(winner: str, loser: str, weight: str, rnd: int, clock: str, rounds: int = 3,
          done: bool = True, draw: bool = False) -> dict:  # fmt: skip
    return {
        "type": {"abbreviation": weight},
        "format": {"regulation": {"periods": rounds}},
        "status": {"period": rnd, "displayClock": clock, "type": {"completed": done}},
        "competitors": [
            {"winner": not draw, "athlete": {"displayName": winner}},
            {"winner": False, "athlete": {"displayName": loser}},
        ],
    }


def _event(*bouts: dict) -> dict:
    return {"name": "UFC 334: Gane vs. Hokit", "competitions": list(bouts)}


EVENT = _event(
    _bout("Iasmin Lucindo", "Nicolle Caliari", "W Strawweight", 3, "5:00"),
    _bout("Petr Yan", "Merab Dvalishvili", "Bantamweight", 5, "5:00", rounds=5),
    _bout("Ciryl Gane", "Josh Hokit", "Heavyweight", 2, "4:54", rounds=5),
)


def _recap():
    """The recap module, imported per test - it is new this wave, so HEAD fails test by test.
    It imports nothing by name at module level, so a later import binds no patch."""
    from core.series import recap

    return recap


class UfcRecapTests(unittest.TestCase):
    def test_the_card_that_ended_overnight(self):
        from core.series.recap import finished_card

        self.assertEqual(finished_card(CALENDAR, now=CARD_START + timedelta(hours=10)),
                         ("UFC 334: Gane vs. Hokit", CARD_START))  # fmt: skip
        self.assertIsNone(finished_card(CALENDAR, now=CARD_START + timedelta(hours=1)))
        self.assertIsNone(finished_card(CALENDAR, now=CARD_START + timedelta(hours=40)))
        fight_night = datetime(2026, 11, 8, 8, tzinfo=UTC)
        self.assertIsNone(finished_card(CALENDAR, now=fight_night))  # not a numbered card

    def test_every_result_the_main_event_first(self):
        from core.series.recap import bout_lines

        self.assertEqual(bout_lines(EVENT), [
            "Main event (Heavyweight): Ciryl Gane beat Josh Hokit - a finish in round 2 at 4:54.",
            "Co-main event (Bantamweight): Petr Yan beat Merab Dvalishvili on the scorecards "
            "after 5 rounds.",
            "Women's Strawweight bout: Iasmin Lucindo beat Nicolle Caliari on the scorecards "
            "after 3 rounds.",
        ])  # fmt: skip

    def test_not_while_a_bout_is_unfinished_and_a_draw_is_said(self):
        from core.series.recap import bout_lines

        self.assertIsNone(bout_lines(_event(_bout("A", "B", "Flyweight", 1, "2:00", done=False))))
        self.assertIsNone(bout_lines(_event()))
        self.assertEqual(bout_lines(_event(_bout("A", "B", "Flyweight", 3, "5:00", draw=True))),
                         ["Main event (Flyweight): A and B - no winner (a draw or a no contest)."])  # fmt: skip

    def test_the_cards_us_evening_is_asked(self):
        from core.series.recap import card_results

        asked: list[str] = []

        def fetch(league, *, dates):
            asked.append(dates)
            return {"events": [EVENT]}

        lines = card_results("UFC 334: Gane vs. Hokit", CARD_START, fetch=fetch)
        self.assertEqual(asked, ["20261114"])
        self.assertEqual(len(lines), 3)

    def test_one_long_recap_written_from_the_results(self):
        headlines = [{"title": "UFC 334 results: Gane stops Hokit", "source": "MMA Junkie",
                      "published": CARD_START + timedelta(hours=6)}]  # fmt: skip
        with (
            patch.dict(os.environ, {"UFC_RECAP": "true"}),
            patch.object(core.batch_generation, "series_drafted", return_value=False),
        ):
            ideas = _recap().recap_ideas(
                "tapin", now=CARD_START + timedelta(hours=10), board=BOARD,
                fetch=lambda *_a, **_k: {"events": [EVENT]}, headlines=lambda *_a: headlines,
            )  # fmt: skip
        self.assertEqual(len(ideas), 1)
        idea = ideas[0]
        self.assertEqual(idea.topic, "UFC 334 recap: every finish and what's next")
        self.assertEqual((idea.source, idea.draft_kind, idea.domain), ("long", "long", "ufc"))
        self.assertEqual(idea.facts[0], "UFC 334: Gane vs. Hokit was held on Saturday, November "
                                        "14, 2026 (ESPN's results).")  # fmt: skip
        self.assertIn("MMA Junkie reported: UFC 334 results: Gane stops Hokit", idea.facts)
        self.assertIn("started 10 hours ago", idea.rationale)

    def test_it_waits_once_drafted_unfinished_or_off(self):
        unfinished = _event(_bout("A", "B", "Flyweight", 1, "2:00", done=False))
        notes: list[str] = []
        later = CARD_START + timedelta(hours=10)
        with (
            patch.dict(os.environ, {"UFC_RECAP": "true"}),
            patch.object(core.batch_generation, "series_drafted", return_value=False),
        ):
            self.assertEqual(_recap().recap_ideas(
                "tapin", now=later, board=BOARD, fetch=lambda *_a, **_k: {"events": [unfinished]},
                headlines=lambda *_a: [], notes=notes), [])  # fmt: skip
        self.assertIn("ESPN does not show every UFC 334 bout final yet", notes[0])
        with (
            patch.dict(os.environ, {"UFC_RECAP": "true"}),
            patch.object(core.batch_generation, "series_drafted", return_value=True),
        ):
            self.assertEqual(_recap().recap_ideas("tapin", now=later, board=BOARD), [])
        fetch = MagicMock()
        self.assertEqual(_recap().recap_ideas("tapin", now=later, fetch=fetch), [])
        fetch.assert_not_called()  # the suite pins UFC_RECAP off

    def test_espn_is_asked_for_the_day(self):
        with patch.object(sports.espn, "_get", return_value={}) as get:
            sports.espn.get_scoreboard("ufc", dates="20261114")
            sports.espn.get_scoreboard("ufc")
        self.assertEqual(get.call_args_list[0].args[1], {"dates": "20261114"})
        self.assertIsNone(get.call_args_list[1].args[1])

    def test_the_night_drafts_it_even_with_drafts_waiting(self):
        bet = core.best_bet.BestBetResult(topic="UFC 334 recap: every finish and what's next",
                                          domain="ufc", avg_engaged_rate=0.0, source="long",
                                          supporting_runs=0, rationale="r", draft_kind="long")  # fmt: skip
        with (
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.dated.dated_ideas", return_value=[]),
            patch.object(core.batch_generation, "long_breakout_ideas", return_value=[]),
            patch("core.series.recap.recap_ideas", return_value=[bet]),
        ):
            picks: dict = {}
            topics = core.batch_generation.collect_topics("tapin", count=0, picks=picks)
        self.assertEqual(topics, [bet.topic])
        self.assertEqual(picks[bet.topic]["draft_kind"], "long")


if __name__ == "__main__":
    unittest.main()
