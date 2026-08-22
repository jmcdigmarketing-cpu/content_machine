"""Candidate 52: the avoid-list must explain itself, not just mute topics.

`graveyard()` returns topics whose measured engaged-rate fell below the floor. That tells
the operator *what* to stop making and nothing about *why*, so the same mistake gets
repeated under a different topic name.

Every code here is read from the `quality_json` the run already persisted — no new
scoring, no inference. A run that predates quality persistence gets an honest empty list
rather than a guessed reason.
"""

import unittest

from core.topic_db import (
    GRAVEYARD_REASONS,
    explain_reason_codes,
    reason_codes_for_quality,
)


class TestReasonCodes(unittest.TestCase):
    def test_thin_facts_from_claim_support(self):
        self.assertIn("thin_facts", reason_codes_for_quality({"claim_support_rate": 0.42}))

    def test_good_support_is_not_thin(self):
        self.assertNotIn("thin_facts", reason_codes_for_quality({"claim_support_rate": 0.95}))

    def test_recap_from_authenticity_verdict(self):
        self.assertIn("recap", reason_codes_for_quality({"authenticity_verdict": "review"}))
        self.assertIn("recap", reason_codes_for_quality({"authenticity_verdict": "block"}))
        self.assertNotIn("recap", reason_codes_for_quality({"authenticity_verdict": "ok"}))

    def test_weak_hook_threshold(self):
        self.assertIn("weak_hook", reason_codes_for_quality({"hook_score": 55}))
        self.assertNotIn("weak_hook", reason_codes_for_quality({"hook_score": 72}))

    def test_ungrounded_from_conflicts_or_tier_warnings(self):
        self.assertIn("ungrounded", reason_codes_for_quality({"fact_conflict_count": 1}))
        self.assertIn("ungrounded", reason_codes_for_quality({"tier_warning_count": 3}))
        self.assertNotIn(
            "ungrounded",
            reason_codes_for_quality({"fact_conflict_count": 0, "tier_warning_count": 0}),
        )

    def test_several_reasons_can_apply(self):
        codes = reason_codes_for_quality(
            {"claim_support_rate": 0.2, "authenticity_verdict": "review", "hook_score": 30}
        )
        self.assertEqual(codes, ["thin_facts", "recap", "weak_hook"])


class TestHonestBlanks(unittest.TestCase):
    """A missing quality block must not become a fabricated reason."""

    def test_no_quality_means_no_codes(self):
        self.assertEqual(reason_codes_for_quality({}), [])
        self.assertEqual(reason_codes_for_quality(None), [])

    def test_non_dict_is_safe(self):
        self.assertEqual(reason_codes_for_quality("nope"), [])

    def test_clean_run_has_no_codes(self):
        clean = {
            "claim_support_rate": 1.0,
            "authenticity_verdict": "ok",
            "hook_score": 80,
            "fact_conflict_count": 0,
            "tier_warning_count": 0,
        }
        self.assertEqual(reason_codes_for_quality(clean), [])

    def test_non_numeric_scores_are_ignored(self):
        self.assertEqual(reason_codes_for_quality({"hook_score": "n/a"}), [])


class TestExplanation(unittest.TestCase):
    def test_blank_when_nothing_is_evidenced(self):
        self.assertEqual(explain_reason_codes([]), "")

    def test_unknown_codes_are_dropped(self):
        self.assertEqual(explain_reason_codes(["not_a_code"]), "")

    def test_duplicates_collapse(self):
        self.assertEqual(explain_reason_codes(["recap", "recap"]), explain_reason_codes(["recap"]))

    def test_every_declared_code_has_a_label(self):
        labels = dict(GRAVEYARD_REASONS)
        for code, _ in GRAVEYARD_REASONS:
            self.assertTrue(labels[code].strip(), code)
            self.assertTrue(explain_reason_codes([code]))


if __name__ == "__main__":
    unittest.main()
