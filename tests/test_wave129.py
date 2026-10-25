"""Wave 129 (2026-10-25): the next ten after wave 128.

Measured first: of 46 drafts in two weeks, 18 expired undecided and 4 of 14 game drafts went public
before their game; a "Decide first" line existed only in `ops status`. Four clean drafts never
rendered under the shelf cap. The operator, 10-25 (decision 78): a toast at the decide-by time,
then a clean overnight render goes out unanswered; the shelf cap 5 when the week is empty; a dull
opener is a warning; preview shapes rotate as an experiment.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)


def _local(moment):
    """A draft's `review.at` is naive local time."""
    return moment.astimezone().replace(tzinfo=None)


class DecideToastTests(unittest.TestCase):
    """#1572: a game draft due for a decision is pushed, not only listed."""

    def _watch(self, by):
        from core import batch_review
        from jobs import worker

        decision = {"draft": SimpleNamespace(title="Bucks vs 76ers preview", run_id=188),
                    "kickoff": NOW + timedelta(hours=6), "slot": by, "by": by}  # fmt: skip
        with (
            patch.object(batch_review, "next_decision", return_value=decision),
            patch("config.channels.active_channel_ids", return_value=["tapin"]),
            patch("core.win_notify.toast_daily") as toast,
        ):
            worker._decide_watch(now=NOW)
        return toast

    def test_within_three_hours_it_toasts_once_per_draft(self):
        toast = self._watch(NOW + timedelta(hours=2))
        toast.assert_called_once()
        self.assertEqual(toast.call_args.args[0], "decide-188")
        self.assertIn("Bucks vs 76ers", toast.call_args.args[2])

    def test_further_off_it_waits(self):
        self._watch(NOW + timedelta(hours=5)).assert_not_called()

    def test_the_deadline_line_reads_the_same_decision(self):
        from core import batch_review

        decision = {"draft": SimpleNamespace(title="X at Y", run_id=1),
                    "kickoff": NOW + timedelta(hours=30), "slot": None, "by": None}  # fmt: skip
        with patch.object(batch_review, "next_decision", return_value=decision):
            self.assertIn("no upload slot is left", batch_review.deadline_line("tapin", now=NOW))


class UnansweredRenderTests(unittest.TestCase):
    """#1574 (decision 78): a clean overnight render left unanswered goes out at its slot."""

    def _run(self, *, rendered_at, event_at="", aside=False, held=False):
        from core import batch_review

        row = SimpleNamespace(
            id=1, content_run_id=200, privacy_status="unlisted", youtube_video_id="V200"
        )
        rendered = [{"run_id": 200, "title": "Mass Effect 5 leak", "at": rendered_at}]
        scheduled = MagicMock(return_value=SimpleNamespace(status="scheduled", detail="Mon noon"))
        with (
            patch("publishing.go_public.listed_holds", return_value=[] if aside else [row]),
            patch.object(batch_review, "overnight_rendered", return_value=rendered),
            patch.object(batch_review, "draft_meta_for_run", return_value={"event_at": event_at}),
            patch("core.spaced_queue.slot_for_run", return_value=(NOW + timedelta(hours=18), "")),
            patch("publishing.go_public.apply_schedule_public", scheduled),
            patch("publishing.go_public.override_held", return_value=held),
        ):
            lines = batch_review.schedule_unanswered_renders("tapin", now=NOW)
        return lines, scheduled

    def test_after_a_day_unanswered_it_goes(self):
        lines, scheduled = self._run(rendered_at=_local(NOW - timedelta(hours=25)))
        scheduled.assert_called_once()
        self.assertIn("200", "\n".join(lines))

    def test_a_preview_due_soon_goes_sooner(self):
        _lines, scheduled = self._run(
            rendered_at=_local(NOW - timedelta(hours=3)),
            event_at=(NOW + timedelta(hours=20)).strftime("%Y-%m-%dT%H:%MZ"),
        )
        scheduled.assert_called_once()

    def test_fresh_set_aside_or_held_waits(self):
        fresh = _local(NOW - timedelta(hours=3))
        old = _local(NOW - timedelta(hours=30))
        self._run(rendered_at=fresh)[1].assert_not_called()
        self._run(rendered_at=old, aside=True)[1].assert_not_called()
        self._run(rendered_at=old, held=True)[1].assert_not_called()

    def test_the_worker_pass_runs_it(self):
        from jobs import worker

        with (
            patch("apis.youtube_quota.get_usage_summary", return_value={"remaining": 5000}),
            patch("config.channels.active_channel_ids", return_value=["tapin"]),
            patch("core.chapter_shorts.schedule_waiting_shorts", return_value=[]),
            patch(
                "core.batch_review.schedule_unanswered_renders", return_value=["run 200: scheduled"]
            ) as renders,
        ):
            worker._schedule_chapter_shorts()
        renders.assert_called_once()


