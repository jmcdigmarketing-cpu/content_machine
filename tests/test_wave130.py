"""Wave 130 (2026-10-25): the next ten.

Measured first: the intro test had settled - 21% stayed past the swipe with the channel intro
(13 videos) against 44% without (8), and every intro render opened on 2.2 s of silence; run 193
was drafted 31 minutes before its game; the insight pass's rewrite was rejected on 8 of 15 runs;
ESPN's scoreboard carries each team's season leaders; 1 idea in 5 was gaming while gaming brings
53% of organic views; channel comments were built and never switched on. The operator, 10-25
(decision 79): drop the intro, at least 2 of 5 ideas gaming, ask for the call on previews.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)


class IntroDroppedTests(unittest.TestCase):
    """#1581 (decision 79): the channel intro is off unless switched on."""

    def test_the_default_is_off(self):
        from video import channel_intro

        with patch.dict(os.environ):
            os.environ.pop("CHANNEL_INTRO_ENABLED", None)
            self.assertFalse(channel_intro._intro_enabled())
            self.assertIsNone(channel_intro.resolve_intro_path("tapin"))
            self.assertFalse(channel_intro.intro_for_run("tapin", 191))

    def test_growth_says_it_is_settled(self):
        from analytics import growth

        rates = ([0.21] * 13, [0.44] * 8)
        with patch.dict(os.environ):
            os.environ.pop("CHANNEL_INTRO_ENABLED", None)
            with patch.object(growth, "_intro_rates", return_value=rates):
                line = growth.intro_line("tapin")
            rep = {"per_week": 7.5, "paid_share": 0.0,
                   "intro_split": {"with": 0.21, "without": 0.44, "n_with": 13, "n_without": 8}}  # fmt: skip
            keys = [lever["key"] for lever in growth.levers(rep)]
        self.assertIn("dropped (decision 79)", line)
        self.assertNotIn("intro", keys)


class TooSoonTests(unittest.TestCase):
    """#1577: a game under 3 hours away is neither offered nor drafted (run 193: 31 minutes)."""

    def test_starts_within(self):
        from core.facts.event_dates import starts_within

        self.assertTrue(starts_within("2026-10-25T17:00Z", 3, now="2026-10-25T16:29Z"))
        self.assertFalse(starts_within("2026-10-25T17:00Z", 3, now="2026-10-25T13:00Z"))
        self.assertFalse(starts_within("2026-10-25T17:00Z", 3, now="2026-10-25T18:00Z"))  # started

    def test_the_menu_skips_it(self):
        from core.best_bet import _too_soon

        self.assertTrue(_too_soon("2026-10-25T17:00Z", NOW - timedelta(minutes=90)))
        self.assertFalse(_too_soon("2026-10-25T17:00Z", NOW - timedelta(hours=8)))

    def test_the_draft_is_refused_before_discovery(self):
        from core import batch_generation

        with (
            patch.object(batch_generation, "_game_start", return_value="2026-10-25T17:00Z"),
            patch("core.facts.event_dates.starts_within", return_value=True),
            patch("core.facts.event_dates.game_started", return_value=False),
            patch("core.pipeline.run_discovery") as discovery,
        ):
            out = batch_generation.generate_draft(
                "Cincinnati Bengals at Baltimore Ravens", channel_id="tapin"
            )
        discovery.assert_not_called()
        self.assertIn("under 3 hours", out.error)


RECAP = (
    "Aston Villa beat Manchester City two nil on Saturday. Jhon Duran scored twice in the second "
    "half. City had won all six league games before this one. Villa sit fourth after the result."
)


