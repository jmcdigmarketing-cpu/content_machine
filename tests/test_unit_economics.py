"""Allocated vs marginal unit economics — isolated numbers, no DB."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core import unit_economics as ue
from core.unit_economics import ChannelEconomics, VideoEconomics


class TestAllocatedVsMarginal(unittest.TestCase):
    def test_allocated_is_plan_divided_by_videos(self):
        env = {"COST_TTS_PLAN_USD": "22", "COST_TTS_PLAN_CHARS": "100000"}
        with patch.dict(os.environ, env):
            self.assertAlmostEqual(ue.allocated_per_video(21), 22 / 21, places=4)
            self.assertAlmostEqual(ue.allocated_per_video(1), 22.0, places=4)
            self.assertEqual(ue.allocated_per_video(0), 0.0)

    def test_capacity_at_typical_script_length(self):
        with patch.dict(os.environ, {"COST_TTS_PLAN_CHARS": "100000"}):
            self.assertEqual(ue.plan_capacity_videos(chars_per_video=1100), 90)

    def test_summary_lines_surface_both(self):
        econ = ChannelEconomics(
            channel_id="tapin",
            videos=[
                VideoEconomics(run_id=1, title="a", cost_usd=0.31, revenue_usd=None),
                VideoEconomics(run_id=2, title="b", cost_usd=0.31, revenue_usd=None),
            ],
        )
        env = {"COST_TTS_PLAN_USD": "22", "COST_TTS_PLAN_CHARS": "100000"}
        with patch.dict(os.environ, env):
            lines = ue.summary_lines(econ)
        blob = "\n".join(lines)
        self.assertIn("marginal", blob)
        self.assertIn("allocated", blob)
        self.assertIn("$11.00/video", blob)  # 22 / 2
        self.assertIn("$0.31/video", blob)

    def test_domain_rpm_lines(self):
        econ = ChannelEconomics(
            channel_id="tapin",
            videos=[
                VideoEconomics(
                    run_id=1,
                    title="ufc",
                    cost_usd=0.30,
                    revenue_usd=1.20,
                    views=1000,
                    domain="ufc",
                ),
                VideoEconomics(
                    run_id=2,
                    title="gta",
                    cost_usd=0.30,
                    revenue_usd=0.10,
                    views=500,
                    domain="gaming",
                ),
            ],
        )
        blob = "\n".join(ue.summary_lines(econ))
        self.assertIn("RPM x cost by domain", blob)
        self.assertIn("ufc", blob)
        self.assertIn("gaming", blob)

    def test_env_override_plan_usd(self):
        with patch.dict(os.environ, {"COST_TTS_PLAN_USD": "99"}):
            self.assertAlmostEqual(ue.allocated_per_video(9), 11.0, places=4)


if __name__ == "__main__":
    unittest.main()