class ShelfCapTests(unittest.TestCase):
    """#1434 (decision 78): overnight's shelf cap is 5 while the week ahead is nearly empty."""

    def test_the_cap_rises_when_the_week_is_empty(self):
        from core import batch_review

        with (
            patch.dict(os.environ, {"OVERNIGHT_SHELF_MAX": "3"}),
            patch("core.chapter_shorts.scheduled_next_days", return_value=1),
        ):
            self.assertEqual(batch_review.shelf_max("tapin"), 5)
            self.assertEqual(batch_review.shelf_pause("tapin", waiting=4), "")
        with (
            patch.dict(os.environ, {"OVERNIGHT_SHELF_MAX": "3"}),
            patch("core.chapter_shorts.scheduled_next_days", return_value=4),
        ):
            self.assertEqual(batch_review.shelf_max("tapin"), 3)
            self.assertIn("overnight stops at 3", batch_review.shelf_pause("tapin", waiting=4))

    def test_no_limit_stays_no_limit(self):
        from core import batch_review

        with (
            patch.dict(os.environ, {"OVERNIGHT_SHELF_MAX": "0"}),
            patch("core.chapter_shorts.scheduled_next_days", return_value=0),
        ):
            self.assertEqual(batch_review.shelf_max("tapin"), 0)


def _schedule(abbr, games):
    """An ESPN team schedule: (date, opponent abbr, our score, their score, home)."""
    events = []
    for when, other, ours, theirs, home in games:
        done = ours is not None
        events.append({
            "date": f"{when}T17:00Z",
            "competitions": [{
                "status": {"type": {"completed": done}},
                "competitors": [
                    {"homeAway": "home" if home else "away", "team": {"abbreviation": abbr},
                     "score": {"displayValue": str(ours)} if done else None, "winner": done and ours > theirs},
                    {"homeAway": "away" if home else "home", "team": {"abbreviation": other},
                     "score": {"displayValue": str(theirs)} if done else None, "winner": done and theirs > ours},
                ],
            }],
        })  # fmt: skip
    return {"events": events}


class SeasonContextTests(unittest.TestCase):
    """#1369: a preview's teams carry their streak, their last results and a meeting this season."""

    def test_the_streak(self):
        from apis.live_scores_api import _streak

        page = {
            "team": {
                "record": {
                    "items": [{"type": "total", "stats": [{"name": "streak", "value": -2.0}]}]
                }
            }
        }
        self.assertEqual(_streak(page), "L2")
        page["team"]["record"]["items"][0]["stats"][0]["value"] = 5.0
        self.assertEqual(_streak(page), "W5")

    def test_the_last_results_and_a_meeting(self):
        from apis.live_scores_api import season_context

        sched = _schedule("KC", [("2026-09-15", "DEN", 31, 10, True), ("2026-10-04", "SEA", 30, 27, False),
                                 ("2026-10-18", "LAC", 22, 6, True), ("2026-10-26", "SEA", None, None, False)])  # fmt: skip
        got = season_context(sched, "KC", opponent="SEA")
        self.assertEqual(got["last"][0], "W 22-6 vs LAC (Oct 18)")
        self.assertIn("W 30-27 at SEA (Oct 4)", got["last"])
        self.assertEqual(got["met"], "W 30-27 at SEA (Oct 4)")

    def test_the_facts_print_them(self):
        from core.signal_facts import format_signal_facts

        sig = {"active": True, "connected": True, "data": {"teams": [{"team": "Kansas City Chiefs", "record": "5-0", "streak": "W5",
               "last": ["W 22-6 vs LAC (Oct 18)"], "met": "", "next_game": "", "league": "nfl"}]}}  # fmt: skip
        text = format_signal_facts({"live_scores": sig})
        self.assertIn("streak W5", text)
        self.assertIn("last results: W 22-6 vs LAC (Oct 18)", text)


