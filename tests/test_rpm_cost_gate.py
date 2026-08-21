"""RPM < cost skip-slot gate — fake economics only, no DB."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.rpm_cost_gate import (
    rpm_below_cost_reason,
    rpm_cost_gate_reason,
    trailing_rpm_and_cost,
)
from core.unit_economics import ChannelEconomics, VideoEconomics


def _vid(run_id: int, *, cost: float, revenue: float | None, views: int) -> VideoEconomics:
    return VideoEconomics(
        run_id=run_id,
        title="t",
        cost_usd=cost,
        revenue_usd=revenue,
        views=views,
    )


class TestRpmCostGate(unittest.TestCase):
    def test_default_off(self):
        with patch.dict(os.environ, {"RPM_COST_GATE": ""}, clear=False):
            self.assertIsNone(rpm_below_cost_reason(rpm=0.01, cost_per_video=0.31))

    def test_no_revenue_fails_open(self):
        env = {"RPM_COST_GATE": "true"}
        econ = ChannelEconomics(
            channel_id="tapin",
            videos=[_vid(1, cost=0.31, revenue=None, views=1000)],
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(rpm_cost_gate_reason("tapin", econ=econ))

    def test_rpm_below_cost_blocks(self):
        # $0.10 revenue / 1000 views = $0.10 RPM vs $0.31 cost.
        env = {"RPM_COST_GATE": "true"}
        econ = ChannelEconomics(
            channel_id="tapin",
            videos=[_vid(1, cost=0.31, revenue=0.10, views=1000)],
        )
        with patch.dict(os.environ, env, clear=False):
            reason = rpm_cost_gate_reason("tapin", econ=econ)
        self.assertIsNotNone(reason)
        self.assertIn("RPM", reason or "")

    def test_rpm_above_cost_passes(self):
        env = {"RPM_COST_GATE": "on"}
        econ = ChannelEconomics(
            channel_id="tapin",
            videos=[_vid(1, cost=0.31, revenue=2.00, views=1000)],
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(rpm_cost_gate_reason("tapin", econ=econ))

    def test_trailing_mixes_recent_monetized_only(self):
        videos = [
            _vid(3, cost=0.31, revenue=None, views=10),
            _vid(2, cost=0.31, revenue=1.0, views=1000),
            _vid(1, cost=0.31, revenue=1.0, views=1000),
        ]
        rpm, cost = trailing_rpm_and_cost(videos, limit=7)
        self.assertAlmostEqual(rpm or 0.0, 1.0)
        self.assertAlmostEqual(cost, 0.31)


if __name__ == "__main__":
    unittest.main()
