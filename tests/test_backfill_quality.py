"""#823: three waves of measurements, zero rows carrying them.

Measured on `tapin` (2026-09-20, 87 runs): `angle_spread` 0 rows,
`hedge_density` 0, `grade_score` 0, `style_recurrence_*` 0. Every one shipped
in wave 26-29 and none has a single data point, because no run has been
generated since. `script_preview` is on all 87 rows, so the script-derived
fields are recomputable offline.

Three constraints, each from something already recorded:

- **As-of window.** `build_quality` -> `evaluate_authenticity` compares against
  the 12 most recent runs *as of now*. Backfilling run 12 against runs that did
  not exist when it was written would poison the archive #808 exists to
  protect. `evaluate_authenticity` already takes `recent=` (added for #630).
- **Carry forward what the rebuilder does not own.** `analytics/backfill_features.py`
  records this hazard exactly: a `--force` rebuild destroyed the cost ledger
  until it copied unknown keys across. Here it is `thumbnail_overall` and the
  claim-verifier keys.
- **Dry run by default.** It writes to the operator's real archive.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord


class _FakeRepo:
    def __init__(self, records):
        self.records = {r.id: r for r in records}
        self.writes: list[int] = []

    def list_for_channel(self, channel_id, *, status=None):
        return [r for r in self.records.values() if r.channel_id == channel_id]

    def get(self, run_id):
        return self.records.get(run_id)

    def update(self, run_id, data):
        self.writes.append(run_id)
        self.records[run_id] = replace(self.records[run_id], **data)
        return self.records[run_id]


def _record(run_id: int, *, script: str, quality: dict | None = None):
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="t",
        selected_topic="t",
        status="published",
        composite_score=60.0 + run_id,
        title=f"run {run_id}",
        script_preview=script,
        quality_json=json.dumps(quality or {}),
    )


_RECORDS = [
    _record(1, script="Rockstar delayed the game. I think the studio is buying time here."),
    _record(2, script="The patch broke matchmaking. My take is that support knew for weeks."),
    _record(
        3,
        script="Reportedly the studio may delay again. Here's why that could matter a lot.",
        quality={"thumbnail_overall": 61.0, "thumbnail_source": "llm"},
    ),
]


class TestDryRunByDefault(unittest.TestCase):
    def test_a_dry_run_writes_nothing(self) -> None:
        from analytics.backfill_quality import backfill_channel

        repo = _FakeRepo(_RECORDS)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            result = backfill_channel("tapin", apply=False)

        self.assertEqual(repo.writes, [])
        self.assertEqual(result["would_update"], 3)
        self.assertEqual(result["updated"], 0)


class TestItPopulatesTheMissingFields(unittest.TestCase):
    def test_apply_writes_the_fields_three_waves_added(self) -> None:
        from analytics.backfill_quality import backfill_channel

        repo = _FakeRepo(_RECORDS)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            backfill_channel("tapin", apply=True)

        row = json.loads(repo.records[3].quality_json)
        self.assertIn("grade_score", row)
        self.assertIn("hedge_density", row)
        self.assertIn("hook_score", row)
        self.assertGreater(row["hedge_density"], 0)  # "reportedly", "may", "could"

    def test_it_does_not_destroy_what_it_does_not_own(self) -> None:
        """backfill_features' recorded hazard: --force ate the cost ledger."""
        from analytics.backfill_quality import backfill_channel

        repo = _FakeRepo(_RECORDS)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            backfill_channel("tapin", apply=True)

        row = json.loads(repo.records[3].quality_json)
        self.assertEqual(row["thumbnail_overall"], 61.0)
        self.assertEqual(row["thumbnail_source"], "llm")


class TestTheAsOfWindow(unittest.TestCase):
    def test_a_run_is_never_compared_against_its_own_future(self) -> None:
        seen: dict[int, list[str]] = {}
        real = None

        def _spy(script, channel_id, *, fact_count=0, exclude_run_id=None, recent=None):
            seen[len(seen) + 1] = list(recent or [])
            return real(
                script,
                channel_id,
                fact_count=fact_count,
                exclude_run_id=exclude_run_id,
                recent=recent,
            )

        from core import authenticity as auth_mod

        real = auth_mod.evaluate_authenticity

        from analytics.backfill_quality import backfill_channel

        repo = _FakeRepo(_RECORDS)
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.authenticity.evaluate_authenticity", side_effect=_spy),
        ):
            backfill_channel("tapin", apply=True)

        # Run 1 has no history; run 3 sees runs 1 and 2 and never its own text.
        windows = list(seen.values())
        self.assertEqual(windows[0], [])
        self.assertEqual(len(windows[2]), 2)
        self.assertNotIn(_RECORDS[2].script_preview, windows[2])

    def test_the_window_never_contains_a_later_run(self) -> None:
        from analytics.backfill_quality import _as_of_window

        rows = sorted(_RECORDS, key=lambda r: r.id)
        self.assertEqual(_as_of_window(rows, 1), [])
        self.assertEqual(_as_of_window(rows, 3), [rows[1].script_preview, rows[0].script_preview])


if __name__ == "__main__":
    unittest.main()


class TestABackfilledGradeSaysSo(unittest.TestCase):
    """A recomputed grade must not be read as evidence the rubric held.

    #808's point is that a recorded grade is the number *that run's rubric*
    produced, so `snapshot_line` can report drift against today's code. A
    backfilled grade was computed by today's code by definition, so counting it
    as "today's rubric reproduces this one" is a claim that cannot fail - found
    immediately after applying the backfill, when the line read
    "Recorded grades: 12/12 - today's rubric reproduces every one".
    """

    def test_the_backfill_stamps_what_it_computed(self) -> None:
        from analytics.backfill_quality import backfill_channel

        repo = _FakeRepo(_RECORDS)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            backfill_channel("tapin", apply=True)

        self.assertTrue(json.loads(repo.records[1].quality_json)["grade_backfilled"])

    def test_calibration_does_not_claim_a_backfilled_row_reproduced(self) -> None:
        from core.grade_calibration import CalibrationReport, CalibrationRow, snapshot_line

        row = CalibrationRow(
            run_id=1,
            title="t",
            grade=70.0,
            actual_percentile=50.0,
            engaged_rate=0.3,
            regraded=70.0,
            recorded=True,
            backfilled=True,
        )
        line = snapshot_line(CalibrationReport(channel_id="tapin", rows=[row]))
        self.assertIn("backfilled", line.lower())
        self.assertNotIn("reproduces every one", line)
