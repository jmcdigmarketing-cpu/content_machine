"""Paid-signal attribution + catalog recommend — fixture traces, no catalog write."""

from __future__ import annotations

import unittest

from core.paid_signal_attribution import (
    MIN_SAMPLES,
    attribute_paid_signals,
    recommend_catalog_action,
    render_report,
)


def _trace(run_id: int, *, tiktok: bool, engaged: float | None, composite: float) -> dict:
    return {
        "run_id": run_id,
        "engaged_rate": engaged,
        "composite_score": composite,
        "signals": {
            "tiktok_trends": {
                "active": tiktok,
                "status": "ok" if tiktok else "inactive",
                "score": 80 if tiktok else 0,
            },
            "youtube_competitors": {"active": False, "status": "inactive", "score": 0},
        },
    }


class TestPaidSignalAttribution(unittest.TestCase):
    def test_insufficient_sample_waits(self):
        traces = [
            _trace(1, tiktok=True, engaged=0.12, composite=70),
            _trace(2, tiktok=False, engaged=0.10, composite=65),
        ]
        lifts = attribute_paid_signals(traces)
        tiktok = next(x for x in lifts if x.name == "tiktok_trends")
        self.assertEqual(recommend_catalog_action(tiktok), "wait")
        blob = render_report(lifts)
        self.assertIn("does not change apify_sources.json", blob.lower())

    def test_negative_lift_recommends_disable(self):
        on = [_trace(i, tiktok=True, engaged=0.05, composite=40) for i in range(MIN_SAMPLES)]
        off = [
            _trace(100 + i, tiktok=False, engaged=0.12, composite=70) for i in range(MIN_SAMPLES)
        ]
        lifts = attribute_paid_signals(on + off)
        tiktok = next(x for x in lifts if x.name == "tiktok_trends")
        self.assertEqual(recommend_catalog_action(tiktok), "disable")
        self.assertIn("enabled: false", render_report(lifts))

    def test_positive_lift_keeps(self):
        on = [_trace(i, tiktok=True, engaged=0.20, composite=80) for i in range(MIN_SAMPLES)]
        off = [
            _trace(100 + i, tiktok=False, engaged=0.10, composite=50) for i in range(MIN_SAMPLES)
        ]
        tiktok = next(x for x in attribute_paid_signals(on + off) if x.name == "tiktok_trends")
        self.assertEqual(recommend_catalog_action(tiktok), "keep")

    def test_composite_fallback_when_no_engaged_rate(self):
        traces = [_trace(1, tiktok=True, engaged=None, composite=90)]
        lifts = attribute_paid_signals(traces)
        tiktok = next(x for x in lifts if x.name == "tiktok_trends")
        self.assertEqual(tiktok.metric, "composite_score")
        self.assertEqual(tiktok.with_signal.n, 1)

    def test_ops_command_registered(self):
        from scripts import ops

        self.assertIn("paid-signals", ops.COMMANDS)


if __name__ == "__main__":
    unittest.main()
