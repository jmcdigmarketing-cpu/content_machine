"""#559: the engagement prediction is recorded when the video publishes, not refitted.

`analytics/youtube_metrics.refresh_publish_metrics` called `predict_engaged_rate` at every
metrics sync, and `engagement_predictor._training_rows` included the video's own
outcome. So a video's "surprise" (actual minus predicted) was fitted on the answer, and it
moved every time a later video changed the fit - a number that can never be wrong cannot
measure anything. Now the prediction is frozen once in the run's features
(`core/predictions/ledger.py`), fitted without the video itself; a video published before
this gets a leave-one-out prediction once, stamped `backfilled`, and is never refitted.
"""

from __future__ import annotations

import json
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord


def _run(run_id: int, hook: float, auth: float) -> ContentRunRecord:
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="t",
        selected_topic=f"topic {run_id}",
        status="published",
        composite_score=60.0,
        quality_json=json.dumps({"hook_score": hook, "authenticity_score": auth}),
        timings_json=json.dumps({"length_choice": "2"}),
    )


class _Runs:
    def __init__(self, runs):
        self.runs = {r.id: r for r in runs}

    def list_for_channel(self, channel_id, *, status=None):
        return list(self.runs.values())

    def get(self, run_id):
        return self.runs.get(int(run_id))

    def update(self, run_id, data):
        run = self.runs[int(run_id)]
        for key, value in data.items():
            setattr(run, key, value)
        return run


class _Case(unittest.TestCase):
    RATES: ClassVar[dict[int, float]] = {1: 0.10, 2: 0.20, 3: 0.30, 4: 0.40, 9: 0.90}

    def setUp(self):
        self.repo = _Runs([_run(1, 40, 60), _run(2, 50, 60), _run(3, 60, 75), _run(4, 70, 75),
                           _run(9, 80, 100)])  # fmt: skip
        self.rates = dict(self.RATES)
        self.stack = ExitStack()
        self.stack.enter_context(patch.dict(os.environ, {"PREDICTOR_MIN_SAMPLES": "3"}))
        self.stack.enter_context(
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=self.repo,
            )
        )
        self.stack.enter_context(
            patch("core.engagement_predictor.run_engagement_map", side_effect=lambda c: self.rates)
        )

    def tearDown(self):
        self.stack.close()

    def _features(self, run_id):
        return json.loads(self.repo.get(run_id).features_json or "{}")


class PredictorTests(_Case):
    def test_the_fit_can_leave_the_video_out(self):
        from core.engagement_predictor import _training_rows, predict_engaged_rate

        self.assertEqual(len(_training_rows("tapin")), 5)
        self.assertEqual(len(_training_rows("tapin", exclude_run_id=9)), 4)
        quality = {"hook_score": 80, "authenticity_score": 100}
        with_it = predict_engaged_rate("tapin", quality=quality)
        without = predict_engaged_rate("tapin", quality=quality, exclude_run_id=9)
        self.assertNotEqual(with_it.rate, without.rate)
        self.assertEqual(without.n, 4)


class FreezeTests(_Case):
    def test_publish_freezes_it_once(self):
        from core.predictions.ledger import freeze

        entry = freeze(9, "tapin")
        stored = self._features(9)["prediction_ledger"]
        self.assertEqual(stored["engaged_rate"]["n"], 4)  # fitted without run 9
        self.assertFalse(stored["backfilled"])
        self.assertEqual(entry, stored)

    def test_a_later_fit_does_not_move_it(self):
        from core.predictions.ledger import freeze

        first = freeze(9, "tapin")["engaged_rate"]["rate"]
        self.rates[1] = 0.80  # a later video changes the fit
        self.assertEqual(freeze(9, "tapin")["engaged_rate"]["rate"], first)

    def test_an_old_video_is_backfilled_once_and_says_so(self):
        from core.predictions.ledger import frozen_engagement

        got = frozen_engagement(9, "tapin")
        self.assertTrue(self._features(9)["prediction_ledger"]["backfilled"])
        self.rates[1] = 0.80
        self.assertEqual(frozen_engagement(9, "tapin"), got)


class SyncTests(_Case):
    def _sync(self):
        from analytics import youtube_metrics

        written: dict = {}
        row = SimpleNamespace(id=77, metrics_json="{}", published_at=None)

        class _Log:
            def find_by_idempotency(self, key):
                return row

            def update(self, log_id, data):
                written.update(json.loads(data["metrics_json"]))
                row.metrics_json = data["metrics_json"]

        with (
            patch.object(
                youtube_metrics,
                "fetch_video_metrics",
                return_value={"views": 500, "engaged_rate": 0.9, "likes": 10},
            ),
            patch.object(youtube_metrics, "get_publish_log_repository", return_value=_Log()),
            patch.object(youtube_metrics, "record_publish_outcome"),
            patch.object(youtube_metrics, "infer_domain", return_value="gaming"),
        ):
            youtube_metrics.refresh_publish_metrics(
                content_run_id=9, youtube_video_id="abc", channel_id="tapin", topic="t"
            )
        return written

    def test_the_surprise_does_not_move_between_syncs(self):
        first = self._sync()
        self.rates[1] = 0.80  # a later video lands
        second = self._sync()
        self.assertEqual(first["predicted_engaged_rate"], second["predicted_engaged_rate"])
        self.assertEqual(first["surprise"], second["surprise"])

    def test_the_sync_does_not_fit_on_the_answer(self):
        from core.engagement_predictor import predict_engaged_rate

        quality = {"hook_score": 80, "authenticity_score": 100}
        without = predict_engaged_rate("tapin", quality=quality, exclude_run_id=9)
        self.assertEqual(self._sync()["predicted_engaged_rate"], without.rate)


class GradeTests(_Case):
    def test_the_report_card_shows_the_frozen_prediction(self):
        from core.predictions.ledger import freeze
        from core.video_grade import grade_from_parts

        frozen = freeze(9, "tapin")["engaged_rate"]["rate"]
        self.rates[1] = 0.80
        quality = {"hook_score": 80, "authenticity_score": 100}
        grade = grade_from_parts(quality=quality, channel_id="tapin", run_id=9)
        self.assertEqual(grade.predicted_engaged_rate, frozen)
        self.assertIn("frozen at publish", grade.prediction_note)


class PublishTests(_Case):
    def test_the_helper_freezes(self):
        from publishing.youtube_publisher import _freeze_prediction

        _freeze_prediction(9, "tapin")
        self.assertIn("prediction_ledger", self._features(9))

    def test_the_helper_never_raises(self):
        from publishing.youtube_publisher import _freeze_prediction

        with patch("core.predictions.ledger.freeze", side_effect=RuntimeError("db down")):
            _freeze_prediction(9, "tapin")

    def test_publish_calls_it_after_the_success_row(self):
        import inspect

        from publishing.youtube_publisher import YouTubePublisher

        source = inspect.getsource(YouTubePublisher.publish)
        row = source.index('"published_at": publish_when or datetime.now(timezone.utc)')
        self.assertGreater(source.index("_freeze_prediction(content_run_id, channel_id)"), row)


if __name__ == "__main__":
    unittest.main()
