"""Run 74: the fact prompt must select, not just collect.

Selection happens once, at intake, where the provenance actually exists —
`prompt_key_facts_result` knows which lines the operator typed, which came from a
scraped URL and when that page was published, and which came from the vault.
Downstream, `key_facts` is already the chosen set, so the script prompt, the
regeneration loop and the grounding display all see the same facts.

The vault still stores everything: selection decides what rides in the prompt,
never what is kept.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.ui import prompt_key_facts_result

SCAFFOLDING = [
    "Below, you will find everything shown off during the GTA 6 Extended Look:",
    "Check out the five biggest takeaways from the Grand Theft Auto 6 extended look below.",
    "Note: All of these details and features are compiled from various GTA 6 previews.",
]
DETAIL = [
    "Six Wanted Stars return in GTA 6, up from the five-star cap GTA 5 used.",
    "Rob Nelson said his most recent GTA 6 playthrough took around 80 hours to finish.",
    "Grand Theft Auto 6 releases on November 19 on PlayStation 5 and Xbox Series X/S.",
]


class _Printed(list):
    """`subsection()` calls print_fn() with no argument, so plain .append will not do."""

    def __call__(self, *args) -> None:
        self.append(args[0] if args else "")


def _run(answers, *, budget, printed=None):
    """Drive the fact prompt with a scripted operator, returning its selection."""
    it = iter(answers)
    printed = printed if printed is not None else _Printed()
    with (
        patch("core.obsidian_facts.load_fact_records", return_value=[]),
        patch("core.operator_facts.capture_facts_to_vault", return_value=None),
        patch("core.console_input.input_pending", return_value=False),
        patch("core.console_input.read_pending_lines", return_value=[]),
        patch("core.operator_facts.operator_key_fact_char_budget", return_value=budget),
    ):
        return prompt_key_facts_result(
            "GTA 6 extended look",
            "tapin",
            signals={},
            print_fn=printed,
            input_fn=lambda *_a, **_k: next(it, ""),
        )


class TestSelectionHappensAtIntake(unittest.TestCase):
    def test_the_selection_is_returned_not_the_raw_pool(self):
        answers = [*SCAFFOLDING, *DETAIL, ""]
        budget = sum(len(c) + 2 for c in DETAIL) + 10
        result = _run(answers, budget=budget)
        self.assertLess(len(result.facts), len(answers) - 1)

    def test_every_collected_fact_is_still_recorded(self):
        answers = [*SCAFFOLDING, *DETAIL, ""]
        result = _run(answers, budget=200)
        claims = {r.claim for r in result.records}
        for line in SCAFFOLDING + DETAIL:
            self.assertIn(line, claims)

    def test_what_was_held_back_is_named_on_screen(self):
        printed = _Printed()
        answers = [*SCAFFOLDING, *DETAIL, ""]
        _run(answers, budget=200, printed=printed)
        text = " ".join(printed).lower()
        self.assertIn("held back", text)

    def test_typed_facts_are_all_operator_tier(self):
        result = _run([*DETAIL, ""], budget=100_000)
        self.assertTrue(result.records)
        self.assertTrue(all(r.tier == "operator" for r in result.records), result.records)


class TestNothingChangesWhenEverythingFits(unittest.TestCase):
    def test_a_generous_budget_keeps_every_fact_in_order(self):
        result = _run([*DETAIL, ""], budget=100_000)
        self.assertEqual(result.facts, DETAIL)

    def test_no_hold_back_line_is_printed_when_nothing_was_held_back(self):
        printed = _Printed()
        _run([*DETAIL, ""], budget=100_000, printed=printed)
        self.assertNotIn("held back", " ".join(printed).lower())


if __name__ == "__main__":
    unittest.main()
