"""#863: the auto-research verdict, computed once ten runs carry it.

Wave 34 turned auto-research on by default on the promise of a keep / retune / switch-off call
after ten measured runs; `ops auto-research` (wave 35) counts them but left the call to whoever
read the numbers. `verdict` now makes it from the same summary once ten runs stored their kept
lines:

- no kept line ever backed a supported claim -> switch off (`AUTO_RESEARCH_ENABLED=false`);
- under 10% of kept lines cited -> retune (`AUTO_RESEARCH_URLS=2`, fewer pages);
- the deadline cut half the runs or more -> give it longer (`AUTO_RESEARCH_DEADLINE_S`);
- otherwise keep.

`ops auto-research` prints it, and `ops status` repeats it once it is due.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _run(rid, *, lines=3, kept=None, reason="ok", cited_lines=()):
    kept = (
        kept
        if kept is not None
        else [f"Line {rid}-{i} about the patch notes and the meta" for i in range(lines)]
    )
    claims = [{"supported": True, "citation_line": line} for line in cited_lines]
    features = {"auto_research": {"pages": 2, "lines": len(kept), "off_topic": 0, "reason": reason,
                                  "kept_lines": kept},
                "claim_verification": {"claims": claims}}  # fmt: skip
    return SimpleNamespace(id=rid, input_topic="t", features_json=json.dumps(features))


class VerdictTests(unittest.TestCase):
    def _verdict(self, runs):
        from analytics.auto_research_report import summarize, verdict

        return verdict(summarize(runs))

    def test_not_due_before_ten(self):
        self.assertIsNone(self._verdict([_run(i) for i in range(9)]))

    def test_never_cited_switches_off(self):
        got = self._verdict([_run(i) for i in range(10)])
        self.assertEqual(got["call"], "switch off")
        self.assertIn("AUTO_RESEARCH_ENABLED=false", got["line"])

    def test_rarely_cited_retunes(self):
        runs = [_run(i) for i in range(10)]
        runs[0] = _run(0, cited_lines=["Line 0-0 about the patch notes and the meta"])
        got = self._verdict(runs)
        self.assertEqual(got["call"], "retune")
        self.assertIn("AUTO_RESEARCH_URLS=2", got["line"])

    def test_cut_by_the_deadline_gets_longer(self):
        runs = []
        for i in range(10):
            reason = "deadline" if i < 5 else "ok"
            runs.append(
                _run(
                    i, reason=reason, cited_lines=[f"Line {i}-0 about the patch notes and the meta"]
                )
            )
        got = self._verdict(runs)
        self.assertEqual(got["call"], "longer")
        self.assertIn("AUTO_RESEARCH_DEADLINE_S", got["line"])

    def test_well_cited_keeps(self):
        runs = [_run(i, cited_lines=[f"Line {i}-0 about the patch notes and the meta"])
                for i in range(10)]  # fmt: skip
        self.assertEqual(self._verdict(runs)["call"], "keep")

    def test_runs_without_kept_lines_do_not_count(self):
        runs = [_run(i) for i in range(9)] + [
            SimpleNamespace(id=99, input_topic="t", features_json=json.dumps(
                {"auto_research": {"pages": 1, "lines": 2, "reason": "ok"}}))]  # fmt: skip
        self.assertIsNone(self._verdict(runs))


class OutputTests(unittest.TestCase):
    def test_the_report_prints_the_call(self):
        from analytics.auto_research_report import render, summarize

        text = render(summarize([_run(i) for i in range(10)]), "tapin")
        self.assertIn("#863 verdict: switch off", text)
        self.assertNotIn("more run(s) before the #863 verdict", text)

    def test_status_repeats_it_when_due(self):
        from core.status import build_status_lines

        runs = [_run(i) for i in range(10)]
        with patch("analytics.auto_research_report._runs", return_value=runs):
            lines = build_status_lines("tapin")
        self.assertTrue(any("#863 verdict: switch off" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