class InsightRetryTests(unittest.TestCase):
    """#1578: the insight pass asks twice and records why a rewrite was refused."""

    def test_a_second_ask_after_no_take(self):
        from core import content_engine

        replies = [{"script": RECAP + " Villa travel to Brighton next."},
                   {"script": RECAP + " Here's why it matters: City's defence has to change now."}]  # fmt: skip
        with patch.object(content_engine, "_call_content_llm", side_effect=replies) as llm:
            script, extra = content_engine.insight_pass(RECAP, "facts", "Villa beat City")
        self.assertEqual(llm.call_count, 2)
        self.assertIn("Here's why", script)
        self.assertEqual(extra["insight_rejected"], ["no take"])
        self.assertIn(
            "retry", llm.call_args_list[1].args[0].lower()
        )  # the cues named the second time
        self.assertNotIn("retry", llm.call_args_list[0].args[0].lower())

    def test_two_refusals_keep_the_script_and_say_why(self):
        from core import content_engine

        replies = [{"script": "Villa won."}, {"script": RECAP + " Villa travel to Brighton next."}]
        with patch.object(content_engine, "_call_content_llm", side_effect=replies):
            script, extra = content_engine.insight_pass(RECAP, "facts", "Villa beat City")
        self.assertEqual(script, RECAP)
        self.assertEqual(extra["insight_rejected"], ["short", "no take"])

    def test_the_old_entry_point_returns_a_script(self):
        from core import content_engine

        with patch.object(content_engine, "_call_content_llm", return_value={"script": RECAP}):
            self.assertEqual(
                content_engine._maybe_inject_insight(RECAP, "facts", "Villa beat City"), RECAP
            )


def _competitor(name, home, leaders, score="0"):
    return {"homeAway": "home" if home else "away", "team": {"displayName": name}, "score": score,
            "winner": False, "leaders": leaders}  # fmt: skip


def _leader(abbr, value, player):
    return {"name": abbr.lower(), "shortDisplayName": abbr,
            "leaders": [{"displayValue": value, "athlete": {"displayName": player}}]}  # fmt: skip


class LeadersTests(unittest.TestCase):
    """#1575: the matched game's season leaders become a fact line."""

    EVENT: ClassVar[dict] = {
        "name": "Los Angeles Lakers at Utah Jazz",
        "date": "2026-10-26T01:00Z",
        "status": {"type": {"description": "Scheduled", "completed": False}},
        "competitions": [{"competitors": [
            _competitor("Utah Jazz", True, [_leader("PPG", "20.5", "Keyonte George"),
                                             _leader("RPG", "9.1", "Walker Kessler")]),
            _competitor("Los Angeles Lakers", False, [_leader("PPG", "27.0", "Luka Doncic")]),
        ]}],
    }  # fmt: skip

    def test_the_event_keeps_its_leaders(self):
        from apis.live_scores_api import _parse_event

        game = _parse_event(self.EVENT)
        self.assertEqual(
            game["leaders"]["Utah Jazz"], ["Keyonte George 20.5 PPG", "Walker Kessler 9.1 RPG"]
        )

    def test_the_facts_print_them(self):
        from apis.live_scores_api import _parse_event
        from core.signal_facts import format_signal_facts

        sig = {
            "active": True,
            "connected": True,
            "data": {"matched_game": _parse_event(self.EVENT)},
        }
        text = format_signal_facts({"live_scores": sig})
        self.assertIn("ESPN season leaders", text)
        self.assertIn("Utah Jazz: Keyonte George 20.5 PPG, Walker Kessler 9.1 RPG", text)
        self.assertIn("Los Angeles Lakers: Luka Doncic 27.0 PPG", text)


