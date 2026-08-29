"""#433 cross-channel duplicate guard — same lens, not same topic.

Calls real infer_domain. Fixture runs via a fake repository. Never mocks the scorer.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

REVIEW = "GTA 6 leak review"
STOCK = "Take-Two stock after GTA 6 leak"
# The operator's own words for the case that MUST be allowed:
# "MoneyWise could do a video talking of the economic impact of gta 6 hitting
#  the market but reviews or commentary should stop there."
ECONOMIC = "GTA 6 economic impact on the games market"


def _row(channel_id: str, topic: str, *, rid: int = 1, status: str = "drafted"):
    return SimpleNamespace(
        id=rid,
        channel_id=channel_id,
        input_topic=topic,
        selected_topic=topic,
        status=status,
        title=topic,
    )


class _Repo:
    def __init__(self, rows: list):
        self.rows = rows

    def list_for_channel(self, channel_id: str, *, status: str | None = None):
        out = [r for r in self.rows if r.channel_id == channel_id]
        if status:
            out = [r for r in out if r.status == status]
        return out


def _repo_patch(rows: list):
    return patch(
        "storage.repositories.content_runs.get_content_run_repository",
        return_value=_Repo(rows),
    )


class TestCrossChannelLens(unittest.TestCase):
    def test_same_gta_review_on_two_channels_blocks(self):
        from core.cross_channel_dup import cross_channel_lens_collision

        rows = [_row("tapin", REVIEW, rid=71)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "block"}, clear=False),
            _repo_patch(rows),
        ):
            hit = cross_channel_lens_collision(REVIEW, "moneywise")
        self.assertIsNotNone(hit)
        self.assertIn("lens", hit.lower())
        self.assertIn("gaming", hit.lower())
        self.assertIn("tapin", hit)

    def test_gta_review_vs_take_two_stock_is_allowed(self):
        from core.cross_channel_dup import cross_channel_lens_collision

        rows = [_row("tapin", REVIEW, rid=71)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "block"}, clear=False),
            _repo_patch(rows),
        ):
            hit = cross_channel_lens_collision(STOCK, "moneywise")
        self.assertIsNone(hit)

    def test_economic_impact_angle_is_allowed_beside_a_gaming_take(self):
        """The operator's canonical ALLOWED case. `infer_domain` reads this as
        `gaming` (the franchise words outweigh the treatment), so keying the lens
        on infer_domain alone refuses the one MoneyWise angle that was explicitly
        permitted -- and CROSS_CHANNEL_DUP defaults to block."""
        from core.cross_channel_dup import cross_channel_lens_collision

        rows = [_row("tapin", REVIEW, rid=71)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "block"}, clear=False),
            _repo_patch(rows),
        ):
            hit = cross_channel_lens_collision(ECONOMIC, "moneywise")
        self.assertIsNone(hit, hit)

    def test_review_commentary_is_still_blocked(self):
        """...and the boundary the operator drew right after it still holds."""
        from core.cross_channel_dup import cross_channel_lens_collision

        rows = [_row("tapin", REVIEW, rid=71)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "block"}, clear=False),
            _repo_patch(rows),
        ):
            hit = cross_channel_lens_collision("GTA 6 review: is it worth it", "moneywise")
        self.assertIsNotNone(hit)

    def test_same_channel_is_not_this_guard(self):
        from core.cross_channel_dup import cross_channel_lens_collision

        rows = [_row("tapin", REVIEW, rid=71), _row("tapin", REVIEW, rid=72)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "block"}, clear=False),
            _repo_patch(rows),
        ):
            hit = cross_channel_lens_collision(REVIEW, "tapin")
        self.assertIsNone(hit)

    def test_off_returns_none(self):
        from core.cross_channel_dup import cross_channel_lens_collision

        rows = [_row("tapin", REVIEW, rid=71)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "off"}, clear=False),
            _repo_patch(rows),
        ):
            self.assertIsNone(cross_channel_lens_collision(REVIEW, "moneywise"))

    def test_publish_blockers_surface_the_collision(self):
        from core.publish_blockers import blocking_publish_reasons

        rows = [_row("tapin", REVIEW, rid=71)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "block"}, clear=False),
            _repo_patch(rows),
        ):
            reasons = blocking_publish_reasons(
                channel_id="moneywise",
                features={"selected_topic": REVIEW},
            )
        blob = " ".join(reasons).lower()
        self.assertIn("lens", blob)
        self.assertIn("tapin", blob)


class TestPipelineStopsBeforeScript(unittest.TestCase):
    @patch("core.pipeline.write_run_dossier")
    @patch("core.pipeline.write_run_trace")
    @patch("core.pipeline.persist_quality")
    @patch("core.pipeline.build_quality", return_value={})
    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=88)
    @patch("core.pipeline.generate_content_package")
    @patch("core.pipeline.build_research_brief")
    def test_same_lens_aborts_before_the_script(
        self, mock_brief, mock_content, _record, _learn, _bq, _pq, _tr, _doss
    ):
        from core.pipeline import DiscoveryResult, run_pipeline

        discovery = DiscoveryResult(
            input_topic=REVIEW,
            base_signals={},
            evaluated=[(REVIEW, 70.0, {})],
            channel_id="moneywise",
        )
        rows = [_row("tapin", REVIEW, rid=71)]
        with (
            patch.dict(os.environ, {"CROSS_CHANNEL_DUP": "block"}, clear=False),
            _repo_patch(rows),
        ):
            result = run_pipeline(
                REVIEW,
                discovery=discovery,
                proceed_video=False,
                channel_id="moneywise",
            )
        self.assertTrue(result.aborted)
        self.assertIn("lens", (result.abort_reason or "").lower())
        mock_brief.assert_not_called()
        mock_content.assert_not_called()
