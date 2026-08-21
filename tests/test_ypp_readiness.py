"""YPP checklist — fail-open without metrics."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.ypp_readiness import inspect_ypp, render_report


class TestYppReadiness(unittest.TestCase):
    def test_no_metrics_fail_open(self):
        report = inspect_ypp(
            "tapin",
            metrics_rows=[],
            disclosure="AI-generated",
            cadence=SimpleNamespace(total=1, cap=5),
        )
        names = {c.name: c for c in report.checks}
        self.assertTrue(names["ypp_threshold"].ok)
        self.assertTrue(names["disclosure"].ok)
        self.assertTrue(names["cadence_headroom"].ok)
        self.assertTrue(report.ok)

    def test_missing_disclosure_fails(self):
        report = inspect_ypp(
            "tapin",
            metrics_rows=[],
            disclosure="",
            cadence=SimpleNamespace(total=0, cap=5),
        )
        disc = next(c for c in report.checks if c.name == "disclosure")
        self.assertFalse(disc.ok)
        self.assertFalse(report.ok)

    def test_shorts_views_path(self):
        report = inspect_ypp(
            "tapin",
            metrics_rows=[{"views": 10_000_001, "averageViewDuration": 10}],
            disclosure="d",
            cadence=SimpleNamespace(total=0, cap=5),
        )
        thresh = next(c for c in report.checks if c.name == "ypp_threshold")
        self.assertTrue(thresh.ok)
        self.assertIn("READY", render_report(report))

    def test_cadence_at_cap_fails_headroom(self):
        report = inspect_ypp(
            "tapin",
            metrics_rows=[],
            disclosure="d",
            cadence=SimpleNamespace(total=5, cap=5),
        )
        cad = next(c for c in report.checks if c.name == "cadence_headroom")
        self.assertFalse(cad.ok)


if __name__ == "__main__":
    unittest.main()
