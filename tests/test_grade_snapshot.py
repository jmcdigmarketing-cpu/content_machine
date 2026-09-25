"""#808: a grade re-run is not reproducible.

`core/grade_calibration.build_calibration` re-grades every archived run with
*today's* `grade_from_parts`. `GRADE_VERSION` stamps that the rubric moved, not
what the grade was, so a v2 row's letter is silently re-issued under v4 and a
component change can never be measured against the archive.

The fix records the grade beside the inputs it was computed from. Two writers:
`build_quality` at generation time, and `merge_quality` again once the
thumbnail score lands post-render (`core/pipeline` merges `thumbnail_overall`
after the grade was first taken, so a build-time-only snapshot would disagree
with the card the operator actually saw).
"""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord


class _FakeRepo:
    """One in-memory run row, enough for persist/merge/load round-trips."""

    def __init__(self, record: ContentRunRecord) -> None:
        self.record = record

    def get(self, run_id: int) -> ContentRunRecord | None:
        return self.record if run_id == self.record.id else None

    def update(self, run_id: int, data: dict) -> ContentRunRecord | None:
        if run_id != self.record.id:
            return None
        self.record = replace(self.record, **data)
        return self.record

    def list_for_channel(self, channel_id: str, *, status: str | None = None):
        return [self.record] if self.record.channel_id == channel_id else []


def _quality_stub(**extra) -> dict:
    """A quality dict with every component the grader reads except thumbnail."""
    base = {
        "hook_score": 70,
        "hook_verdict": "strong",
        "authenticity_score": 80,
        "authenticity_gate_score": 100,
        "authenticity_verdict": "ok",
        "ungrounded_count": 0,
        "trade_warning_count": 0,
        "word_count": 150,
        "min_words": 120,
        "max_words": 180,
    }
    base.update(extra)
    return base


class TestGradeSnapshotAtBuild(unittest.TestCase):
    def test_build_quality_records_the_grade_it_produced(self) -> None:
        from core.run_quality import build_quality

        with (
            patch("core.hook_score.score_script_hook") as hook,
            patch("core.authenticity.evaluate_authenticity") as auth,
            patch("core.engagement_predictor.predict_engaged_rate", return_value=None),
        ):
            hook.return_value.score = 70
            hook.return_value.verdict = "strong"
            auth.return_value.score = 80
            auth.return_value.gate_score = 100
            auth.return_value.verdict = "ok"
            auth.return_value.semantic_overlap = 0.1
            quality = build_quality(
                script="A real script with enough words to score.",
                channel_id="tapin",
                features={"word_count": 150, "length_preset": "2"},
                composite_score=64.0,
            )

        self.assertIn("grade_score", quality)
        self.assertIn("grade_letter", quality)
        self.assertIsInstance(quality["grade_score"], float)
        components = quality.get("grade_components")
        self.assertIsInstance(components, dict)
        self.assertIn("hook", components)
        # The snapshot must carry the weight too: a component change is a change
        # of weight as often as it is a change of score.
        self.assertIn("weight", components["hook"])


class TestGradeSnapshotAfterThumbnail(unittest.TestCase):
    def test_merging_the_thumbnail_restamps_the_snapshot(self) -> None:
        """The thumbnail component arrives post-render; the grade must follow it."""
        from core.run_quality import merge_quality
        from core.video_grade import grade_from_parts

        before = _quality_stub()
        stamped = grade_from_parts(quality=before, composite_score=64.0, channel_id=None)
        before["grade_score"] = stamped.score
        record = ContentRunRecord(
            id=7,
            channel_id="tapin",
            input_topic="t",
            selected_topic="t",
            status="rendered",
            composite_score=64.0,
            quality_json=json.dumps(before),
        )
        repo = _FakeRepo(record)

        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            merge_quality(7, {"thumbnail_overall": 20.0, "thumbnail_source": "llm"})

        after = json.loads(repo.record.quality_json)
        self.assertIn("thumbnail", after.get("grade_components", {}))
        # A 20/100 thumbnail at 10% weight cannot leave the grade untouched.
        self.assertNotEqual(after["grade_score"], before["grade_score"])


class TestCalibrationPrefersTheRecordedGrade(unittest.TestCase):
    def test_a_recorded_grade_is_not_silently_re_graded(self) -> None:
        """A row graded under an older rubric keeps its own number."""
        from core.grade_calibration import build_calibration

        quality = _quality_stub(grade_version="v2", grade_score=42.0, grade_letter="D")
        record = ContentRunRecord(
            id=7,
            channel_id="tapin",
            input_topic="t",
            selected_topic="t",
            status="published",
            composite_score=64.0,
            title="a title",
            quality_json=json.dumps(quality),
        )
        repo = _FakeRepo(record)

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.engagement_predictor.run_engagement_map", return_value={7: 0.4}),
            patch("config.channels.resolve_channel_id", return_value="tapin"),
        ):
            report = build_calibration("tapin")

        self.assertEqual(len(report.rows), 1)
        row = report.rows[0]
        self.assertEqual(row.grade, 42.0)
        # ...and the drift against today's rubric is what makes the change
        # measurable, rather than invisible.
        self.assertIsNotNone(row.regraded)
        self.assertNotEqual(row.regraded, 42.0)


class TestTheSnapshotIsRead(unittest.TestCase):
    """A recorded component nothing reads back is not a record."""

    def test_the_drift_line_names_the_component_that_moved(self) -> None:
        from core.grade_calibration import CalibrationReport, CalibrationRow, snapshot_line

        row = CalibrationRow(
            run_id=7,
            title="t",
            grade=42.0,
            actual_percentile=50.0,
            engaged_rate=0.4,
            grade_version="v2",
            regraded=81.7,
            recorded=True,
            components={"hook": 70.0, "authenticity": 30.0},
            regraded_components={"hook": 70.0, "authenticity": 95.0},
        )
        line = snapshot_line(CalibrationReport(channel_id="tapin", rows=[row]))
        self.assertIn("+39.7", line)
        # ...and which component carried the change, not just that one did.
        self.assertIn("authenticity", line)


if __name__ == "__main__":
    unittest.main()
