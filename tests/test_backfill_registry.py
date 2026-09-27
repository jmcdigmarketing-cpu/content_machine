"""#870: one `ops backfill` over a registry of derived fields.

Four verbs each had their own stale rule and their own default: `backfill-features` and
`backfill-cost` wrote unless told not to, `backfill-quality` and `backfill-angles` only
wrote with `--apply`. A rubric change could leave history half re-stamped. The registry
names each backfill, its version and its stale rule; `ops backfill` is a dry run unless
`--apply`, and recomputes only the stale rows.
"""

from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _run(rid, *, features=None, quality=None, status="drafted", script="A script.", variants=None):
    return SimpleNamespace(
        id=rid,
        status=status,
        script_preview=script,
        features_json=json.dumps(features or {}),
        quality_json=json.dumps(quality or {}),
        variants_json=json.dumps(variants or []),
        selected_topic="Angle A",
        input_topic="Topic",
        composite_score=50.0,
        title="T",
        word_count=100,
        timings_json="{}",
    )


def _current_quality():
    from core.run_quality import QUALITY_VERSION
    from core.video_grade import GRADE_VERSION

    return {"quality_version": QUALITY_VERSION, "grade_version": GRADE_VERSION, "grade_score": 70}


class StaleRuleTests(unittest.TestCase):
    def test_quality_behind_a_version_is_stale_and_current_is_not(self):
        from analytics.backfills import get_backfill

        quality = get_backfill("quality")
        self.assertTrue(
            quality.stale(_run(1, quality={"quality_version": "v1", "grade_score": 50}))
        )
        self.assertTrue(quality.stale(_run(2, quality={})))
        self.assertFalse(quality.stale(_run(3, quality=_current_quality())))
        self.assertFalse(
            quality.stale(_run(4, quality={}, script="")), "no script, nothing to grade"
        )

    def test_features_are_stale_only_when_missing(self):
        from analytics.backfills import get_backfill

        features = get_backfill("features")
        self.assertTrue(features.stale(_run(1)))
        self.assertFalse(
            features.stale(_run(2, features={"feature_version": "v1", "domain": "gaming"}))
        )

    def test_cost_is_stale_on_a_rendered_run_without_tts(self):
        from analytics.backfills import get_backfill

        cost = get_backfill("cost")
        self.assertTrue(cost.stale(_run(1, status="published", features={"cost": {"llm": 0.01}})))
        self.assertFalse(cost.stale(_run(2, status="drafted", features={})))
        self.assertFalse(cost.stale(_run(3, status="published", features={"cost": {"tts": 0.2}})))

    def test_angles_are_stale_without_a_score(self):
        from analytics.backfills import get_backfill

        angles = get_backfill("angles")
        self.assertTrue(angles.stale(_run(1, variants=["Angle A", "Angle B"])))
        self.assertFalse(
            angles.stale(_run(2, variants=["Angle A"])), "one variant cannot be ranked"
        )
        self.assertFalse(
            angles.stale(_run(3, variants=["Angle A", "Angle B"], quality={"angle_score": 0.4}))
        )


class RegistryRunTests(unittest.TestCase):
    def _repo(self, runs):
        repo = MagicMock()
        repo.list_for_channel.return_value = runs
        return repo

    def test_the_status_counts_stale_rows_per_backfill(self):
        from analytics.backfills import stale_counts

        runs = [_run(1, quality={}), _run(2, quality=_current_quality(), features={"domain": "g"})]
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=self._repo(runs),
        ):
            counts = stale_counts("tapin")
        self.assertEqual(counts["quality"], (1, 2))
        self.assertEqual(counts["features"], (1, 2))

    def test_a_dry_run_writes_nothing(self):
        from analytics.backfills import run_backfills

        repo = self._repo([_run(1, quality={"quality_version": "v1", "grade_score": 5})])
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.run_quality.build_quality", return_value={"grade_score": 60}),
            patch("core.run_quality.snapshot_grade", return_value={}),
        ):
            tallies = run_backfills("tapin", ["quality"], apply=False)
        repo.update.assert_not_called()
        self.assertEqual(tallies["quality"]["would_update"], 1)

    def test_only_the_stale_quality_rows_are_recomputed(self):
        from analytics.backfills import run_backfills

        repo = self._repo(
            [
                _run(1, quality={"quality_version": "v1", "grade_score": 5}),
                _run(2, quality=_current_quality()),
            ]
        )
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.run_quality.build_quality", return_value={"grade_score": 60}) as build,
            patch("core.run_quality.snapshot_grade", return_value={}),
        ):
            run_backfills("tapin", ["quality"], apply=True)
        self.assertEqual(build.call_count, 1)
        self.assertEqual(repo.update.call_args.args[0], 1)

    def test_all_runs_in_dependency_order(self):
        from analytics import backfills

        order = []
        fakes = [
            backfills.Backfill(
                b.name, b.fills, b.version, b.stale, lambda c, a, f, n=b.name: order.append(n) or {}
            )
            for b in backfills.REGISTRY
        ]
        with patch.object(backfills, "REGISTRY", tuple(fakes)):
            backfills.run_backfills("tapin", ["all"], apply=True)
        self.assertEqual(order, ["features", "cost", "quality", "angles"])


class VerbTests(unittest.TestCase):
    def test_ops_backfill_without_a_name_prints_the_status(self):
        from scripts.ops import cmd_backfill

        out = io.StringIO()
        with (
            patch(
                "analytics.backfills.stale_counts",
                return_value={"quality": (12, 96), "features": (0, 96)},
            ),
            redirect_stdout(out),
        ):
            cmd_backfill(argparse.Namespace(channel="tapin", target="", apply=False, force=False))
        self.assertIn("quality", out.getvalue())
        self.assertIn("12 of 96", out.getvalue())
        self.assertIn("--apply", out.getvalue())

    def test_an_old_verb_still_runs_and_points_at_the_new_one(self):
        from scripts.ops import cmd_backfill_quality

        out = io.StringIO()
        with patch("scripts.ops._run_module", return_value=0) as run, redirect_stdout(out):
            cmd_backfill_quality(argparse.Namespace(channel="tapin", apply=False, force=False))
        run.assert_called_once()
        self.assertIn("ops backfill quality", out.getvalue())


if __name__ == "__main__":
    unittest.main()
