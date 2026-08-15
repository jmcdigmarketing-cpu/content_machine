"""Historical repair of the missing TTS cost line.

Runs that rendered before the fix kept `cost.tts = 0.0`, so `ops economics` reported
38 rendered runs at $0.75 when the real figure was $11.77. This repairs them.

The safety properties matter more than the arithmetic: it must only touch runs that
actually rendered, must be idempotent, must never rewrite the rest of `features_json`,
and must label anything it estimated rather than measured.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from analytics import backfill_cost as bc


def _run(run_id, status, *, preview="", word_count=None, cost=None, title="T"):
    features = {}
    if word_count is not None:
        features["word_count"] = word_count
    if cost is not None:
        features["cost"] = cost
    run = MagicMock()
    run.id = run_id
    run.status = status
    run.title = title
    run.selected_topic = title
    run.script_preview = preview
    run.features_json = json.dumps(features)
    return run


def _plan(runs, **kw):
    repo = MagicMock()
    repo.list_for_channel.return_value = runs
    with (
        patch("storage.repositories.content_runs.get_content_run_repository", return_value=repo),
        patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False),
    ):
        return bc.plan_channel("tapin", **kw)


class TestTargeting(unittest.TestCase):
    def test_only_rendered_statuses(self):
        runs = [
            _run(1, "drafted", preview="x" * 1000),
            _run(2, "rendered", preview="x" * 1000),
            _run(3, "published", preview="x" * 1000),
            _run(4, "scheduled", preview="x" * 1000),
            _run(5, "failed", preview="x" * 1000),
        ]
        self.assertEqual({r["run_id"] for r in _plan(runs)}, {2, 3, 4})

    def test_skips_runs_already_repaired(self):
        runs = [_run(1, "published", preview="x" * 1000, cost={"tts": 0.25, "total": 0.3})]
        self.assertEqual(_plan(runs), [])

    def test_force_revisits_repaired_runs(self):
        runs = [_run(1, "published", preview="x" * 1000, cost={"tts": 0.25, "total": 0.3})]
        self.assertEqual(len(_plan(runs, force=True)), 1)

    def test_run_with_no_length_information_is_skipped(self):
        self.assertEqual(_plan([_run(1, "published", preview="")]), [])

    def test_idempotent_after_apply(self):
        # Second pass finds nothing, because tts is now set.
        repaired = _run(1, "published", preview="x" * 1000, cost={"tts": 0.22, "total": 0.25})
        self.assertEqual(_plan([repaired]), [])


class TestCharacterCount(unittest.TestCase):
    def test_full_preview_is_measured(self):
        chars, estimated = bc.script_chars(_run(1, "published", preview="x" * 1135), {})
        self.assertEqual(chars, 1135)
        self.assertFalse(estimated)

    def test_truncated_preview_estimates_from_word_count(self):
        # run_recorder truncates script_preview at 2000 chars, so its length is a floor.
        run = _run(1, "published", preview="x" * bc._PREVIEW_CAP)
        chars, estimated = bc.script_chars(run, {"word_count": 350})
        self.assertTrue(estimated)
        self.assertGreater(chars, bc._PREVIEW_CAP)

    def test_estimate_matches_observed_ratio(self):
        # Run 64 measured 191 words / 1135 chars.
        chars, _ = bc.script_chars(_run(1, "published", preview=""), {"word_count": 191})
        self.assertAlmostEqual(chars, 1135, delta=60)

    def test_no_preview_and_no_word_count(self):
        self.assertEqual(bc.script_chars(_run(1, "published", preview=""), {}), (0, False))


class TestPlanOutput(unittest.TestCase):
    def test_cost_increases_and_flags_are_set(self):
        rows = _plan(
            [_run(1, "published", preview="x" * 1135, cost={"llm": 0.005, "total": 0.005})]
        )
        row = rows[0]
        self.assertGreater(row["after"], row["before"])
        self.assertFalse(row["estimated"])
        self.assertFalse(row["partial"])

    def test_pre_metering_run_is_flagged_partial(self):
        # No prior cost block at all: TTS is added but llm/apify are still unknown.
        rows = _plan([_run(1, "published", preview="x" * 1135)])
        self.assertTrue(rows[0]["partial"])

    def test_session_metered_lines_are_preserved(self):
        stored = {"llm": 0.0048, "apify": 0.02, "web_search": 0.008, "tts": 0.0, "total": 0.0328}
        rows = _plan([_run(1, "published", preview="x" * 1135, cost=stored)])
        cost = rows[0]["cost"]
        self.assertEqual(cost["llm"], 0.0048)
        self.assertEqual(cost["apify"], 0.02)

    def test_local_tts_backfills_zero(self):
        repo = MagicMock()
        repo.list_for_channel.return_value = [_run(1, "published", preview="x" * 1135)]
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch.dict("os.environ", {"TTS_PROVIDER": "piper"}, clear=False),
        ):
            rows = bc.plan_channel("tapin")
        # Nothing to add — a $0 provider leaves the row untouched by design.
        self.assertTrue(all(r["cost"]["tts"] == 0.0 for r in rows))


class TestApply(unittest.TestCase):
    def _apply(self, rows, trace_ok=True):
        with (
            patch("core.run_features.merge_features") as merge,
            patch("core.run_trace.update_trace", return_value=trace_ok) as trace,
        ):
            result = bc.apply_rows(rows)
        return merge, trace, result

    def test_writes_only_the_cost_keys(self):
        rows = [
            {
                "run_id": 5,
                "cost": {"tts": 0.25, "total": 0.28},
                "estimated": False,
                "partial": False,
            }
        ]
        merge, _, _ = self._apply(rows)
        merge.assert_called_once_with(5, {"cost": {"tts": 0.25, "total": 0.28}})

    def test_estimated_rows_are_labelled(self):
        rows = [{"run_id": 5, "cost": {"tts": 0.4}, "estimated": True, "partial": False}]
        merge, _, _ = self._apply(rows)
        self.assertTrue(merge.call_args[0][1]["cost_estimated"])

    def test_partial_rows_are_labelled(self):
        rows = [{"run_id": 5, "cost": {"tts": 0.4}, "estimated": False, "partial": True}]
        merge, _, _ = self._apply(rows)
        self.assertTrue(merge.call_args[0][1]["cost_partial"])

    def test_trace_is_corrected_too(self):
        # `ops traces` reads the trace file, which carries the same "drafted" lie.
        rows = [{"run_id": 5, "cost": {"tts": 0.4}, "estimated": False, "partial": False}]
        _, trace, (applied, traces) = self._apply(rows)
        trace.assert_called_once_with(5, {"status": "rendered", "cost": {"tts": 0.4}})
        self.assertEqual((applied, traces), (1, 1))

    def test_missing_trace_file_is_not_an_error(self):
        rows = [{"run_id": 5, "cost": {"tts": 0.4}, "estimated": False, "partial": False}]
        _, _, (applied, traces) = self._apply(rows, trace_ok=False)
        self.assertEqual((applied, traces), (1, 0), "row still repaired without a trace")


if __name__ == "__main__":
    unittest.main()