class SeasonFetchTests(unittest.TestCase):
    """#1369: the NFL signal adds each team's season when the switch is on (the suite's is off)."""

    def test_the_signal_carries_the_season(self):
        import json
        from pathlib import Path

        from apis import live_scores_api

        team = json.loads((Path(__file__).resolve().parent / "fixtures" / "signal_payloads" / "live_scores.json")
                          .read_text(encoding="utf-8"))["response"]  # fmt: skip
        sched = _schedule("LAC", [("2026-10-05", "DEN", 20, 23, True)])
        with (
            patch.dict(os.environ, {"ESPN_SEASON_CONTEXT": "true"}),
            patch("sports.espn.get_team", return_value=team),
            patch("sports.espn.get_scoreboard", return_value={"events": []}),
            patch("sports.espn.get_schedule", return_value=sched) as fetch,
        ):
            sig = live_scores_api.get_live_scores_signal(
                "How the 0-4 chargers can turn it around this year"
            )
        fetch.assert_called()
        self.assertEqual(sig["data"]["teams"][0]["last"], ["L 20-23 vs DEN (Oct 5)"])


class ApiSportsFactsTests(unittest.TestCase):
    """#1568: api_sports' team-search lines are context, never raw JSON."""

    def test_no_raw_json_and_context_tier(self):
        from core.grounding_tiers import build_tiered_corpus
        from core.signal_facts import format_signal_facts

        sig = {"active": True, "connected": True, "data": {"connected": True, "source": "api_sports",
               "lines": ["Manchester City (England) — API-SPORTS"]}}  # fmt: skip
        text = format_signal_facts({"api_sports": sig})
        self.assertNotIn("api_sports data:", text)
        self.assertIn("Manchester City (England)", text)
        tiers = [
            tier
            for tier, line in build_tiered_corpus(signal_facts=text).lines
            if "Manchester" in line
        ]
        self.assertEqual(tiers, ["context"])


class RuleEffectTests(unittest.TestCase):
    """#1454: the first-line rule (#1311, from 2026-10-18) read before and after."""

    def test_before_and_after(self):
        from analytics.hook_learning import rule_effect

        def row(day, stayed, hook):
            return {
                "made": datetime(2026, 10, day, tzinfo=timezone.utc),
                "stayed": stayed,
                "hook": hook,
            }

        rows = [row(10, 0.20, "The Chargers are 0-4."), row(11, 0.22, "Here is the news."),
                row(12, 0.24, "A trade happened."), row(19, 0.30, "Seattle will win because the pass rush wins."),
                row(20, 0.32, "The Bears win this one because their defense travels."), row(21, 0.28, "Fans react.")]  # fmt: skip
        got = rule_effect(rows)
        self.assertEqual((got["before"]["n"], got["after"]["n"]), (3, 3))
        self.assertAlmostEqual(got["before"]["stayed"], 0.22)
        self.assertAlmostEqual(got["after"]["stayed"], 0.30)
        self.assertGreater(got["after"]["calls"], got["before"]["calls"])

    def test_ops_hooks_prints_it(self):
        from analytics import hook_learning

        with (
            patch.object(hook_learning, "_rows", return_value=[]),
            patch.object(hook_learning, "rule_effect",
                         return_value={"before": {"n": 3, "stayed": 0.22, "calls": 0.0},
                                       "after": {"n": 3, "stayed": 0.30, "calls": 0.67}}),
        ):  # fmt: skip
            lines = hook_learning.hook_table_lines("tapin")
        self.assertTrue(
            any("First-line rule" in line and "22%" in line and "30%" in line for line in lines)
        )


