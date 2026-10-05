"""#967: `ops auto-research` says whether pasting went down.

Wave 58 looks up who's who on every run (#963) and calls each topic settled or fresh
(#964), so a settled topic should need no paste. The report now shows, per run, the
verdict, the who's-who lines and how many a supported claim cited, and whether facts were
pasted; and in sum, how many settled runs still had a paste against the runs before the
verdict existed.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

TEAM = "LeBron James - current team: Los Angeles Lakers (Wikidata, as of 2026-10-05)"


def _run(run_id, features):
    return SimpleNamespace(id=run_id, input_topic=f"topic {run_id}",
                           features_json=json.dumps(features))  # fmt: skip


RUNS = [
    _run(1, {"key_facts_count": 4}),
    _run(2, {"key_facts_count": 0}),
    _run(3, {
        "key_facts_count": 0,
        "research": {"need": "settled", "why": ["article since 2003"]},
        "entity_research": {"names": ["LeBron James"], "lines": 4, "kept_lines": [TEAM]},
        "claim_verification": {"claims": [
            {"claim": "LeBron plays for the Lakers", "supported": True, "citation_line": TEAM}]},
    }),
    _run(4, {
        "key_facts_count": 2,
        "research": {"need": "settled", "why": []},
        "entity_research": {"names": ["Lakers"], "lines": 2, "kept_lines": []},
    }),
    _run(5, {
        "key_facts_count": 3,
        "research": {"need": "fresh", "why": ["released 4 days ago"]},
        "entity_research": {"names": ["Ghost of Yotei"], "lines": 1, "kept_lines": []},
    }),
]  # fmt: skip


class SummaryTests(unittest.TestCase):
    def test_the_research_counts(self):
        from analytics.auto_research_report import summarize

        research = summarize(RUNS)["research"]
        self.assertEqual(research["with_verdict"], 3)
        self.assertEqual(research["settled"], 2)
        self.assertEqual(research["settled_pasted"], 1)
        self.assertEqual(research["fresh"], 1)
        self.assertEqual(research["fresh_pasted"], 1)
        self.assertEqual(research["who_lines"], 7)
        self.assertEqual(research["who_cited"], 1)
        self.assertEqual(research["before"], 2)
        self.assertEqual(research["before_pasted"], 1)

    def test_the_report_says_it(self):
        from analytics.auto_research_report import render, summarize

        text = render(summarize(RUNS), "tapin")
        self.assertIn("settled 2 (pasted 1)", text)
        self.assertIn("fresh 1 (pasted 1)", text)
        self.assertIn("who's-who lines 7, cited 1", text)
        self.assertIn("before the verdict: 1 of 2 run(s) had pasted facts", text)

    def test_a_channel_with_only_old_runs_still_reports(self):
        from analytics.auto_research_report import render, summarize

        text = render(summarize(RUNS[:2]), "tapin")
        self.assertIn("no run has a settled/fresh verdict yet", text)


if __name__ == "__main__":
    unittest.main()
