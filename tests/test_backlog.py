"""#949: `ops backlog` - fresh best bets into two weeks of scheduled videos (operator, 2026-10-03).

The operator wants to be away from the PC while videos keep publishing. A video uploaded
private with `publishAt` goes public on YouTube's side, so only the drafting, rendering and
uploading need the PC. Nothing could fill more than the next 7 days:
`core/spaced_queue.plan_spaced_uploads` stopped at the cadence cap of the current window,
and every draft waited for a human yes in `batch-review`.

Operator calls: auto-render a draft that clears every gate, the operator vetoes (`ops
backlog pull`); two weeks, about ten videos; news topics take the first slots and are
dropped when their slot is more than 3 days out, evergreen topics fill the rest.

#950 found answering the same question: `scripts/schedule_auto_generate.ps1` ran the repo
from a hard-coded `C:\\Users\\jonma\\OneDrive\\Desktop\\content_machine`.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _daily_slots(channel_id, topic="", *, run_id=None, after=None):
    """A slot every day at 18:00 UTC strictly after `after`."""
    base = (after or NOW).replace(hour=18, minute=0, second=0, microsecond=0)
    return base if base > (after or NOW) else base + timedelta(days=1)


def _option(topic, source):
    from core.best_bet import BestBetResult

    return BestBetResult(topic=topic, domain="gaming", avg_engaged_rate=0.0, source=source,
                         supporting_runs=0, rationale="")  # fmt: skip


class _Stores(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        self.drafts = os.path.join(self.d, "drafts")
        os.makedirs(self.drafts)
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", os.path.join(self.d, "log.json")),
            patch("core.batch_generation._drafts_dir", return_value=self.drafts),
            patch("analytics.post_timing.planned_post_time", side_effect=_daily_slots),
            patch(
                "storage.repositories.jobs.get_job_repository",
                return_value=SimpleNamespace(list_upload_jobs=lambda c: []),
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _scheduled(self, when, vid):
        from storage.repositories.publish_log import get_publish_log_repository

        get_publish_log_repository().create(
            {
                "channel_id": "tapin",
                "status": "scheduled",
                "youtube_video_id": vid,
                "published_at": when,
                "content_run_id": None,
                "detail": vid,
            }
        )

    def _draft(self, run_id, topic, **meta):
        folder = os.path.join(self.drafts, f"d{run_id}")
        os.makedirs(folder)
        with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
            f.write(f"# {topic}\n\n## Script\n\nA script about {topic} that is long enough.\n")
        body = {"topic": topic, "variant": topic, "title": topic, "run_id": run_id,
                "channel_id": "tapin", "length_choice": "1", "hook_verdict": "strong",
                "authenticity_verdict": "ok", "claim_verification": {},
                # A draft made just now: the staleness gate measures age on the real clock,
                # so a fixed date turned this test red two days after it was written.
                "created_at": datetime.now().isoformat(timespec="seconds")}  # fmt: skip
        body.update(meta)
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(body, f)
        return SimpleNamespace(topic=topic, ok=True, run_id=run_id, path=folder, error="")


class CapTests(unittest.TestCase):
    def test_a_slot_never_makes_any_seven_days_hold_more_than_the_cap(self):
        from publishing.backlog import fits_cap

        week = [NOW + timedelta(days=i) for i in range(5)]
        self.assertFalse(fits_cap(week, NOW + timedelta(days=5), 5))
        self.assertTrue(fits_cap(week, NOW + timedelta(days=7, hours=1), 5))
        # The window that matters can start before the slot: 5 videos in the 7 days ahead.
        ahead = [NOW + timedelta(days=i) for i in range(1, 6)]
        self.assertFalse(fits_cap(ahead, NOW, 5))


class SlotTests(_Stores):
    def test_two_weeks_fill_around_what_is_already_scheduled(self):
        from publishing.backlog import fits_cap, plan_backlog_slots

        self._scheduled(NOW + timedelta(days=1, hours=8), "s1")
        self._scheduled(NOW + timedelta(days=2, hours=8), "s2")
        slots = plan_backlog_slots("tapin", weeks=2, now=NOW)
        self.assertEqual(len(slots), 8)
        everything = [*slots, NOW + timedelta(days=1, hours=8), NOW + timedelta(days=2, hours=8)]
        for slot in slots:
            others = [t for t in everything if t != slot]
            self.assertTrue(fits_cap(others, slot, 5), slot)
        self.assertLessEqual(max(slots), NOW + timedelta(days=14))


class TopicTests(_Stores):
    def test_news_first_and_dropped_past_three_days_evergreen_after(self):
        from publishing.backlog import pick_backlog_topics

        slots = [NOW + timedelta(days=i, hours=6) for i in range(1, 7)]
        options = [
            _option("GTA 6 trailer 3 drops", "trending"),
            _option("Elden Ring Nightreign tier list", "analytics"),
            _option("Nintendo Direct recap", "trending"),
            _option("Silksong boss guide", "angle"),
            _option("Game Awards nominees", "calendar"),
            _option("Marvel Rivals meta explained", "continuity"),
            _option("Hollow Knight lore", "analytics"),
            _option("Fortnite chapter leak", "trending"),
        ]
        with patch("core.best_bet.get_best_bets", return_value=options):
            plan = pick_backlog_topics("tapin", slots, now=NOW)
        kinds = [(item.kind, item.topic) for item in plan.items]
        self.assertEqual([k for k, _t in kinds[:3]], ["news", "news", "news"])
        self.assertEqual([k for k, _t in kinds[3:]], ["evergreen"] * 3)
        self.assertEqual([d.topic for d in plan.dropped], ["Fortnite chapter leak"])
        self.assertIn("no open slot left within 3 days", plan.dropped[0].reason)
        self.assertEqual(plan.items[0].pick["by"], "backlog")


class GateTests(_Stores):
    def test_each_failed_gate_is_named(self):
        from core.batch_review import pending_drafts
        from publishing.backlog import backlog_gate

        claims = {"unsupported": ["Topuria retired in 2019"], "unsupported_types": [""]}
        self._draft(1, "A good one")
        self._draft(2, "Bad claim", claim_verification=claims)
        self._draft(3, "Weak hook", hook_verdict="weak")
        drafts = {d.run_id: d for d in pending_drafts("tapin", root=self.drafts)}
        grades = {1: "B", 2: "A", 3: "C"}
        with patch(
            "core.video_grade.grade_run",
            side_effect=lambda r: SimpleNamespace(letter=grades[r], score=80),
        ):
            self.assertEqual(backlog_gate(drafts[1]), [])
            self.assertIn("unsupported claim", " ".join(backlog_gate(drafts[2])))
            reasons = " ".join(backlog_gate(drafts[3]))
        self.assertIn("grade C", reasons)
        self.assertIn("weak hook", reasons)


class RunTests(_Stores):
    def _plan(self):
        from publishing.backlog import BacklogItem, TopicPlan

        slots = [NOW + timedelta(days=1, hours=6), NOW + timedelta(days=2, hours=6)]
        return TopicPlan(
            items=[
                BacklogItem(
                    slot=slots[0], topic="GTA 6 trailer 3", kind="news", pick={"by": "backlog"}
                ),
                BacklogItem(slot=slots[1], topic="Silksong boss guide", kind="evergreen", pick={}),
            ],
            dropped=[],
        )

    def _run(self, *, answer="y", dry_run=False, outcomes=None):
        from publishing import backlog

        out = io.StringIO()
        with (
            patch.object(
                backlog, "plan_backlog_slots", return_value=[i.slot for i in self._plan().items]
            ),
            patch.object(backlog, "pick_backlog_topics", return_value=self._plan()),
            patch("core.batch_generation.run_batch", return_value=outcomes or []) as drafted,
            patch("core.batch_review._render") as rendered,
            patch(
                "core.spaced_queue.queue_spaced_uploads",
                side_effect=lambda s, **k: [x.run_id for x in s],
            ) as queued,
            patch("core.video_grade.grade_run", return_value=SimpleNamespace(letter="B", score=80)),
            patch("core.thumbnail_pick.dual_thumbnail_enabled", return_value=False),
        ):
            summary = backlog.run_backlog(
                "tapin",
                dry_run=dry_run,
                ask=lambda _p: answer,
                print_fn=lambda *a: out.write(" ".join(map(str, a)) + "\n"),
            )
        return summary, out.getvalue(), drafted, rendered, queued

    def test_a_dry_run_plans_and_spends_nothing(self):
        _summary, text, drafted, rendered, _q = self._run(dry_run=True)
        drafted.assert_not_called()
        rendered.assert_not_called()
        self.assertIn("GTA 6 trailer 3", text)
        self.assertIn("news", text)
        self.assertIn("projected", text)
        self.assertIn("PC-day", text)

    def test_declining_spends_nothing(self):
        _summary, _text, drafted, _r, _q = self._run(answer="n")
        drafted.assert_not_called()

    def test_passes_render_into_their_slot_and_failures_wait_for_review(self):
        good = self._draft(11, "GTA 6 trailer 3")
        bad = self._draft(
            12,
            "Silksong boss guide",
            claim_verification={"unsupported": ["x"], "unsupported_types": [""]},
        )
        summary, text, _drafted, rendered, queued = self._run(outcomes=[good, bad])
        self.assertEqual(rendered.call_count, 1)
        slots = queued.call_args.args[0]
        self.assertEqual(
            [(s.run_id, s.publish_at) for s in slots], [(11, self._plan().items[0].slot)]
        )
        self.assertEqual(summary.queued, [11])
        self.assertEqual(summary.waiting, [12])
        self.assertIn("py -m scripts.ops batch-review", text)
        with open(os.path.join(good.path, "meta.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["review"]["by"], "backlog")
        with open(os.path.join(bad.path, "meta.json"), encoding="utf-8") as f:
            self.assertNotIn("review", json.load(f))  # still pending for batch-review

    def test_the_cost_and_upload_days_are_measured(self):
        from publishing.backlog import upload_days

        self.assertEqual(upload_days(10), 2)  # 10,000 units / 1,600 per upload = 6 a day
        self.assertEqual(upload_days(6), 1)


class VetoTests(_Stores):
    def test_pull_cancels_a_queued_upload(self):
        from publishing.backlog import pull

        updates = []
        job = SimpleNamespace(id=7, content_run_id=11, status="pending", job_type="upload")
        repo = SimpleNamespace(
            list_upload_jobs=lambda c: [job], update=lambda i, d: updates.append((i, d))
        )
        with patch("storage.repositories.jobs.get_job_repository", return_value=repo):
            text = pull("tapin", 11)
        self.assertEqual(updates[0][0], 7)
        self.assertEqual(updates[0][1]["status"], "failed")
        self.assertIn("will not upload", text)

    def test_pull_on_an_uploaded_video_says_what_it_needs(self):
        from publishing.backlog import pull
        from storage.repositories.publish_log import get_publish_log_repository

        get_publish_log_repository().create(
            {
                "channel_id": "tapin",
                "status": "scheduled",
                "youtube_video_id": "v9",
                # list_future_scheduled reads the real clock; a fixed date went stale 2026-10-06.
                "published_at": datetime.now(timezone.utc) + timedelta(days=3),
                "content_run_id": 11,
                "detail": "x",
            }
        )
        with patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": ""}):
            text = pull("tapin", 11)
        self.assertIn("v9", text)
        self.assertIn("YOUTUBE_UPLOAD_ENABLED", text)

    def test_the_ops_verb(self):
        from scripts.ops import COMMANDS

        with redirect_stdout(io.StringIO()) as out:
            code = COMMANDS["backlog"][1](
                Namespace(
                    channel="tapin", target="list", run_id=0, dry_run=False, yes=False, weeks=2
                )
            )
        self.assertEqual(code, 0)
        self.assertIn("Backlog - tapin", out.getvalue())


class ScheduledTaskTests(unittest.TestCase):
    def test_the_auto_generate_task_runs_this_checkout(self):
        with open("scripts/schedule_auto_generate.ps1", encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("OneDrive\\Desktop", text)
        self.assertIn("$PSScriptRoot", text)


if __name__ == "__main__":
    unittest.main()