class GamingFloorTests(unittest.TestCase):
    """#1447 (decision 79): at least 2 of 5 ideas are gaming while gaming leads organic views."""

    FRESH: ClassVar[list[dict]] = [
        {"topic": "Lakers trade for a backup center", "domain": "nba", "source": "ESPN"},
        {"topic": "Celtics extend Joe Mazzulla", "domain": "nba", "source": "ESPN"},
        {"topic": "Knicks bench struggles again", "domain": "nba", "source": "ESPN"},
        {"topic": "Chiefs sign a new kicker", "domain": "nfl", "source": "ESPN"},
        {"topic": "Bears fire their offensive coordinator", "domain": "nfl", "source": "ESPN"},
        {
            "topic": "Topuria books his next title defense",
            "domain": "ufc",
            "source": "MMA Fighting",
        },
        {
            "topic": "Marvel Rivals season 5 leak shows a new map",
            "domain": "gaming",
            "source": "IGN",
        },
        {
            "topic": "Elden Ring Nightreign gets a surprise DLC date",
            "domain": "gaming",
            "source": "IGN",
        },
    ]
    ENTRIES: ClassVar[list[dict]] = [
        {"topic": "NBA trade deadline winners", "engaged_rate": 0.40, "composite_score": 70, "domain": "nba", "views": 300},
        {"topic": "NFL week 5 picks", "engaged_rate": 0.38, "composite_score": 68, "domain": "nfl", "views": 250},
        {"topic": "UFC 333 preview", "engaged_rate": 0.35, "composite_score": 66, "domain": "ufc", "views": 200},
        {"topic": "GTA 6 map breakdown", "engaged_rate": 0.20, "composite_score": 50, "domain": "gaming", "views": 900},
    ]  # fmt: skip

    def _ideas(self, leads):
        from core import best_bet

        with (
            patch.object(best_bet, "_build_entries", return_value=self.ENTRIES),
            patch.object(best_bet, "recent_input_topics", return_value=[]),
            patch.object(best_bet, "_fresh_candidates", return_value=list(self.FRESH)),
            patch.object(best_bet, "_gaming_leads", return_value=leads),
            patch("core.topic_graph.follow_up_seed", return_value=None),
            patch("core.seasonal_calendar.due_topics", return_value=[]),
            patch("analytics.mailbag.top_question", return_value=None),
        ):
            return best_bet.get_best_bets("tapin", 5, games=False, scheduled=[])

    def test_the_floor(self):
        base = [b.domain for b in self._ideas(False)]
        floored = [b.domain for b in self._ideas(True)]
        self.assertLess(base.count("gaming"), 2, base)  # the fixture's precondition
        self.assertGreaterEqual(floored.count("gaming"), 2, floored)
        self.assertEqual(len(floored), len(base))


class GamingHistoryTests(unittest.TestCase):
    """#1447: one gaming franchise in the news - the floor takes a past gaming topic."""

    def test_the_history_fills_in(self):
        from core import best_bet

        fresh = [f for f in GamingFloorTests.FRESH if f["domain"] != "gaming"] + [
            {
                "topic": "Call Of Duty Modern Warfare 4 first DLC is out",
                "domain": "gaming",
                "source": "IGN",
            },
            {
                "topic": "Call Of Duty ads on Xbox annoy players",
                "domain": "gaming",
                "source": "IGN",
            },
        ]
        entries = [*GamingFloorTests.ENTRIES,
                   {"topic": "Marvel Rivals tier list", "engaged_rate": 0.25, "composite_score": 55,
                    "domain": "gaming", "views": 968}]  # fmt: skip
        with (
            patch.object(best_bet, "_build_entries", return_value=entries),
            patch.object(best_bet, "recent_input_topics", return_value=[]),
            patch.object(best_bet, "_fresh_candidates", return_value=fresh),
            patch.object(best_bet, "_gaming_leads", return_value=True),
            patch("core.topic_graph.follow_up_seed", return_value=None),
            patch("core.seasonal_calendar.due_topics", return_value=[]),
            patch("analytics.mailbag.top_question", return_value=None),
        ):
            ideas = best_bet.get_best_bets("tapin", 5, games=False, scheduled=[])
        gaming = [b.topic for b in ideas if b.domain == "gaming"]
        self.assertGreaterEqual(len(gaming), 2, gaming)
        self.assertEqual(sum("Call Of Duty" in t for t in gaming), 1)  # one place a franchise


class MenuMixTests(unittest.TestCase):
    """#1446: `ops predictions` names the menu's domain mix and what was taken."""

    def test_the_mix(self):
        from core.predictions import ledger

        def run(rid, offered, picked):
            features = {
                "best_bet": {
                    "offered": [{"topic": t, "domain": d} for t, d in offered],
                    "picked": picked,
                }
            }
            return SimpleNamespace(id=rid, features_json=json.dumps(features))

        runs = MagicMock()
        runs.list_for_channel.return_value = [
            run(1, [("a", "gaming"), ("b", "nba"), ("c", "nfl")], 2),
            run(2, [("d", "gaming"), ("e", "ufc")], 1),
            run(3, [("f", "nba")], None),
        ]
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=runs
        ):
            line = ledger.menu_mix_line("tapin")
        self.assertIn("offered gaming 2, nba 2, nfl 1, ufc 1", line)
        self.assertIn("taken gaming 1, nba 1", line)


