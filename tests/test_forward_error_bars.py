"""#560 (operator's choice: forward-only, withhold nothing): honest error bars.

A true hold-out would withhold videos from the recommenders, and at ~10 measured videos
that delays every learned recommendation. The ledger already freezes each claim at upload,
before its outcome exists - so every non-backfilled row is an honest forward error. What
was not honest: a backfilled entry's length and post-time claims were fitted on data that
included the video's own outcome (only the engaged-rate claim left it out), and the report
mixed backfilled rows into the headline error. Now backfilled claims leave the video out,
the headline error is forward rows only, backfilled rows are shown apart, and the
predictor's claimed band (an in-sample spread) is set beside its forward error.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_prediction_ledger import _Ledger

SLOT = datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)


class LeaveOneOutTests(_Ledger):
    def test_a_backfilled_length_claim_leaves_the_video_out(self):
        from core.predictions.ledger import freeze

        with patch("core.length_recommender.get_recommended_length") as rec:
            rec.return_value = SimpleNamespace(
                length_choice="2", source="analytics", avg_engaged_rate=0.3, supporting_runs=6
            )
            freeze(9, "tapin", backfilled=True)
            freeze(1, "tapin")
        backfill, forward = rec.call_args_list
        self.assertEqual(backfill.kwargs.get("exclude_run_id"), 9)
        self.assertIsNone(forward.kwargs.get("exclude_run_id"))

    def test_a_backfilled_post_claim_leaves_the_video_out(self):
        from core.predictions.ledger import freeze

        claim = {"used_at": SLOT.isoformat(), "on_slot": True, "expected": 0.2,
                 "source": "analytics", "n": 3}  # fmt: skip
        with (
            patch("core.predictions.ledger._used_at", return_value=SLOT),
            patch("analytics.post_timing.slot_claim", return_value=claim) as asked,
        ):
            freeze(9, "tapin", backfilled=True)
        self.assertEqual(asked.call_args.kwargs.get("exclude_run_id"), 9)


class SampleTests(unittest.TestCase):
    def test_length_samples_can_leave_one_out(self):
        from core.length_recommender import _collect_length_samples

        runs = [SimpleNamespace(id=i, timings_json='{"length_preset": "2"}') for i in (1, 2, 3)]
        logs = [
            SimpleNamespace(content_run_id=i, metrics_json='{"engaged_rate": 0.3}')
            for i in (1, 2, 3)
        ]
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_timed_outcomes=lambda c: logs),
            ),
        ):
            self.assertEqual(len(_collect_length_samples("tapin")), 3)
            self.assertEqual(len(_collect_length_samples("tapin", exclude_run_id=2)), 2)

    def test_post_time_samples_can_leave_one_out(self):
        from analytics.post_timing import _collect_timed_samples

        logs = [
            SimpleNamespace(content_run_id=i, published_at=SLOT, detail="",
                            metrics_json='{"engaged_rate": 0.3}')
            for i in (1, 2)
        ]  # fmt: skip
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=SimpleNamespace(list_timed_outcomes=lambda c: logs),
        ):
            self.assertEqual(len(_collect_timed_samples("tapin", exclude_run_id=1)), 1)


class ReportTests(_Ledger):
    def test_the_headline_is_forward_rows_only(self):
        from core.predictions.ledger import freeze, report_lines

        for run_id in (1, 2, 3, 4):
            freeze(run_id, "tapin")
        freeze(9, "tapin", backfilled=True)
        text = "\n".join(report_lines("tapin"))
        self.assertIn("engagement predictor (frozen before the outcome): collecting (n=4", text)
        self.assertIn("backfilled, left out of the fit: collecting (n=1", text)

    def test_the_claimed_band_sits_beside_the_forward_error(self):
        from core.predictions.ledger import freeze, report_lines

        for run_id in (1, 2, 3, 4, 9):
            freeze(run_id, "tapin")
        text = "\n".join(report_lines("tapin"))
        self.assertIn("claimed band", text)
        self.assertIn("inside the band", text)


if __name__ == "__main__":
    unittest.main()
