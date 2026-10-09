"""#1000: a render past the grounding gate must not go public at its slot.

Run 120 (job 52): after "Render anyway? y" the privacy menu offered only private and
unlisted ("this upload stays unlisted until the flagged claim is fixed"), but option 4
("Schedule on YouTube") still sent `privacyStatus: private` + `publishAt`, which YouTube
turns public at the slot. The video went public on Oct 7 22:00 EDT with its flagged claim.

- The menu (`core.ui.prompt_upload_plan`): option 4 on a flagged render queues the upload
  for the slot, unlisted, with no `youtube_publish_at`, and says why.
- The publisher (`publishing.youtube_publisher.hold_flagged_schedule`): a queued job whose
  run - or the run a Short was cut from - carries `grounding_override` loses its
  `publish_at` and uploads unlisted, whatever the job says. Older jobs already in the queue
  are caught here.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

SLOT = datetime(2026, 10, 9, 2, 0, tzinfo=timezone.utc)


class MenuTests(unittest.TestCase):
    def _plan(self, answers, *, override):
        from core.ui import prompt_upload_plan

        inputs = iter(answers)
        printed: list[str] = []
        with (
            patch("core.ui.display_upload_queue"),
            patch("analytics.post_timing.next_optimal_post_time", return_value=SLOT),
            patch("analytics.post_timing.planned_post_time", return_value=SLOT),
            patch("analytics.post_timing.format_scheduled_local", return_value="Thu 10:00 PM"),
        ):
            plan = prompt_upload_plan(
                channel_id="tapin",
                topic="t",
                print_fn=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: next(inputs),
                grounding_override=override,
            )
        return plan, "\n".join(printed)

    def test_option_four_on_a_flagged_render_never_sets_publish_at(self):
        plan, text = self._plan(["4", "2"], override=True)
        self.assertEqual(plan.mode, "queue")
        self.assertIsNone(plan.youtube_publish_at)
        self.assertEqual(plan.privacy_status, "unlisted")
        self.assertEqual(plan.scheduled_at, SLOT)
        self.assertIn("will not go public", text)

    def test_private_stays_private(self):
        plan, _text = self._plan(["4", "1"], override=True)
        self.assertIsNone(plan.youtube_publish_at)
        self.assertEqual(plan.privacy_status, "private")

    def test_a_clean_render_still_schedules_on_youtube(self):
        plan, _text = self._plan(["4", "3"], override=False)
        self.assertEqual(plan.youtube_publish_at, SLOT)


class PublisherTests(unittest.TestCase):
    def _request(self, **kw):
        from publishing.base import PublishRequest

        base = {"file_path": "x.mp4", "title": "T", "description": "", "tags": [],
                "privacy_status": "private",
                "publish_at": datetime.now(timezone.utc) + timedelta(hours=5)}  # fmt: skip
        base.update(kw)
        return PublishRequest(**base)

    def test_a_flagged_run_loses_publish_at(self):
        from publishing.youtube_publisher import hold_flagged_schedule

        with patch("publishing.go_public.load_features", return_value={"grounding_override": 1}):
            held = hold_flagged_schedule(self._request(), 120)
        self.assertIsNone(held.publish_at)
        self.assertEqual(held.privacy_status, "private")  # never made more public

    def test_a_short_from_a_flagged_run_is_held_too(self):
        from publishing.youtube_publisher import hold_flagged_schedule

        rows = {121: {"parent_run_id": 120}, 120: {"grounding_override": 1}}
        with patch("publishing.go_public.load_features", side_effect=lambda rid: rows.get(rid, {})):
            held = hold_flagged_schedule(self._request(privacy_status="public"), 121)
        self.assertIsNone(held.publish_at)
        self.assertEqual(held.privacy_status, "unlisted")

    def test_a_clean_run_keeps_its_slot(self):
        from publishing.youtube_publisher import hold_flagged_schedule

        req = self._request()
        with patch("publishing.go_public.load_features", return_value={}):
            self.assertIs(hold_flagged_schedule(req, 7), req)

    def test_publish_applies_it(self):
        import inspect

        from publishing.youtube_publisher import YouTubePublisher

        src = inspect.getsource(YouTubePublisher.publish)
        self.assertIn("hold_flagged_schedule(request, content_run_id)", src)


if __name__ == "__main__":
    unittest.main()
