"""#861 show the auto-research lines, #863 measure them across runs.

Wave 34 printed only "Auto-research: N line(s) kept" - the operator could not see what
was kept, and nothing persisted the lines, so #863's question ("did the claim verifier
ever cite them?") could not be answered from the stored runs. The report now carries
`kept_lines`; `report_lines` shows them; `ops auto-research` counts pages, lines, and
the lines a supported claim actually cited.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from tests.test_auto_research import _attach, _signals


class TestReportCarriesLines(unittest.TestCase):
    def test_kept_lines_in_report(self) -> None:
        _new, report, _ = _attach(_signals())
        self.assertEqual(report["lines"], len(report["kept_lines"]))
        self.assertTrue(any("114 of the 115" in line for line in report["kept_lines"]))


class TestReportLines(unittest.TestCase):
    def test_shows_first_five_and_counts_the_rest(self) -> None:
        from core.auto_research import report_lines

        kept = [f"Fact number {i} about City." for i in range(7)]
        out = report_lines(
            {"pages": 2, "lines": 7, "off_topic": 1, "reason": "ok", "kept_lines": kept}
        )
        self.assertTrue(out[0].startswith("Auto-research: 2 page(s) read, 7 line(s) kept"))
        self.assertIn("Fact number 0 about City.", out[1])
        self.assertEqual(len([o for o in out if "Fact number" in o]), 5)
        self.assertIn("+2 more", out[-1])

    def test_no_report_no_lines(self) -> None:
        from core.auto_research import report_lines

        self.assertEqual(report_lines(None), [])

    def test_old_report_without_lines_prints_header_only(self) -> None:
        from core.auto_research import report_lines

        out = report_lines({"pages": 1, "lines": 2, "off_topic": 0, "reason": "ok"})
        self.assertEqual(len(out), 1)


def _run(rid, research=None, claims=None):
    features = {}
    if research is not None:
        features["auto_research"] = research
    if claims is not None:
        features["claim_verification"] = {"claims": claims}
    return SimpleNamespace(id=rid, input_topic=f"topic {rid}", features_json=json.dumps(features))


class TestSummary(unittest.TestCase):
    def test_counts_pages_lines_and_cited(self) -> None:
        from analytics.auto_research_report import summarize

        runs = [
            _run(
                1,
                {
                    "pages": 2,
                    "lines": 2,
                    "off_topic": 1,
                    "reason": "ok",
                    "kept_lines": [
                        "Manchester City were found guilty of 114 of the 115 charges.",
                        "A commission will decide sanctions.",
                    ],
                },
                claims=[
                    {
                        "claim": "City were found guilty on 114 charges",
                        "supported": True,
                        "citation_line": "- Manchester City were found guilty of 114 of the 115 charges.",
                    },
                    {"claim": "x", "supported": False, "citation_line": ""},
                ],
            ),
            _run(2, {"pages": 0, "lines": 0, "off_topic": 0, "reason": "no web results"}),
            _run(3),  # before wave 34: no report at all
        ]
        s = summarize(runs)
        self.assertEqual(s["runs"], 3)
        self.assertEqual(s["with_report"], 2)
        self.assertEqual(s["pages"], 2)
        self.assertEqual(s["lines"], 2)
        self.assertEqual(s["off_topic"], 1)
        self.assertEqual(s["cited"], 1)
        self.assertEqual(s["reasons"]["no web results"], 1)

    def test_render_says_when_there_is_nothing(self) -> None:
        from analytics.auto_research_report import render, summarize

        text = render(summarize([_run(1)]))
        self.assertIn("No run has an auto-research report yet", text)

    def test_ops_verb_registered(self) -> None:
        from scripts.ops import COMMANDS

        self.assertIn("auto-research", COMMANDS)


if __name__ == "__main__":
    unittest.main()
