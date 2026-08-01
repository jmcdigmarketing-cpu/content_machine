"""Post-generation length prompt + Queue-manager recovery of rendered MP4s.

Both use injected print_fn/input_fn, so they test without a terminal, DB, or network
(per tests/CLAUDE.md — all DB-backed helpers are patched).
"""

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from core.ui import prompt_proceed_or_length, prompt_upload_plan, run_queue_manager_interactive


def _seq(*items):
    """An input_fn that returns the given answers in order."""
    it = iter(items)
    return lambda *_a, **_k: next(it)


def _sink():
    """A print_fn that swallows output."""
    return lambda *_a, **_k: None


class TestProceedOrLength(unittest.TestCase):
    def test_render(self):
        self.assertEqual(
            prompt_proceed_or_length("2", input_fn=_seq("y"), print_fn=_sink()),
            ("render", "2"),
        )

    def test_longer_and_shorter_nudge(self):
        self.assertEqual(
            prompt_proceed_or_length("2", input_fn=_seq("+"), print_fn=_sink()),
            ("relength", "3"),
        )
        self.assertEqual(
            prompt_proceed_or_length("2", input_fn=_seq("-"), print_fn=_sink()),
            ("relength", "1"),
        )

    def test_shorter_clamps_at_short(self):
        self.assertEqual(
            prompt_proceed_or_length("1", input_fn=_seq("-"), print_fn=_sink()),
            ("relength", "1"),
        )

    def test_explicit_length_choice(self):
        self.assertEqual(
            prompt_proceed_or_length("2", input_fn=_seq("4"), print_fn=_sink()),
            ("relength", "4"),
        )

    def test_stop_on_n_or_empty(self):
        self.assertEqual(
            prompt_proceed_or_length("2", input_fn=_seq("n"), print_fn=_sink()),
            ("stop", "2"),
        )
        self.assertEqual(
            prompt_proceed_or_length("2", input_fn=_seq(""), print_fn=_sink()),
            ("stop", "2"),
        )


class TestQueueManagerRecovery(unittest.TestCase):
    def _patches(self, *, recyclable, candidates):
        profile = SimpleNamespace(privacy_status_default="private")
        return (
            patch("core.ui.resolve_channel_id", side_effect=lambda c: c or "tapin"),
            patch("core.ui.get_channel_profile", return_value=profile),
            patch("core.ui.display_upload_queue"),
            patch("analytics.queue_manager.list_requeue_candidates", return_value=candidates),
            patch("scripts.requeue_upload.list_recyclable", return_value=recyclable),
        )

    def test_recover_queues_upload_job(self):
        run = SimpleNamespace(
            id=59,
            title="France vs England",
            selected_topic="france",
            description="desc",
            tags_json='["a", "b"]',
        )
        enqueue = MagicMock(return_value=SimpleNamespace(id=123))
        p_chan, p_prof, p_queue, p_cands, p_recyc = self._patches(recyclable=[run], candidates=[])
        with (
            p_chan,
            p_prof,
            p_queue,
            p_cands,
            p_recyc,
            patch("scripts.requeue_upload._resolve_mp4_path", return_value="C:/x/video.mp4"),
            patch("storage.repositories.jobs.enqueue_upload_job", enqueue),
        ):
            # No candidates → straight into recovery. Pick #1, queue now, private.
            run_queue_manager_interactive("tapin", print_fn=_sink(), input_fn=_seq("1", "1", "1"))

        enqueue.assert_called_once()
        kw = enqueue.call_args.kwargs
        self.assertEqual(kw["content_run_id"], 59)
        self.assertEqual(kw["file_path"], "C:/x/video.mp4")
        self.assertEqual(kw["privacy_status"], "private")
        self.assertIsNone(kw["youtube_publish_at"])  # queue-now, not scheduled
        self.assertEqual(kw["tags"], ["a", "b"])

    def test_nothing_to_recover_enqueues_nothing(self):
        enqueue = MagicMock()
        p_chan, p_prof, p_queue, p_cands, p_recyc = self._patches(recyclable=[], candidates=[])
        with (
            p_chan,
            p_prof,
            p_queue,
            p_cands,
            p_recyc,
            patch("storage.repositories.jobs.enqueue_upload_job", enqueue),
        ):
            run_queue_manager_interactive("tapin", print_fn=_sink(), input_fn=_seq())
        enqueue.assert_not_called()


class TestUploadPlanOption3(unittest.TestCase):
    """Option 3 now takes a clock time (or minutes), not just minutes-from-now."""

    # The target must stay in the FUTURE relative to the wall clock: prompt_upload_plan
    # clamps any past time to now+1min ("never schedule in the past"). A hardcoded date
    # here silently expires — this test failed every CI run from 2026-07-25 onward for
    # exactly that reason. Always derive it from now.
    @staticmethod
    def _future_local(days: int = 3, hour: int = 18):
        """A fixed clock time `days` ahead, in the channel's tz (tapin = America/New_York)."""
        return (datetime.now(ZoneInfo("America/New_York")) + timedelta(days=days)).replace(
            hour=hour, minute=0, second=0, microsecond=0
        )

    def _run(self, time_input):
        # timing=3, privacy=default(""), then the time string.
        with (
            patch.dict(os.environ, {"USE_LEARNED_POST_SLOTS": "0"}, clear=False),
            patch("core.ui.display_upload_queue"),
            patch(
                "analytics.post_timing.next_optimal_post_time",
                return_value=self._future_local(days=1, hour=22).astimezone(timezone.utc),
            ),
        ):
            return prompt_upload_plan(
                channel_id="tapin",
                topic="",
                print_fn=_sink(),
                input_fn=_seq("3", "", time_input),
            )

    def test_explicit_datetime_schedules_that_time(self):
        # An explicit date+time is honoured verbatim, including the local→UTC conversion.
        target_local = self._future_local()
        plan = self._run(target_local.strftime("%Y-%m-%d %H:%M"))
        self.assertEqual(plan.mode, "queue")
        self.assertEqual(
            plan.scheduled_at.astimezone(timezone.utc),
            target_local.astimezone(timezone.utc),
        )

    def test_bare_number_falls_back_to_minutes(self):
        plan = self._run("45")
        self.assertEqual(plan.mode, "queue")
        # ~45 minutes from now (allow scheduling slack), and safely in the future.
        delta = (plan.scheduled_at - datetime.now(timezone.utc)).total_seconds()
        self.assertGreater(delta, 40 * 60)
        self.assertLess(delta, 50 * 60)


if __name__ == "__main__":
    unittest.main()
