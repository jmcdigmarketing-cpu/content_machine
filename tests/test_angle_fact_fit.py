"""#849: fact-fit - a per-angle number, measured before anything leans on it.

Signals are fetched once per topic, so every angle got the same composite (run 98's
five-way 94.61 tie) and the editorial score decided. The operator's calibration put that
score at r=-0.26 (n=22, not significant). Fact-fit asks something the angle text alone
cannot answer: how much of the fact pool the pipeline already holds supports this angle.
Words every angle shares with the seed cannot separate them, so they do not count.

This wave measures it and stores it; selection is unchanged until it has an n.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

FACTS = [
    "Rockstar confirms GTA 6 delay to May 2026",
    "GTA 6 online economy leak shows shark card prices",
    "Take-Two stock falls after the GTA 6 delay",
]
ANGLES = [
    "GTA 6 delay: what it means for launch",
    "GTA 6 online economy and shark cards",
    "GTA 6 map size rumours",
]


class FactFitTests(unittest.TestCase):
    def test_angles_over_one_fact_pool_score_differently(self):
        from core.angle_fact_fit import fact_fit

        scores = fact_fit(ANGLES, FACTS, seed_topic="GTA 6")
        self.assertAlmostEqual(scores[ANGLES[0]], 2 / 3, places=3)
        self.assertAlmostEqual(scores[ANGLES[1]], 1 / 3, places=3)
        self.assertEqual(scores[ANGLES[2]], 0.0)

    def test_the_seed_words_do_not_count(self):
        from core.angle_fact_fit import fact_fit

        scores = fact_fit(["GTA 6"], FACTS, seed_topic="GTA 6")
        self.assertEqual(scores["GTA 6"], 0.0, "every fact names GTA 6; that separates nothing")

    def test_no_facts_is_zero_not_an_error(self):
        from core.angle_fact_fit import fact_fit

        self.assertEqual(fact_fit(ANGLES, [], seed_topic="GTA 6"), dict.fromkeys(ANGLES, 0.0))

    def test_fact_lines_come_from_the_signal_block(self):
        from core.angle_fact_fit import fact_lines

        text = "News headlines:\n- Rockstar confirms delay (wire)\n- Leak shows cards (x)\n"
        self.assertEqual(
            fact_lines(text), ["Rockstar confirms delay (wire)", "Leak shows cards (x)"]
        )


class PersistenceTests(unittest.TestCase):
    def test_discovery_cache_round_trips_it(self):
        from core.pipeline import DiscoveryResult, _discovery_from_payload

        result = DiscoveryResult(
            input_topic="GTA 6",
            base_signals={},
            evaluated=[(ANGLES[0], 90.0, {})],
            angle_fact_fit={ANGLES[0]: 0.5},
        )
        payload = {
            "input_topic": result.input_topic,
            "evaluated": result.evaluated,
            "angle_fact_fit": result.angle_fact_fit,
        }
        self.assertEqual(_discovery_from_payload(payload).angle_fact_fit, {ANGLES[0]: 0.5})

    def test_quality_carries_the_chosen_value(self):
        from core.run_quality import build_quality

        with patch("core.run_quality.logger"):
            quality = build_quality(
                script="A short script about the GTA 6 delay and what it means.",
                channel_id="tapin",
                features={"fact_fit": 0.4},
                composite_score=50.0,
                recent=[],
            )
        self.assertEqual(quality.get("fact_fit"), 0.4)

    def test_calibration_reports_it_once_it_has_n(self):
        from core.grade_calibration import (
            MIN_MEASURED,
            CalibrationReport,
            CalibrationRow,
            fact_fit_line,
        )

        report = CalibrationReport(channel_id="tapin")
        report.rows = [
            CalibrationRow(
                run_id=i,
                title="t",
                grade=50.0,
                actual_percentile=50.0,
                engaged_rate=0.01 * i,
                fact_fit=0.1 * i,
            )
            for i in range(1, MIN_MEASURED + 1)
        ]
        from core.grade_calibration import _pearson

        pairs = [(r.fact_fit, r.engaged_rate) for r in report.rows]
        report.fact_fit_correlation = (_pearson(*map(list, zip(*pairs, strict=True))), len(pairs))
        self.assertIn("Fact-fit vs engaged-rate r=+1.00", fact_fit_line(report))

    def test_calibration_says_collecting_without_n(self):
        from core.grade_calibration import CalibrationReport, fact_fit_line

        report = CalibrationReport(channel_id="tapin")
        self.assertIn("collecting", fact_fit_line(report))

    def test_build_calibration_reads_fact_fit_from_quality(self):
        from core import grade_calibration as gc

        runs = [
            SimpleNamespace(
                id=i,
                title="t",
                selected_topic="t",
                composite_score=50.0,
                quality_json=json.dumps(
                    {"grade_score": 50, "grade_version": "v5", "fact_fit": 0.1 * i}
                ),
                youtube_video_id=f"v{i}",
            )
            for i in range(1, gc.MIN_MEASURED + 2)
        ]
        engagement = {i: 0.01 * i for i in range(1, gc.MIN_MEASURED + 2)}
        repo = SimpleNamespace(list_for_channel=lambda cid: runs)
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.engagement_predictor.run_engagement_map", return_value=engagement),
            patch.object(gc, "_thumbnail_scores", return_value={}),
        ):
            report = gc.build_calibration("tapin")
        r, n = report.fact_fit_correlation
        self.assertEqual(n, gc.MIN_MEASURED + 1)
        self.assertGreater(r, 0.9)


class DossierTests(unittest.TestCase):
    def test_the_audit_block_ranks_the_angles_by_fact_fit(self):
        from core.vault_dossiers import audit_lines

        text = "\n".join(audit_lines({"angle_fact_fit": {ANGLES[0]: 0.67, ANGLES[2]: 0.0}}, {}))
        self.assertIn("Fact-fit:** 0.67 GTA 6 delay", text)


class SelectionUnchangedTests(unittest.TestCase):
    def test_best_variant_ignores_fact_fit(self):
        import inspect

        from core.pipeline import best_variant_index

        self.assertNotIn("fact_fit", inspect.signature(best_variant_index).parameters)


if __name__ == "__main__":
    unittest.main()