class CallCommentTests(unittest.TestCase):
    """#1327 (decision 79): a public preview gets one comment asking for the viewer's call."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CALL_COMMENT_FILE": os.path.join(self.tmp.name, "calls.json"),
                                           "YOUTUBE_CALL_COMMENT": "true"})  # fmt: skip
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _post(self, *, published, event):
        from youtube import pin_comment

        row = SimpleNamespace(youtube_video_id="V185", content_run_id=185, privacy_status="public",
                              published_at=published)  # fmt: skip
        logs = MagicMock()
        logs.list_uploaded_for_channel.return_value = [row]
        runs = MagicMock()
        runs.get.return_value = SimpleNamespace(id=185, title="Chiefs vs Seahawks: Can Seattle stop KC?",
                                                selected_topic="Kansas City Chiefs at Seattle Seahawks")  # fmt: skip
        service = MagicMock()
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=logs),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=runs
            ),
            patch("core.stale_renders.run_event", return_value=event),
        ):
            lines = pin_comment.post_call_comments(service, "tapin", now=NOW)
        return lines, service

    def test_a_public_preview_gets_one(self):
        lines, service = self._post(
            published=NOW - timedelta(hours=1), event=NOW + timedelta(hours=5)
        )
        body = service.commentThreads.return_value.insert.call_args.kwargs["body"]
        text = body["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
        self.assertIn("Kansas City Chiefs or Seattle Seahawks", text)
        self.assertIn("grade", text)
        self.assertEqual(len(lines), 1)
        _lines, again = self._post(
            published=NOW - timedelta(hours=1), event=NOW + timedelta(hours=5)
        )
        again.commentThreads.return_value.insert.assert_not_called()  # once per video

    def test_none_after_kickoff_or_a_day_late(self):
        _l, started = self._post(
            published=NOW - timedelta(hours=1), event=NOW - timedelta(minutes=5)
        )
        started.commentThreads.return_value.insert.assert_not_called()
        _l, late = self._post(published=NOW - timedelta(hours=30), event=NOW + timedelta(hours=5))
        late.commentThreads.return_value.insert.assert_not_called()

    def test_the_worker_pass_and_the_status_line(self):
        from jobs import worker
        from youtube import pin_comment

        with (
            patch.object(worker, "_post_due_pins"),
            patch.object(worker, "_crosspost_scheduled_live"),
            patch.object(worker, "_previews_first"),
            patch.object(worker, "process_one", return_value=False),
            patch.object(worker, "_schedule_chapter_shorts"),
            patch.object(worker, "_post_call_comments") as calls,
        ):
            worker.drain_due()
        calls.assert_called_once()
        self._post(published=NOW - timedelta(hours=1), event=NOW + timedelta(hours=5))
        line = pin_comment.call_comment_line("tapin", now=NOW + timedelta(hours=1))
        self.assertIn("pin it in Studio", line)
        self.assertIn("youtu.be/V185", line)


class RetireDeadTests(unittest.TestCase):
    """#1580: a render whose game started over a day ago is retired; the file stays."""

    def test_a_day_after_kickoff(self):
        from core import stale_renders

        old, fresh = SimpleNamespace(id=181), SimpleNamespace(id=184)
        events = {181: NOW - timedelta(days=3), 184: NOW - timedelta(hours=4)}
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[old, fresh]),
            patch.object(
                stale_renders, "started_event", side_effect=lambda run, ch, **k: events[run.id]
            ),
            patch.object(
                stale_renders, "retire_renders", side_effect=lambda runs: [r.id for r in runs]
            ) as retire,
        ):
            got = stale_renders.retire_dead_renders("tapin", now=NOW)
        self.assertEqual(got, [181])
        retire.assert_called_once()


if __name__ == "__main__":
    unittest.main()
