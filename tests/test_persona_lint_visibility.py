"""Run 74: a style hit the operator has to read the log for is not a gate.

`persona_lint` fired on "but here's the thing" and reported it as a bare log line
above the script:

    13:07:55 [WARNING] persona lint: but here's the thing

`core/pipeline.py` already carries the hits into `result.features["persona_lint"]`
— nothing had ever displayed them, so the phrase sailed past the report card and
into an A grade. Style is not a fact problem, so this shows without forcing a
fact review; it just has to be on screen before `Proceed?`.
"""

from __future__ import annotations

import unittest

from core.ui import display_fact_engine_report


class _Printed(list):
    def __call__(self, *args) -> None:
        self.append(args[0] if args else "")


class TestPersonaHitsAreShown(unittest.TestCase):
    def test_a_hit_reaches_the_screen(self):
        printed = _Printed()
        display_fact_engine_report({"persona_lint": ["but here's the thing"]}, print_fn=printed)
        text = " ".join(printed).lower()
        self.assertIn("but here's the thing", text)
        self.assertIn("style", text)

    def test_a_style_hit_does_not_force_a_fact_review(self):
        needs_review = display_fact_engine_report(
            {"persona_lint": ["buckle up"]}, print_fn=_Printed()
        )
        self.assertFalse(needs_review)

    def test_a_clean_script_prints_no_style_line(self):
        printed = _Printed()
        display_fact_engine_report({"persona_lint": []}, print_fn=printed)
        self.assertNotIn("style", " ".join(printed).lower())

    def test_missing_key_is_not_an_error(self):
        display_fact_engine_report({}, print_fn=_Printed())

    def test_a_real_fact_problem_still_forces_review(self):
        needs_review = display_fact_engine_report(
            {"persona_lint": ["buckle up"], "tier_warnings": ["signal-tier claim unbacked"]},
            print_fn=_Printed(),
        )
        self.assertTrue(needs_review)


if __name__ == "__main__":
    unittest.main()
