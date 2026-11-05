"""Wave 150 (2026-11-05) - the next five.

#1735 a long video spoken at 1.0x; #1993 a season explainer's title, tags and chapters from search;
#1670 + #1893 overnight's preview is a game 24-48 hours away, read from the next days' boards, so it
is drafted, rendered and in its slot a day ahead; #1608 a "more of what worked" idea each night.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

# Imported before any patch below: a module first imported under a patch of a name it imports
# binds the mock for the rest of the process (wave 145's reversed-suite failure).
import core.batch_generation
import core.best_bet
import core.seasonal_calendar
import core.series.long_form
import core.tts

UTC = timezone.utc


# ---- #1735: a long video at 1.0x ----------------------------------------------------------------


class LongPaceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TTS_SPEED": "", "TTS_SPEED_LONG": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_a_long_length_speaks_at_one(self):
        self.assertEqual(core.tts.speech_speed("tapin", length_choice="4"), 1.0)
        self.assertEqual(core.tts.speech_speed("tapin", length_choice="2"), 1.05)  # a Short
        self.assertEqual(core.tts.speech_speed("tapin"), 1.05)
        with patch.dict(os.environ, {"TTS_SPEED_LONG": "0.97"}):
            self.assertEqual(core.tts.speech_speed("tapin", length_choice="4"), 0.97)

    def test_the_synth_reads_the_renders_length(self):
        with core.tts.length_context("4"):
            self.assertEqual(core.tts.speech_speed("tapin"), 1.0)
        with core.tts.length_context("2"):
            self.assertEqual(core.tts.speech_speed("tapin"), 1.05)

    def test_long_is_over_three_minutes(self):
        self.assertTrue(core.tts.is_long_length("3"))
        self.assertTrue(core.tts.is_long_length("4"))
        self.assertFalse(core.tts.is_long_length("2"))
        self.assertFalse(core.tts.is_long_length(""))


# ---- #1993: a season explainer's title from search ------------------------------------------------

SEASON_ROW = {"id": "marvel-rivals-seasons", "kind": "season", "subject": "Marvel Rivals",
              "names": ["Marvel Rivals"], "domain": "gaming",
              "topic": "Everything in Marvel Rivals {season}",
              "search_terms": ["new heroes", "battle pass", "release date"]}  # fmt: skip
TOPIC = "Everything in Marvel Rivals Season 5"


class SeasonTitleTests(unittest.TestCase):
    def test_the_season_a_topic_fills_in(self):
        fill = core.series.long_form.season_in
        self.assertEqual(fill(SEASON_ROW["topic"], TOPIC), "Season 5")
        self.assertEqual(fill("Everything in Fortnite {season}",
                              "Everything in Fortnite Chapter 7 Season 1"), "Chapter 7 Season 1")  # fmt: skip
        self.assertEqual(fill(SEASON_ROW["topic"], "Everything in Fortnite Season 5"), "")
        self.assertEqual(fill("GTA 6 - everything we know", TOPIC), "")

    def test_its_title_carries_the_search_phrase(self):
        asked = []

        def suggest(query):
            asked.append(query)
            return ["marvel rivals season 5", "marvel rivals season 5 battle pass"]

        with (
            patch("core.series.long_form.series_rows", return_value=[SEASON_ROW]),
            patch("apis.autocomplete_api.youtube_suggestions", side_effect=suggest),
        ):
            title, found = core.series.long_form.long_title("tapin", TOPIC, "Every New Hero")
            tags = core.series.long_form.long_tags("tapin", TOPIC, [])
            chapters = core.series.long_form.chapter_keywords("tapin", TOPIC)
        self.assertEqual(asked[0], "Marvel Rivals season 5")
        self.assertTrue(title.startswith("Marvel Rivals Season 5"), title)
        self.assertIn("marvel rivals season 5", found)
        self.assertIn("Marvel Rivals season 5", tags)
        self.assertEqual(chapters[0], ("season 5", "Marvel Rivals Season 5"))

    def test_the_season_rows_carry_search_terms(self):
        from core.series.countdown import series_rows

        rows = [r for r in series_rows("tapin") if r.get("kind") == "season"]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r.get("search_terms") for r in rows))


# ---- #1670 / #1893: the preview a day ahead -----------------------------------------------------

NOW = datetime(2026, 11, 25, 5, tzinfo=UTC)


def _at(hours):
    return (NOW + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _preview(topic, kind="national"):
    return SimpleNamespace(topic=topic, kind=kind, source="schedule", outlets=0)


class AheadTests(unittest.TestCase):
    def _first(self, bets, starts):
        with patch.dict(core.seasonal_calendar._STARTS, starts, clear=True):
            return [b.topic for b in core.best_bet.ahead_first(bets, now=NOW)]

    def test_the_window(self):
        rank = core.best_bet.ahead_rank
        self.assertEqual(rank(_at(30), NOW), 0)
        self.assertEqual(rank(_at(20), NOW), 1)
        self.assertEqual(rank(_at(70), NOW), 2)
        self.assertEqual(rank("", NOW), 3)

    def test_the_game_30_hours_away(self):
        bets = [_preview("A at B"), _preview("C at D"), _preview("E at F")]
        starts = {"A at B": _at(20), "C at D": _at(30), "E at F": _at(70)}
        self.assertEqual(self._first(bets, starts)[0], "C at D")
        self.assertEqual(self._first(bets[:1], {"A at B": _at(20)}), ["A at B"])

    def test_a_prime_game_outranks_a_leagues(self):
        bets = [_preview("TNF", "national"), _preview("Cup game", "league")]
        starts = {"TNF": _at(14), "Cup game": _at(37)}
        self.assertEqual(self._first(bets, starts), ["TNF", "Cup game"])
        bets = [_preview("Tonight", "national"), _preview("Tomorrow", "national")]
        self.assertEqual(self._first(bets, {"Tonight": _at(11), "Tomorrow": _at(35)})[0],
                         "Tomorrow")  # fmt: skip

    def test_the_window_game_is_among_the_previews(self):
        scheduled = [("Nets at Hawks", "nba"), ("Wizards at Hawks", "nba")]
        details = {"Nets at Hawks": {"league": "nba", "date": _at(6)},
                   "Wizards at Hawks": {"league": "nba", "date": _at(30)}}  # fmt: skip
        starts = {k: v["date"] for k, v in details.items()}
        with (
            patch.dict(core.seasonal_calendar._DETAILS, details, clear=True),
            patch.dict(core.seasonal_calendar._STARTS, starts, clear=True),
            patch("core.best_bet.suggested_games", return_value=[]),
        ):
            soonest = core.best_bet.preview_options(scheduled, covered_topics=[], n=1, now=NOW)
            ahead = core.best_bet.preview_options(
                scheduled, covered_topics=[], n=1, now=NOW, ahead=True
            )
        self.assertEqual([p.topic for p in soonest], ["Nets at Hawks"])
        self.assertEqual([p.topic for p in ahead], ["Wizards at Hawks"])

    def test_the_overnight_drafts_the_day_ahead_game(self):
        tonight, tomorrow = _preview("Jets at Bills"), _preview("Rams at 49ers")
        starts = {"Jets at Bills": _at(10), "Rams at 49ers": _at(33)}
        menu = {}

        def get_menu(_channel, **kwargs):
            menu.update(kwargs)
            return [], [tonight, tomorrow]

        with (
            patch.dict(core.seasonal_calendar._STARTS, starts, clear=True),
            patch("core.best_bet.get_idea_menu", side_effect=get_menu),
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
            patch("core.best_bet.datetime") as clock,
        ):
            clock.now.return_value = NOW
            clock.fromisoformat = datetime.fromisoformat
            topics = core.batch_generation.collect_topics("tapin", count=2)
        self.assertTrue(menu.get("prefer_ahead"))
        self.assertEqual(topics[0], "Rams at 49ers")  # #1893: a day ahead, so in time

    def test_a_daily_leagues_next_days_are_read(self):
        def board(league, dates=""):
            if league == "nba" and dates == "20261126":
                return {"events": [{"id": "9", "name": "Knicks at Celtics",
                                    "date": "2026-11-27T00:30Z", "status": {"type": {}}}]}  # fmt: skip
            return {"events": []}

        with (
            patch("core.seasonal_calendar.schedule_enabled", return_value=True),
            patch(
                "core.seasonal_calendar._board_today", return_value=datetime(2026, 11, 25).date()
            ),  # fmt: skip
            patch("sports.espn.get_scoreboard", side_effect=board) as fetch,
            patch.dict(core.seasonal_calendar._STARTS, {}, clear=True),
            patch.dict(core.seasonal_calendar._DETAILS, {}, clear=True),
        ):
            topics = core.seasonal_calendar.fetch_week_topics()
        self.assertIn(("Knicks at Celtics", "nba"), topics)
        days = [c.kwargs.get("dates") for c in fetch.call_args_list if c.args[0] == "nba"]
        self.assertEqual(days, [None, "20261126", "20261127"])

    def test_boards_merge_each_game_once(self):
        merged = core.seasonal_calendar.merge_boards(
            {"events": [{"id": "1"}], "season": 2026}, {"events": [{"id": "1"}, {"id": "2"}]}
        )
        self.assertEqual([e["id"] for e in merged["events"]], ["1", "2"])
        self.assertEqual(merged["season"], 2026)


# ---- #1608: more of what worked -----------------------------------------------------------------

WNOW = datetime(2026, 11, 5, 11, tzinfo=UTC)


def _row(run_id, days_ago, views):
    return SimpleNamespace(content_run_id=run_id, published_at=WNOW - timedelta(days=days_ago),
                           privacy_status="public", metrics_json=json.dumps({"v": views}),
                           youtube_video_id=f"v{run_id}")  # fmt: skip


def _run(title, names=(), **features):
    data = {"entity_research": {"names": list(names)}, **features}
    return SimpleNamespace(title=title, features_json=json.dumps(data))


class WorkedTests(unittest.TestCase):
    def test_the_top_three_subjects_by_first_week_views(self):
        from core.series.worked import worked_subjects

        rows = [_row(1, 9, 1091), _row(2, 12, 308), _row(3, 10, 91), _row(4, 8, 30),
                _row(5, 9, 5000), _row(6, 20, 900), _row(7, 8, 12)]  # fmt: skip
        runs = {1: _run("GTA 6 online", ["GTA 6"]), 2: _run("Fans react to GTA 6", ["GTA 6"]),
                3: _run("Real Madrid set pieces", ["Real Madrid"], domains={"effective": "soccer"}),
                4: _run("Xbox Game Pass adds FF7", ["Xbox Game Pass"]),
                5: _run("Week in Review", compilation={"week": "2026-11-02"}),
                6: _run("Too old", ["Mahomes"]), 7: _run("Kane wins", ["Harry Kane"])}  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository",
                  return_value=SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)),
            patch("storage.repositories.publish_log.is_seeded", return_value=False),
            patch("storage.repositories.content_runs.get_content_run_repository",
                  return_value=SimpleNamespace(get=lambda rid: runs[rid])),
            patch("core.success.target.views_7d", side_effect=lambda m, _w: m.get("v")),
        ):  # fmt: skip
            found = worked_subjects("tapin", now=WNOW)
        self.assertEqual([f["subject"] for f in found], ["GTA 6", "Real Madrid", "Xbox Game Pass"])
        self.assertEqual(found[1]["domain"], "soccer")

    def test_tonights_idea_is_the_next_subject_with_fresh_news(self):
        from core.series.worked import worked_idea

        subjects = [{"subject": "GTA 6", "views": 1091, "run_id": 191, "domain": "gaming"},
                    {"subject": "Real Madrid", "views": 91, "run_id": 195, "domain": "soccer"}]  # fmt: skip
        lines = [{"title": "Real Madrid beat AEK Athens late", "source": "BBC Sport",
                  "published": WNOW - timedelta(hours=6)},
                 {"title": "Real Madrid sign a striker", "source": "BBC Sport",
                  "published": WNOW - timedelta(hours=80)}]  # fmt: skip
        with (
            patch.dict(os.environ, {"WORKED_SLOT": "true"}),
            patch("core.series.worked.worked_subjects", return_value=subjects),
            patch(
                "core.series.worked.drafted_since",
                side_effect=lambda _c, subject, _s: subject == "GTA 6",
            ),  # fmt: skip
        ):
            idea = worked_idea("tapin", now=WNOW, headlines=lambda *_a: lines)
        with patch.dict(os.environ, {"WORKED_SLOT": "false"}):
            self.assertIsNone(worked_idea("tapin", now=WNOW, headlines=lambda *_a: lines))
        self.assertEqual(idea.topic, "Real Madrid beat AEK Athens late")
        self.assertEqual((idea.source, idea.domain), ("worked", "soccer"))
        self.assertIn("91 organic views", idea.rationale)

    def test_no_fresh_news_waits(self):
        from core.series.worked import worked_idea

        notes = []
        with (
            patch.dict(os.environ, {"WORKED_SLOT": "true"}),
            patch(
                "core.series.worked.worked_subjects",
                return_value=[
                    {"subject": "Real Madrid", "views": 91, "run_id": 195, "domain": "soccer"}
                ],
            ),  # fmt: skip
            patch("core.series.worked.drafted_since", return_value=False),
        ):
            idea = worked_idea("tapin", now=WNOW, headlines=lambda *_a: [], notes=notes)
        self.assertIsNone(idea)
        self.assertIn("no Real Madrid headline", notes[0])

    def test_it_is_second_in_the_menu(self):
        def bet(topic, source="trending"):
            return core.best_bet.BestBetResult(topic=topic, domain="gaming", avg_engaged_rate=0.0,
                                               source=source, supporting_runs=0, rationale="")  # fmt: skip

        worked = bet("Real Madrid beat AEK Athens late", "worked")
        with (
            patch("core.seasonal_calendar.fetch_week_topics", return_value=[]),
            patch("core.best_bet.get_best_bets", return_value=[bet("A"), bet("B"), bet("C")]),
            patch("core.best_bet._series_idea", return_value=None),
            patch("core.series.worked.worked_idea", return_value=worked),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.dated.dated_ideas", return_value=[]),
            patch("core.best_bet.recent_input_topics", return_value=[]),
        ):
            ideas, _previews = core.best_bet.get_idea_menu("tapin", previews=0)
        self.assertEqual([b.topic for b in ideas], ["A", worked.topic, "B", "C"])

    def test_it_is_written_as_news(self):
        from core.angle_intent import ANGLE_NEWS

        self.assertEqual(
            core.batch_generation.draft_intent(own_idea=False, preview="", source="worked"),
            ANGLE_NEWS,
        )


if __name__ == "__main__":
    unittest.main()
