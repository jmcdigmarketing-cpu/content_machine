"""#1061: the weekly report as three decisions - more of, less of, try next.

Measured 2026-10-10 on TapIn's 39 videos: the digest called "three decisions" was the first
three per-dimension lines in dimension order ("Make more ufc videos", "Lead with the 'ranking'
angle again", ...). It never said what to do less of unless a loser happened to sort early,
and it had no "try next" at all. Each decision now carries the number it came from.
"""

from __future__ import annotations

import unittest


def _group(value, avg, n, baseline=0.30):
    return {"value": value, "avg": avg, "n": n, "delta": avg - baseline}


REPORT = {
    "channel_id": "tapin",
    "ready": True,
    "n": 39,
    "baseline": 0.30,
    "dimensions": {
        "domain": [_group("ufc", 0.39, 8), _group("gaming", 0.28, 30)],
        "angle": [_group("ranking", 0.49, 3), _group("general", 0.26, 11)],
        "title_structure": [_group("question", 0.41, 7), _group("statement", 0.19, 8)],
    },
    "untested": [
        {"dimension": "angle", "value": "explainer", "avg": 0.44, "n": 2},
        {"dimension": "domain", "value": "nfl", "avg": 0.31, "n": 1},
        {"dimension": "angle", "value": "rumour", "avg": 0.12, "n": 2},
    ],
    "next_actions": ["Make more ufc videos (39% vs 30% baseline, n=8)"],
}


class ThreeDecisionsTests(unittest.TestCase):
    def _decisions(self, report=REPORT):
        from analytics.weekly_report import three_decisions

        return {d["kind"]: d for d in three_decisions(report)}

    def test_there_are_exactly_three_kinds_in_order(self):
        from analytics.weekly_report import three_decisions

        self.assertEqual([d["kind"] for d in three_decisions(REPORT)], ["more", "less", "try"])

    def test_more_of_is_the_winner_after_shrinking(self):
        """Ranked the way the recommenders rank (#352): each group pulled toward the baseline
        by four pseudo-videos. ranking (+19 on 3) still beats question titles (+11 on 7),
        and the line says how thin it is."""
        more = self._decisions()["more"]
        self.assertEqual((more["dimension"], more["value"]), ("angle", "ranking"))
        self.assertIn("49%", more["line"])
        self.assertIn("n=3", more["line"])
        self.assertIn("low confidence", more["line"])

    def test_a_lucky_pair_does_not_outrank_a_real_winner(self):
        report = {
            **REPORT,
            "dimensions": {
                "angle": [_group("ranking", 0.42, 3)],
                "title_structure": [_group("question", 0.41, 12)],
            },
        }
        more = self._decisions(report)["more"]
        self.assertEqual((more["dimension"], more["value"]), ("title_structure", "question"))

    def test_less_of_is_the_best_supported_loser(self):
        less = self._decisions()["less"]
        self.assertEqual((less["dimension"], less["value"]), ("title_structure", "statement"))
        self.assertIn("19%", less["line"])
        self.assertIn("30%", less["line"])

    def test_try_next_is_a_value_too_new_to_call(self):
        trial = self._decisions()["try"]
        self.assertEqual((trial["dimension"], trial["value"]), ("angle", "explainer"))
        self.assertIn("2 video", trial["line"])
        self.assertIn("44%", trial["line"])

    def test_without_an_untested_value_the_thinnest_winner_is_tried_again(self):
        report = {**REPORT, "untested": []}
        trial = self._decisions(report)["try"]
        self.assertEqual((trial["dimension"], trial["value"]), ("title_structure", "question"))
        self.assertIn("n=7", trial["line"])

    def test_no_real_loser_means_no_less_of(self):
        report = {
            **REPORT,
            "dimensions": {"domain": [_group("ufc", 0.39, 8), _group("gaming", 0.29, 30)]},
        }
        self.assertNotIn("less", self._decisions(report))

    def test_an_unready_report_decides_nothing(self):
        from analytics.weekly_report import three_decisions

        self.assertEqual(three_decisions({"ready": False}), [])

    def test_the_digest_is_the_three_decisions(self):
        from analytics.weekly_report import operator_digest

        text = operator_digest(REPORT)
        self.assertIn("More of:", text)
        self.assertIn("Less of:", text)
        self.assertIn("Try next:", text)
        self.assertNotIn("Make more ufc videos", text)

    def test_the_report_opens_with_them(self):
        from analytics.weekly_report import _format_body

        body = _format_body(REPORT)
        self.assertLess(body.index("More of:"), body.index("By domain:"))

    def test_build_report_keeps_values_too_new_to_score(self):
        from unittest.mock import patch

        from analytics import weekly_report

        rows = [{"engaged_rate": 0.30, "features": {"angle": "general"}} for _ in range(4)]
        rows += [{"engaged_rate": 0.50, "features": {"angle": "explainer"}} for _ in range(2)]
        with patch.object(weekly_report, "_load_rows", return_value=rows):
            report = weekly_report.build_report("tapin")
        self.assertEqual(
            [(u["dimension"], u["value"], u["n"]) for u in report["untested"]],
            [("angle", "explainer", 2)],
        )


if __name__ == "__main__":
    unittest.main()
