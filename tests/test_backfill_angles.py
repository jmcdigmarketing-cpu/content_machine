"""#836: give #819's angle correlation an n now, from what the archive already holds.

`content_runs.variants_json` stores every run's angle texts (`[text, composite]`
pairs) and `selected_topic` names the chosen one - so `angle_ranker.rank_angles`,
run deterministically (`llm_judge=False`), can score the archive offline. The
`backfill_quality` docstring said "traces never stored the five variants"; the run
rows always did. Values are approximate - the operator's brief that fed the live
seed was never persisted - so every written value is stamped `angle_backfilled`.
Dry run by default; an existing score is kept unless `--force`.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord

ANGLES = [
    ["Premier League's future hinges on how City's violations are punished.", 94.6],
    ["Fans question if City's success built on unfair financial advantages.", 94.6],
    ["City's dominance may finally face credible challenge from rivals.", 94.6],
]


def _run(run_id, variants, *, selected, quality=None, features=None):
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="Man City guilty",
        selected_topic=selected,
        status="published",
        composite_score=94.6,
        title=f"run {run_id}",
        variants_json=json.dumps(variants),
        quality_json=json.dumps(quality or {"hook_score": 80}),
        features_json=json.dumps(features or {}),
    )


class _Repo:
    def __init__(self, runs):
        self.runs = {r.id: r for r in runs}
        self.updates: dict[int, dict] = {}

    def list_for_channel(self, channel_id, *, status=None):
        return list(self.runs.values())

    def update(self, run_id, data):
        self.updates[run_id] = data
        return self.runs[run_id]


def _backfill(repo, **kwargs):
    from analytics.backfill_angles import backfill_channel

    with patch("storage.repositories.content_runs.get_content_run_repository", return_value=repo):
        return backfill_channel("tapin", **kwargs)


class TestBackfillAngles(unittest.TestCase):
    def _repo(self):
        return _Repo(
            [
                _run(1, ANGLES, selected=ANGLES[0][0]),
                _run(2, ANGLES, selected=ANGLES[1][0]),
                _run(3, [], selected="no variants"),
            ]
        )

    def test_a_dry_run_writes_nothing(self) -> None:
        repo = self._repo()
        tally = _backfill(repo)
        self.assertEqual(tally["would_update"], 2)
        self.assertEqual(repo.updates, {})

    def test_apply_writes_features_and_quality_stamped(self) -> None:
        repo = self._repo()
        tally = _backfill(repo, apply=True)
        self.assertEqual(tally["updated"], 2)
        self.assertNotIn(3, repo.updates)
        features = json.loads(repo.updates[1]["features_json"])
        quality = json.loads(repo.updates[1]["quality_json"])
        self.assertEqual(set(features["angle_scores"]), {a[0] for a in ANGLES})
        self.assertEqual(features["angle_score"], features["angle_scores"][ANGLES[0][0]])
        self.assertEqual(quality["angle_score"], features["angle_score"])
        self.assertTrue(quality["angle_backfilled"])
        self.assertEqual(quality["hook_score"], 80, "other quality keys carried forward")

    def test_the_ranker_runs_offline(self) -> None:
        repo = self._repo()
        with patch("core.angle_ranker._cheap_judge", side_effect=AssertionError("network")):
            _backfill(repo, apply=True)

    def test_an_existing_score_is_kept_unless_forced(self) -> None:
        live = _run(
            4,
            ANGLES,
            selected=ANGLES[0][0],
            quality={"angle_score": 0.9},
            features={"angle_score": 0.9},
        )
        repo = _Repo([live])
        self.assertEqual(_backfill(repo, apply=True)["updated"], 0)
        self.assertEqual(_backfill(repo, apply=True, force=True)["updated"], 1)


class TestCalibrationSaysSo(unittest.TestCase):
    def test_the_angle_line_counts_backfilled_values(self) -> None:
        from core.grade_calibration import CalibrationReport, CalibrationRow, angle_line

        rows = [
            CalibrationRow(
                run_id=i,
                title="t",
                grade=70,
                actual_percentile=50,
                engaged_rate=0.01 * i,
                angle_score=0.1 * i,
                angle_backfilled=i <= 4,
            )
            for i in range(1, 7)
        ]
        report = CalibrationReport(channel_id="tapin", rows=rows, angle_correlation=(0.9, 6))
        self.assertIn("4 of 6 backfilled", angle_line(report))


class TestOpsVerb(unittest.TestCase):
    def test_backfill_angles_is_registered(self) -> None:
        from scripts.ops import COMMANDS

        self.assertIn("backfill-angles", COMMANDS)


if __name__ == "__main__":
    unittest.main()
