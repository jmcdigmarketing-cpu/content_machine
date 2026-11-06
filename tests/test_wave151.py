"""Wave 151 (2026-11-05) - the fast lanes and the sports calendar.

#1647 breaking news on 5+ outlets within 2 hours, #1649 + #1875 a national final within the hour,
#1650 a numbered card's finish within the hour - each drafted, checked, rendered and public now from
the worker (#1655, #1667); #1872 the two-week calendar of marquee events (`ops calendar`).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

# Imported before any patch below (wave 145's reversed-suite failure).
import core.batch_review
import core.best_bet
import core.seasonal_calendar
import jobs.worker

UTC = timezone.utc
NOW = datetime(2026, 11, 19, 15, tzinfo=UTC)


def _lane():
    import jobs.fast_lane

    return jobs.fast_lane


def _cand(topic, outlets, minutes_ago, domain="gaming"):
    first = NOW - timedelta(minutes=minutes_ago)
    return {"topic": topic, "domain": domain, "published": first, "first": first,
            "outlets": [f"Outlet {i}" for i in range(outlets)]}  # fmt: skip


# ---- #1647: breaking news ------------------------------------------------------------------------


class NewsLaneTests(unittest.TestCase):
    def _story(self, pool, drafted=False, env=None):
        lane = _lane()
        with (
            patch.dict(os.environ, env or {"FAST_LANE_OUTLETS": ""}),
            patch("core.best_bet.marquee_names", return_value=["GTA 6", "Mahomes"]),
            patch.object(lane, "_drafted", return_value=drafted),
        ):
            return lane.news_story("tapin", now=NOW, pool=pool, done=set())

    def test_a_marquee_story_on_five_outlets_within_two_hours(self):
        pool = [_cand("Rockstar confirms GTA 6 day-one patch", 6, 50)]
        self.assertEqual(self._story(pool)["topic"], "Rockstar confirms GTA 6 day-one patch")

    def test_what_it_passes_over(self):
        self.assertIsNone(self._story([_cand("GTA 6 patch notes", 4, 50)]))  # four outlets
        self.assertIsNone(self._story([_cand("GTA 6 patch notes", 6, 150)]))  # broke 2.5 h ago
        self.assertIsNone(self._story([_cand("Valve updates Steam", 7, 30)]))  # not marquee
        self.assertIsNone(self._story([_cand("GTA 6 fan has died", 7, 30)]))  # decision 97
        self.assertIsNone(self._story([_cand("GTA 6 patch notes", 6, 50)], drafted=True))

    def test_the_bar_can_be_set(self):
        pool = [_cand("Mahomes ruled out", 3, 20, "nfl")]
        self.assertIsNone(self._story(pool))
        self.assertIsNotNone(self._story(pool, env={"FAST_LANE_OUTLETS": "3"}))

    def test_a_story_keeps_when_it_broke(self):
        early = NOW - timedelta(hours=3)
        pool = [{"topic": "Rockstar confirms GTA 6 day-one patch notes", "source": "IGN",
                 "published": NOW - timedelta(minutes=10)},
                {"topic": "GTA 6 day-one patch notes confirmed by Rockstar", "source": "Kotaku",
                 "published": early}]  # fmt: skip
        ranked = core.best_bet.rank_by_coverage(pool, now=NOW)
        self.assertEqual(ranked[0]["first"], early)


# ---- #1650: a numbered card's finish -----------------------------------------------------------


class UfcLaneTests(unittest.TestCase):
    def _story(self, pool, *, started=True):
        lane = _lane()
        start = (NOW - timedelta(hours=1)) if started else (NOW + timedelta(hours=1))
        with (
            patch("core.seasonal_calendar.event_for",
                  return_value=("UFC 334", start.isoformat().replace("+00:00", "Z"))),
            patch.object(lane, "_drafted", return_value=False),
        ):  # fmt: skip
            return lane.ufc_story("tapin", now=NOW, pool=pool, done=set())

    def test_a_finish_headline_on_three_outlets(self):
        pool = [_cand("UFC 334 results: Gane knocks out Hokit in round one", 3, 20, "ufc")]
        self.assertEqual(self._story(pool)["kind"], "ufc")

    def test_not_before_the_card_nor_a_preview_nor_a_fight_night(self):
        finish = _cand("UFC 334 results: Gane knocks out Hokit in round one", 3, 20, "ufc")
        self.assertIsNone(self._story([finish], started=False))
        self.assertIsNone(self._story([_cand("UFC 334 preview: Gane vs Hokit", 5, 20, "ufc")]))
        night = _cand("UFC Fight Night results: Acosta knocks out Walker", 4, 20, "ufc")
        self.assertIsNone(self._story([night]))
        self.assertIsNone(self._story([{**finish, "first": NOW - timedelta(minutes=90)}]))


# ---- #1649 / #1875: a national final -----------------------------------------------------------


def _event(tv, *, hours_ago, completed=True, scores=(20, 3), event_id="401"):
    start = NOW - timedelta(hours=hours_ago)
    sides = [{"homeAway": "home", "score": str(scores[0]), "team": {"shortDisplayName": "Seahawks"}},
             {"homeAway": "away", "score": str(scores[1]), "team": {"shortDisplayName": "Chiefs"}}]  # fmt: skip
    return {"id": event_id, "name": "Kansas City Chiefs at Seattle Seahawks",
            "date": start.isoformat().replace("+00:00", "Z"),
            "status": {"type": {"completed": completed}},
            "competitions": [{"competitors": sides, "broadcasts": [{"names": [tv]}]}]}  # fmt: skip


class ResultLaneTests(unittest.TestCase):
    def test_a_national_final_within_the_hour(self):
        found = _lane().final_of("nfl", _event("NBC", hours_ago=3.3 + 40 / 60), now=NOW)
        self.assertEqual(found["topic"], "Seahawks beat Chiefs 20-3: what it means")
        self.assertIn("ESPN final: Chiefs 3, Seahawks 20 - Seahawks won (NBC)", found["final"])

    def test_not_a_regional_one_a_stale_one_or_a_game_on(self):
        lane = _lane()
        self.assertIsNone(lane.final_of("nfl", _event("CBS", hours_ago=4.0), now=NOW))
        self.assertIsNone(lane.final_of("nfl", _event("NBC", hours_ago=3.3 + 1.5), now=NOW))
        self.assertIsNone(
            lane.final_of("nfl", _event("NBC", hours_ago=2, completed=False), now=NOW)
        )

    def test_a_final_once(self):
        boards = {"nfl": {"events": [_event("NBC", hours_ago=4.0)]}, "nba": {"events": []}}
        lane = _lane()
        self.assertIsNotNone(lane.result_story("tapin", now=NOW, done=set(), boards=boards))
        self.assertIsNone(lane.result_story("tapin", now=NOW, done={"result:401"}, boards=boards))


# ---- the lane ------------------------------------------------------------------------------------


class LaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        lane = _lane()
        for target in (
            patch.object(
                lane, "store_path", lambda cid: os.path.join(self.tmp.name, f"fast_lane_{cid}.json")
            ),
            patch.dict(os.environ, {"FAST_LANE": "true"}),
            patch.object(lane, "units_left", return_value=9000),
            patch.object(lane, "on_battery", return_value=False),
            patch.object(lane, "overnight_running", return_value=False),
        ):
            target.start()
            self.addCleanup(target.stop)

    def test_why_it_does_not_look(self):
        lane = _lane()
        self.assertEqual(lane.blocked("tapin", now=NOW, store={}), "")
        recent = {"checked": (NOW - timedelta(minutes=10)).isoformat()}
        self.assertIn("10 minutes ago", lane.blocked("tapin", now=NOW, store=recent))
        full = {"days": {"2026-11-19": {"news": 2, "result": 1}}}
        self.assertIn("3 made today", lane.blocked("tapin", now=NOW, store=full))
        with patch.object(lane, "units_left", return_value=1200):
            self.assertIn("1,600", lane.blocked("tapin", now=NOW, store={}))
        with patch.object(lane, "on_battery", return_value=True):
            self.assertEqual(lane.blocked("tapin", now=NOW, store={}), "on battery")
        with patch.object(lane, "overnight_running", return_value=True):
            self.assertEqual(lane.blocked("tapin", now=NOW, store={}), "overnight is running")
        with patch.dict(os.environ, {"FAST_LANE": "false"}):
            self.assertIn("off", lane.blocked("tapin", now=NOW, store={}))

    def test_a_result_before_a_finish_before_news(self):
        lane = _lane()
        boards = {"nfl": {"events": [_event("NBC", hours_ago=4.0)]}}
        news = [_cand("Rockstar confirms GTA 6 day-one patch", 6, 30)]
        with (
            patch("core.best_bet.marquee_names", return_value=["GTA 6"]),
            patch.object(lane, "_drafted", return_value=False),
        ):
            first = lane.next_story("tapin", now=NOW, store={}, pool=lambda _c: news, boards=boards)
            then = lane.next_story("tapin", now=NOW, store={}, pool=lambda _c: news,
                                   boards={"nfl": {"events": []}})  # fmt: skip
            capped = lane.next_story("tapin", now=NOW, pool=lambda _c: news, boards={},
                                     store={"days": {"2026-11-19": {"news": 2}}})  # fmt: skip
        self.assertEqual((first["kind"], then["kind"]), ("result", "news"))
        self.assertIsNone(capped)

    def test_one_pass_drafts_renders_and_counts(self):
        lane = _lane()
        story = {"kind": "result", "key": "result:401", "topic": "Seahawks beat Chiefs 20-3",
                 "domain": "nfl", "why": "a NFL final on national TV", "final": "ESPN final"}  # fmt: skip
        drafted = []

        def draft(_channel, picked):
            drafted.append(picked["topic"])
            return SimpleNamespace(ok=True, run_id=250, error="")

        with patch.object(lane, "next_story", return_value=story):
            lines = lane.run_fast_lane("tapin", now=NOW, draft=draft,
                                       render=lambda _c, _r: ("", 91))  # fmt: skip
            again = lane.run_fast_lane("tapin", now=NOW + timedelta(minutes=10), draft=draft,
                                       render=lambda _c, _r: ("", 92))  # fmt: skip
        self.assertEqual(drafted, ["Seahawks beat Chiefs 20-3"])
        self.assertIn("queued public now (job 91)", lines[-1])
        self.assertEqual(again, [])
        store = lane.load_store("tapin")
        self.assertEqual(store["days"]["2026-11-19"], {"result": 1})
        self.assertIn("result:401", store["done"])

    def test_a_held_draft_is_not_counted(self):
        lane = _lane()
        story = {"kind": "news", "key": "news:x", "topic": "x", "domain": "gaming", "why": "w"}
        with patch.object(lane, "next_story", return_value=story):
            lines = lane.run_fast_lane(
                "tapin", now=NOW, draft=lambda *_a: SimpleNamespace(ok=True, run_id=251),
                render=lambda _c, _r: ("held - a claim is not supported", 0),
            )  # fmt: skip
        self.assertIn("held - a claim is not supported", lines[-1])
        self.assertNotIn("days", lane.load_store("tapin"))

    def test_the_toast_is_for_a_claim_only(self):
        with patch("core.win_notify.toast_daily") as toast:
            _lane()._hold_toast("tapin", 251, "a claim is not supported")
            _lane()._hold_toast("tapin", 252, "second read: the title's story")
        self.assertEqual(toast.call_count, 1)

    def test_the_render_is_queued_public_now(self):
        draft = SimpleNamespace(run_id=250, meta={}, folder="f")
        with (
            patch("core.batch_review.pending_drafts", return_value=[draft]),
            patch("core.batch_review.unattended_block_reason", return_value=""),
            patch("core.batch_review._second_read_for", return_value=""),
            patch("core.batch_review._smoke_failure", return_value=""),
            patch("core.batch_review._memory_short", return_value=""),
            patch("core.batch_review._disk_short", return_value=""),
            patch("core.batch_review._render_in_process", return_value=True),
            patch("core.batch_review._write_review"),
            patch("analytics.queue_manager.requeue_content_run", return_value=93) as queue,
        ):
            held, job = _lane()._render_and_queue("tapin", 250)
        self.assertEqual((held, job), ("", 93))
        self.assertEqual(queue.call_args.kwargs, {"privacy_status": "public"})

    def test_a_result_is_drafted_with_its_final(self):
        story = {"kind": "result", "key": "k", "topic": "Seahawks beat Chiefs 20-3",
                 "domain": "nfl", "why": "w", "final": "ESPN final: Chiefs 3, Seahawks 20"}  # fmt: skip
        with patch("core.overnight._draft_one", return_value="o") as one:
            _lane()._draft("tapin", story)
        self.assertEqual(one.call_args.kwargs["key_facts"], ["ESPN final: Chiefs 3, Seahawks 20"])
        offered = one.call_args.kwargs["pick"]["offered"][0]
        self.assertEqual(offered["source"], "fast_result")


class OvernightBeatTests(unittest.TestCase):
    def test_overnight_running_reads_its_beat(self):
        lane = _lane()
        local = NOW.astimezone().replace(tzinfo=None)
        with patch("core.nightly_task.last_beat",
                   return_value={"beat": (local - timedelta(minutes=1)).isoformat()}):  # fmt: skip
            self.assertTrue(lane.overnight_running(NOW))
        with patch("core.nightly_task.last_beat",
                   return_value={"beat": (local - timedelta(minutes=9)).isoformat()}):  # fmt: skip
            self.assertFalse(lane.overnight_running(NOW))


class WorkerStepTests(unittest.TestCase):
    def test_the_worker_uploads_it_in_the_same_pass(self):
        with (
            patch("config.channels.active_channel_ids", return_value=["tapin"]),
            patch("jobs.fast_lane.run_fast_lane",
                  return_value=["Fast lane (x): y", "  run 250 rendered and queued public now (job 91)"]),
            patch("jobs.worker.process_one", side_effect=[True, False]) as one,
        ):  # fmt: skip
            sent = jobs.worker._fast_lane()
        self.assertEqual((sent, one.call_count), (1, 2))


# ---- #1872: the two-week calendar --------------------------------------------------------------


class CalendarTests(unittest.TestCase):
    def test_the_marquee_events_by_time(self):
        def game(name, tv, hours):
            when = (NOW + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
            return {"id": name, "name": name, "date": when,
                    "competitions": [{"broadcasts": [{"names": [tv]}], "competitors": []}]}  # fmt: skip

        def fetch(league, week=None, dates=""):
            if league == "nfl":
                return {"week": {"number": 11},
                        "events": [game("Bills at Chiefs", "NBC", 50), game("Jets at Colts", "CBS", 30)]
                        if week is None else []}  # fmt: skip
            if league == "nba":
                return {
                    "events": [game("Knicks at Celtics", "ESPN", 8)] if dates == "20261119" else []
                }
            return {"leagues": [{"calendar": [{"label": "UFC 335: A vs. B",
                                               "startDate": (NOW + timedelta(days=3)).isoformat()}]}]}  # fmt: skip

        with patch("core.series.countdown.series_rows", return_value=[]):
            rows = core.seasonal_calendar.marquee_calendar(now=NOW, days=14, fetch=fetch)
        self.assertEqual([r["name"] for r in rows],
                         ["Knicks at Celtics", "Bills at Chiefs", "UFC 335: A vs. B"])  # fmt: skip
        lines = core.seasonal_calendar.calendar_lines(rows)
        self.assertTrue(
            any("preview the day before; result in the fast lane" in line for line in lines)
        )

    def test_ops_calendar_is_a_command(self):
        from scripts.ops import COMMANDS

        self.assertIn("calendar", COMMANDS)


if __name__ == "__main__":
    unittest.main()
