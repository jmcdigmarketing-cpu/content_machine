"""#826: say what the claim taxonomy covers, so coverage is not mistaken for accuracy.

#345's per-claim types exist from run 76 on; the 27 verified runs before it persist a
flat `unsupported` list with no types. 76 of 84 unsupported claims in the archive cannot
be told apart by bar, and #822's question is unanswerable for three quarters of the
record. Not backfillable (#823 does not re-run the verifier). The fix is a line wherever
the taxonomy is reported.

A run is "typed" when any of its claims carries a type - NOT when the row has an
`unsupported_types` key: `relational_check.merge_reversals` pads that key with "" to
keep lengths aligned, so its presence proves nothing.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord


def _run(run_id: int, verification: dict | None) -> ContentRunRecord:
    features = {"claim_verification": verification} if verification is not None else {}
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="t",
        selected_topic="t",
        status="published",
        composite_score=60.0,
        title=f"run {run_id}",
        features_json=json.dumps(features),
    )


_TYPED = {
    "unsupported": ["x"],
    "unsupported_types": ["rumor"],
    "claims": [{"claim": "x", "supported": False, "type": "rumor"}],
}
_FLAT = {"unsupported": ["x", "y"]}
_PADDED = {
    "unsupported": ["x"],
    "unsupported_types": [""],
    "claims": [{"claim": "x", "supported": False}],
}


class TestClaimTypeCoverage(unittest.TestCase):
    def test_counts_typed_runs_over_verified_runs(self) -> None:
        from core.claim_types import claim_type_coverage

        runs = [_run(1, _TYPED), _run(2, _TYPED), _run(3, _TYPED)] + [
            _run(i, _FLAT) for i in range(4, 9)
        ]
        self.assertEqual(claim_type_coverage(runs), (3, 8))

    def test_a_padded_types_key_is_not_typed(self) -> None:
        from core.claim_types import claim_type_coverage

        self.assertEqual(claim_type_coverage([_run(1, _PADDED)]), (0, 1))

    def test_runs_with_no_verification_are_not_verified(self) -> None:
        from core.claim_types import claim_type_coverage

        self.assertEqual(claim_type_coverage([_run(1, None), _run(2, _TYPED)]), (1, 1))

    def test_the_line_names_both_numbers_and_the_reason(self) -> None:
        from core.claim_types import claim_type_coverage_line

        line = claim_type_coverage_line((3, 8))
        self.assertIn("3 of 8", line)
        self.assertIn("cannot be backfilled", line)
        self.assertEqual(claim_type_coverage_line((0, 0)), "")


class TestReported(unittest.TestCase):
    def test_calibration_render_carries_the_coverage_line(self) -> None:
        from core.grade_calibration import render

        runs = [_run(1, _TYPED), _run(2, _FLAT)]

        class _Repo:
            def list_for_channel(self, channel_id, *, status=None):
                return runs

            def get(self, run_id):
                return None

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=_Repo(),
            ),
            patch("core.engagement_predictor.run_engagement_map", return_value={}),
            patch("config.channels.resolve_channel_id", return_value="tapin"),
            patch("core.grade_calibration._thumbnail_scores", return_value={}),
        ):
            text = render("tapin")
        self.assertIn("1 of 2 verified runs carry per-claim types", text)

    def test_weekly_report_passes_a_real_runs_total(self) -> None:
        # Found on the way: weekly_report passed runs_total=len(report.get("rows")) and
        # build_report never sets "rows", so the "N runs" part of #818's line never printed.
        import inspect

        from analytics import weekly_report

        source = inspect.getsource(weekly_report.format_report)
        self.assertNotIn('report.get("rows")', source)


if __name__ == "__main__":
    unittest.main()
