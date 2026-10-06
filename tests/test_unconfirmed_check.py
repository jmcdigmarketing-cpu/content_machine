"""#977: does unconfirmed mode hold up?

Wave 61 (#339) writes a fresh topic with thin facts in unconfirmed mode: what is not confirmed
is said with a label ("not confirmed yet", "early reports say", "reportedly") instead of being
dropped. Nothing checked afterwards whether those labelled claims turned out true.
`analytics/unconfirmed_check` takes each run written in that mode, finds its labelled sentences,
and reads the facts of later runs on the same subject (a shared name from
`apis.topic_tokens.title_phrases`):

- contradicted - `core.facts.conflicts.find_fact_conflicts` finds the later facts disagreeing;
- confirmed - every number and name in the claim (label stripped) is in the later facts;
- open - otherwise, including a claim with nothing specific to check.

The totals print in `ops auto-research` and, once any claim has resolved, in `ops status`.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = (
    "Early reports say Jon Jones beat Tom Aspinall at UFC 321. "
    "Reportedly Team Cherry sold 2 million copies of Silksong. "
    "Not confirmed yet: Silksong gets a sequel in 2027. "
    "Fans are excited either way."
)


def _run(rid, topic, *, script="", mode="", facts=""):
    quality = {"script_mode": mode} if mode else {}
    return SimpleNamespace(id=rid, selected_topic=topic, input_topic=topic, script=script,
                           quality_json=json.dumps(quality),
                           features_json=json.dumps({"grounding_text": facts}))  # fmt: skip


LATER_FACTS = (
    "Tom Aspinall beat Jon Jones at UFC 321.\n"
    "Team Cherry sold 2 million copies of Silksong in three days."
)


class ClaimTests(unittest.TestCase):
    def test_labelled_sentences(self):
        from analytics.unconfirmed_check import labelled_claims

        claims = labelled_claims(SCRIPT)
        self.assertEqual(len(claims), 3)
        self.assertNotIn("Fans are excited either way.", claims)

    def test_the_label_is_stripped_for_checking(self):
        from analytics.unconfirmed_check import strip_label

        self.assertEqual(strip_label("Reportedly Team Cherry sold 2 million copies."),
                         "Team Cherry sold 2 million copies.")  # fmt: skip
        self.assertEqual(strip_label("Not confirmed yet: Silksong gets a sequel."),
                         "Silksong gets a sequel.")  # fmt: skip


class CheckTests(unittest.TestCase):
    def _check(self, runs):
        from analytics import unconfirmed_check

        with patch("analytics.unconfirmed_check._runs", return_value=runs):
            return unconfirmed_check.check("tapin")

    def test_confirmed_contradicted_and_open(self):
        runs = [
            _run(10, "UFC and Silksong week", script=SCRIPT, mode="unconfirmed"),
            _run(11, "Arsenal transfer news", facts="Arsenal signed a striker."),
            _run(12, "Silksong sales and UFC 321 result", facts=LATER_FACTS),
        ]
        got = self._check(runs)
        self.assertEqual(got["runs"], 1)
        self.assertEqual(got["claims"], 3)
        self.assertEqual((got["confirmed"], got["contradicted"], got["open"]), (1, 1, 1))
        verdicts = {row["claim"][:20]: row["verdict"] for row in got["rows"]}
        self.assertEqual(verdicts["Early reports say Jo"], "contradicted")
        self.assertEqual(verdicts["Reportedly Team Cher"], "confirmed")
        self.assertEqual(verdicts["Not confirmed yet: S"], "open")

    def test_earlier_and_unrelated_runs_are_not_evidence(self):
        runs = [
            _run(9, "Silksong sales", facts=LATER_FACTS),  # before the claim: not evidence
            _run(10, "UFC and Silksong week", script=SCRIPT, mode="unconfirmed"),
            _run(11, "Arsenal transfer news", facts=LATER_FACTS),  # no shared name
        ]
        got = self._check(runs)
        self.assertEqual(got["open"], 3)

    def test_standard_runs_are_not_counted(self):
        got = self._check([_run(10, "Silksong", script=SCRIPT, mode="standard")])
        self.assertEqual(got["runs"], 0)


class ShownTests(unittest.TestCase):
    def test_lines(self):
        from analytics.unconfirmed_check import render_lines, status_line

        summary = {"runs": 2, "claims": 5, "confirmed": 2, "contradicted": 1, "open": 2,
                   "rows": []}  # fmt: skip
        with patch("analytics.unconfirmed_check.check", return_value=summary):
            text = "\n".join(render_lines("tapin"))
            line = status_line("tapin")
        self.assertIn("2 confirmed", text)
        self.assertIn("1 contradicted", text)
        self.assertIn("2 confirmed", line)
        empty = {"runs": 1, "claims": 3, "confirmed": 0, "contradicted": 0, "open": 3, "rows": []}
        with patch("analytics.unconfirmed_check.check", return_value=empty):
            self.assertEqual(status_line("tapin"), "")

    def test_status_prints_it(self):
        from core.status import build_status_lines

        with patch("analytics.unconfirmed_check.status_line", return_value="UNCONF STATUS"):
            self.assertIn("UNCONF STATUS", build_status_lines("tapin"))

    def test_auto_research_prints_it(self):
        from analytics import auto_research_report

        with patch("analytics.unconfirmed_check.render_lines", return_value=["  UNCONF LINE"]):
            text = auto_research_report.render(auto_research_report.summarize([]), "tapin")
        self.assertIn("UNCONF LINE", text)


if __name__ == "__main__":
    unittest.main()
