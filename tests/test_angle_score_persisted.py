"""#819: composite does not predict engagement (r=-0.15, n=12); the obvious successor,
`angle_scores` (#807), has 0 recorded values - because nothing ever persisted it.

`run_discovery` computes `DiscoveryResult.angle_scores` and `_finalize_run` passes
`discovery.meta` (which holds `angle_spread`) into timings, but the scores themselves
never reach `record_content_run`, `build_quality` or the trace. A tie-break that cannot
be measured cannot be chosen. This makes the scores land in `features_json` and the
chosen variant's score in the quality dict, so the calibration join can correlate it
once there is an n. The tie itself (`best_variant_index`) does not move.

Per tests/CLAUDE.md, driving `_finalize_run` patches the ledger writes.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.pipeline import DiscoveryResult, PipelineResult


def _discovery() -> DiscoveryResult:
    return DiscoveryResult(
        input_topic="GTA 6",
        base_signals={},
        evaluated=[("GTA 6 delay", 90.0, {}), ("GTA 6 price", 90.0, {})],
        raw_scores={},
        angle_scores={"GTA 6 delay": 0.71, "GTA 6 price": 0.42},
        timings={},
        meta={},
        channel_id="tapin",
    )


def _result() -> PipelineResult:
    return PipelineResult(
        topic="GTA 6 price",
        score=90.0,
        signals={},
        aborted=True,
        abort_reason="proceed_video=False",
    )


class TestAngleScoresReachTheRecord(unittest.TestCase):
    def test_features_carry_the_scores_and_the_chosen_one(self) -> None:
        from core import pipeline

        captured: dict = {}

        def _record(**kwargs):
            captured.update(kwargs)
            return 1

        with (
            patch.object(pipeline, "record_content_run", side_effect=_record),
            patch.object(pipeline, "build_quality", return_value={}),
            patch.object(pipeline, "persist_quality"),
            patch.object(pipeline, "write_run_trace"),
            patch("core.run_trace.write_full_script", create=True),
        ):
            pipeline._finalize_run(
                channel_id="tapin", input_topic="GTA 6", result=_result(), discovery=_discovery()
            )
        features = captured["features"]
        self.assertEqual(features["angle_scores"], {"GTA 6 delay": 0.71, "GTA 6 price": 0.42})
        self.assertEqual(features["angle_score"], 0.42, "the chosen variant's own score")

    def test_quality_copies_the_chosen_angle_score(self) -> None:
        from core.run_quality import build_quality

        quality = build_quality(
            script="A real script with a few words in it.",
            channel_id="tapin",
            features={"angle_score": 0.42},
            recent=[],
        )
        self.assertEqual(quality.get("angle_score"), 0.42)

    def test_no_angle_scores_leaves_nothing_behind(self) -> None:
        from core.run_quality import build_quality

        quality = build_quality(script="A real script.", channel_id="tapin", features={}, recent=[])
        self.assertNotIn("angle_score", quality)


class TestCalibrationCollectsIt(unittest.TestCase):
    def test_angle_line_says_collecting_until_it_has_n(self) -> None:
        from core.grade_calibration import angle_line, build_calibration
        from tests.test_component_calibration import _patched, _quality, _run

        runs = [_run(i, _quality(60.0, 80.0)) for i in range(1, 7)]
        rates = {i: 0.01 * i for i in range(1, 7)}
        with _patched(runs, rates):
            report = build_calibration("tapin")
        self.assertEqual(report.angle_correlation, (None, 0))
        line = angle_line(report)
        self.assertIn("collecting", line)
        self.assertIn("0 of 6", line)


if __name__ == "__main__":
    unittest.main()
