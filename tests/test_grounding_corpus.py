"""#350. Frozen grounding verdicts in CI — loosening a gate must fail here."""

from __future__ import annotations

import unittest

from core.grounding_corpus import evaluate_case, load_grounding_corpus


class TestGroundingCorpus(unittest.TestCase):
    def test_corpus_has_at_least_twenty_frozen_cases(self):
        cases = load_grounding_corpus()
        self.assertGreaterEqual(len(cases), 20)

    def test_each_frozen_verdict_still_matches(self):
        for case in load_grounding_corpus():
            with self.subTest(case=case.get("id")):
                got = evaluate_case(case)
                expect = list(case.get("expect_ungrounded") or [])
                self.assertEqual(got, expect)

    def test_loosening_generic_title_case_would_fail_ci(self):
        """The Community / Drop Your Thoughts must stay unflagged. A gate that
        starts treating common title-case as entities fails this case.
        """
        case = next(c for c in load_grounding_corpus() if c.get("id") == "generic-title-case")
        self.assertEqual(evaluate_case(case), [])

    def test_the_counter_intuitive_verdicts_say_why_they_are_frozen(self):
        """A frozen corpus records behaviour, and behaviour and *desired*
        behaviour are not the same thing. Three cases look wrong at a glance —
        `Lakers` flagged when the facts say "Los Angeles", `Take-Two` flagged
        when the facts say "the parent company of Rockstar Games", and generic
        title-case deliberately unflagged. Without a reason attached, the next
        reader cannot tell a deliberate verdict from an accidental snapshot, and
        someone genuinely fixing the finder will read a failing case as a
        regression and re-freeze the bug.
        """
        by_id = {c.get("id"): c for c in load_grounding_corpus()}
        for case_id in ("lebron-grounded", "run71-script-names", "generic-title-case"):
            with self.subTest(case=case_id):
                self.assertIn(case_id, by_id)
                self.assertTrue(
                    (by_id[case_id].get("note") or "").strip(),
                    f"{case_id} freezes a non-obvious verdict with no stated reason",
                )

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("grounding-corpus", ops.COMMANDS)