class PreviewShapeTests(unittest.TestCase):
    """#1366 (decision 78): three preview shapes, rotated as an experiment."""

    def test_the_lever(self):
        from core.experiment_levers import arms, directive, kind, levers

        self.assertIn("preview_shape", levers())
        self.assertEqual(kind("preview_shape"), "preview")
        self.assertEqual(sorted(arms("preview_shape")), ["matchup", "stakes", "x_factor"])
        self.assertTrue(all(directive("preview_shape", arm) for arm in arms("preview_shape")))

    def test_only_a_preview_draws_a_shape(self):
        from core import batch_generation

        with patch(
            "core.experiments.next_arm",
            return_value=("preview_shape", "stakes", "SHAPE: the stakes"),
        ) as pick:
            self.assertEqual(batch_generation.preview_shape_arm("tapin", ""), None)
            pick.assert_not_called()
            arm = batch_generation.preview_shape_arm(
                "tapin", "This game has not been played yet - it is on Oct 26."
            )
        self.assertEqual(arm, ("preview_shape", "stakes", "SHAPE: the stakes"))
        pick.assert_called_once_with("tapin", kind="preview")


class DullOpenerTests(unittest.TestCase):
    """#1357 (decision 78): no number, no name and no call in three sentences is a warning."""

    def test_dull_and_not(self):
        from core.batch_review import dull_opener

        self.assertTrue(
            dull_opener(
                "This is a big week. Things are changing fast. Fans are excited. More soon."
            )
        )
        self.assertFalse(dull_opener("The Chiefs are 5-0. Seattle is next. Fans are excited."))
        self.assertFalse(
            dull_opener("Nobody saw this coming. Seattle will win because the pass rush wins.")
        )

    def test_review_shows_it_and_never_holds(self):
        from core import batch_review

        draft = batch_review.PendingDraft(
            "f", {"run_id": 1, "title": "t", "topic": "t", "authenticity_verdict": "ok"},
            "This is a big week. Things are changing fast. Fans are excited.",
        )  # fmt: skip
        shown: list[str] = []
        with patch.object(batch_review, "authenticity_now", return_value=("ok", "")):
            batch_review._show(draft, 1, 1, shown.append)
            reason = batch_review.unattended_block_reason(draft)
        self.assertTrue(any("dull opener" in line for line in shown))
        self.assertNotIn("dull", reason)


class LeagueRotationTests(unittest.TestCase):
    """#1449: the menu's previews take leagues in turn."""

    def test_leagues_alternate_within_a_kind(self):
        from core.best_bet import _alternate_leagues

        rows = [("2026-10-26", "nfl1", "nfl"), ("2026-10-26", "nfl2", "nfl"), ("2026-10-27", "nba1", "nba"),
                ("2026-10-28", "nfl3", "nfl"), ("2026-10-28", "nba2", "nba")]  # fmt: skip
        self.assertEqual(
            [b for _d, b, _l in _alternate_leagues(rows)], ["nfl1", "nba1", "nfl2", "nba2", "nfl3"]
        )


class PauseUntilTests(unittest.TestCase):
    """#1338: one line stops overnight until a date."""

    def test_paused_until_then_running_again(self):
        from core import overnight_pause

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "overnight.paused")
            self.assertTrue(overnight_pause.set_paused(True, path=path, until=date(2026, 11, 2)))
            self.assertTrue(overnight_pause.is_paused(path=path, today=date(2026, 11, 2)))
            self.assertIn(
                "until Mon Nov 2", overnight_pause.status_line(path=path, today=date(2026, 10, 30))
            )
            self.assertFalse(overnight_pause.is_paused(path=path, today=date(2026, 11, 3)))
            self.assertFalse(os.path.exists(path))

    def test_ops_overnight_takes_the_date(self):
        from scripts.ops import build_parser

        args = build_parser().parse_args(["overnight", "--pause-until", "2026-11-02"])
        self.assertEqual(args.pause_until, "2026-11-02")


if __name__ == "__main__":
    unittest.main()
