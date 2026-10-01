"""#579: say when a video costs more than the channel's RPM will return for it.

The opt-in `RPM_COST_GATE` defers a scheduled upload when trailing RPM is under the
cost per video, but nothing told the operator at the moment of choice - the Proceed?
prompt showed the projected cost and no return to set it against. The expected return
is the channel's trailing RPM (`rpm_cost_gate.trailing_rpm_and_cost`) times its median
views per video; the pipeline stores it beside `projected_cost` and the report prints
it, with a "!" when the cost is higher. A channel with no revenue data prints nothing.
`ops economics` adds how many videos cost more than they returned.
"""

from __future__ import annotations

import unittest

from core.unit_economics import ChannelEconomics, VideoEconomics


def _video(run_id, *, cost, revenue, views):
    return VideoEconomics(
        run_id=run_id,
        title=f"t{run_id}",
        domain="ufc",
        cost_usd=cost,
        revenue_usd=revenue,
        views=views,
    )


VIDEOS = [
    _video(1, cost=0.30, revenue=0.20, views=1000),  # RPM $0.20
    _video(2, cost=0.30, revenue=0.10, views=500),
    _video(3, cost=0.30, revenue=0.60, views=3000),
]


class ExpectedReturnTests(unittest.TestCase):
    def test_return_is_rpm_times_median_views(self):
        from core.rpm_cost_gate import expected_return

        got = expected_return(VIDEOS)
        # trailing RPM = 0.90 / 4500 * 1000 = $0.20; median views 1000 -> $0.20
        self.assertAlmostEqual(got["rpm"], 0.20)
        self.assertEqual(got["median_views"], 1000)
        self.assertAlmostEqual(got["usd"], 0.20)

    def test_no_revenue_means_no_estimate(self):
        from core.rpm_cost_gate import expected_return

        self.assertIsNone(expected_return([_video(1, cost=0.3, revenue=None, views=900)]))


class ReportTests(unittest.TestCase):
    def _report(self, features):
        from core.ui import display_fact_engine_report

        lines: list[str] = []
        display_fact_engine_report(features, print_fn=lines.append)
        return "\n".join(lines)

    def test_a_cost_above_the_return_is_flagged(self):
        text = self._report(
            {
                "projected_cost": {"total": 0.36, "tts": 0.28, "llm": 0.01},
                "expected_return": {"usd": 0.20, "rpm": 0.20, "median_views": 1000},
            }
        )
        self.assertIn("! this video would return ~$0.20", text)
        self.assertIn("less than its $0.36 cost", text)

    def test_a_return_above_the_cost_is_one_quiet_line(self):
        text = self._report(
            {
                "projected_cost": {"total": 0.36, "tts": 0.28},
                "expected_return": {"usd": 1.10, "rpm": 1.10, "median_views": 1000},
            }
        )
        self.assertIn("expected return ~$1.10", text)
        self.assertNotIn("! this video", text)

    def test_without_revenue_nothing_is_said(self):
        text = self._report({"projected_cost": {"total": 0.36, "tts": 0.28}})
        self.assertNotIn("return", text)


class EconomicsTests(unittest.TestCase):
    def test_the_summary_counts_the_losers(self):
        from core.unit_economics import summary_lines

        econ = ChannelEconomics(channel_id="tapin", videos=VIDEOS)
        self.assertIn(
            "2 of 3 video(s) with revenue cost more than they returned",
            "\n".join(summary_lines(econ)),
        )


if __name__ == "__main__":
    unittest.main()
