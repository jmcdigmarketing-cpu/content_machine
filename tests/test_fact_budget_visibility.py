"""Ground truth must never be dropped without saying so.

The operator believed an 18-fact cap was truncating pasted articles. There is no
18 anywhere — 18 was that run's actual count, and nothing was dropped (18 of a
24-line cap, 3110 of a 4500-char budget). But the instinct was right about the
consequence: a full news article does not fit, because `link_facts` chops a page
into 400-char lines and a 6-8k-char article blows the budget.

`facts_for_prompt` decides that, and it decided it with a bare `break`. `core/ui.py`
happens to compare the counts afterwards and print a note, but every other caller —
`title_generator`, `auto_generate`, `content_engine` — got a silently shortened
fact set. Operator key facts are the highest-priority ground truth in the system
(decisions §4); losing them quietly is the worst place for a silent truncation.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.operator_facts import (
    facts_for_prompt,
    last_fact_budget_report,
    max_operator_key_facts,
    operator_key_fact_char_budget,
)


def _lines(n: int, chars: int = 300) -> list[str]:
    return [f"Fact {i} " + ("x" * chars) for i in range(n)]


class TestDefaultsFitARealArticle(unittest.TestCase):
    """A single BBC-length article should not need an env var to survive."""

    def test_char_budget_holds_a_full_article(self):
        self.assertGreaterEqual(operator_key_fact_char_budget(), 12000)

    def test_line_cap_holds_a_chopped_article(self):
        # link_facts emits ~400-char lines, so a long read is dozens of them.
        self.assertGreaterEqual(max_operator_key_facts(), 40)


class TestDroppedFactsAreReported(unittest.TestCase):
    def test_nothing_dropped_reports_nothing_dropped(self):
        facts = _lines(5)
        sent = facts_for_prompt(facts)
        report = last_fact_budget_report()
        self.assertEqual(len(sent), 5)
        self.assertEqual(report["dropped"], 0)
        self.assertEqual(report["reason"], "")

    def test_char_budget_overflow_names_the_count_and_the_knob(self):
        with patch.dict(os.environ, {"OPERATOR_KEY_FACT_CHAR_BUDGET": "700"}, clear=False):
            sent = facts_for_prompt(_lines(10))
            report = last_fact_budget_report()
        self.assertLess(len(sent), 10)
        self.assertEqual(report["dropped"], 10 - len(sent))
        self.assertIn("OPERATOR_KEY_FACT_CHAR_BUDGET", report["reason"])

    def test_line_cap_overflow_names_the_other_knob(self):
        with patch.dict(
            os.environ,
            {"MAX_OPERATOR_KEY_FACTS": "3", "OPERATOR_KEY_FACT_CHAR_BUDGET": "100000"},
            clear=False,
        ):
            sent = facts_for_prompt(_lines(10))
            report = last_fact_budget_report()
        self.assertEqual(len(sent), 3)
        self.assertEqual(report["dropped"], 7)
        self.assertIn("MAX_OPERATOR_KEY_FACTS", report["reason"])

    def test_the_drop_is_logged_not_only_recorded(self):
        with (
            patch.dict(os.environ, {"OPERATOR_KEY_FACT_CHAR_BUDGET": "700"}, clear=False),
            self.assertLogs("content_machine.core.operator_facts", level="WARNING") as caught,
        ):
            facts_for_prompt(_lines(10))
        self.assertTrue(any("operator fact" in m.lower() for m in caught.output), caught.output)


if __name__ == "__main__":
    unittest.main()
