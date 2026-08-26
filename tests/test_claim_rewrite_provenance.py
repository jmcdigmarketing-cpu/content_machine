"""Candidate 322: a hedged script must not report the score of an honest one.

Live run 71: the claim verifier found **7 of 12 claims unsupported**. The rewrite pass
(`_maybe_rewrite_unsupported_claims`) then restated each as attributed speculation
("Reports claim a hacker breached...", "allegedly showed"), re-verified, and adopted
the result. The console printed:

    [ok] Claim check: 12/12 factual claim(s) backed by the facts.

Same verifier, rewritten script. Nothing was verified between the two numbers — the
claims were hedged. But only the post-rewrite verdict was persisted, so
`quality_json` recorded support_rate 1.0 / 0 unsupported, the report card graded the
run A, and the #52 graveyard codes could never emit `thin_facts` for it.

Behaviour is deliberately unchanged: this records and surfaces, it does not gate or
re-grade. The operator decides.
"""

import unittest

from core.claim_verifier import ClaimVerification, VerifiedClaim, display_claim_verification
from core.run_quality import build_quality
from core.topic_db import reason_codes_for_quality


def _verification(total: int, unsupported: int) -> ClaimVerification:
    v = ClaimVerification()
    for i in range(total):
        v.claims.append(VerifiedClaim(claim=f"claim {i}", supported=i >= unsupported))
    return v


def _run71_rewritten() -> ClaimVerification:
    """The real shape: 7/12 unsupported, rewritten, re-check clean."""
    after = _verification(12, 0)
    after.rewritten = True
    after.pre_rewrite_unsupported = 7
    after.pre_rewrite_total = 12
    return after


def _quality(verification: ClaimVerification) -> dict:
    """Real build_quality over a real features dict — no hand-built quality blocks."""
    return build_quality(
        script="A grounded sentence about the topic. " * 20,
        channel_id="tapin",
        features={"claim_verification": verification.to_dict()},
    )


class TestPreRewriteSurvives(unittest.TestCase):
    def test_rewritten_run_carries_both_numbers(self):
        d = _run71_rewritten().to_dict()
        self.assertEqual(d["support_rate"], 1.0)
        self.assertTrue(d["rewritten"])
        self.assertEqual(d["pre_rewrite_unsupported"], 7)
        self.assertEqual(d["pre_rewrite_total"], 12)
        self.assertAlmostEqual(d["pre_rewrite_support_rate"], 0.417, places=3)

    def test_untouched_run_gains_no_keys(self):
        # Existing readers must see exactly the old shape when nothing was rewritten.
        d = _verification(12, 0).to_dict()
        self.assertEqual(set(d), {"total", "supported", "support_rate", "unsupported"})

    def test_pre_rate_is_none_when_not_rewritten(self):
        self.assertIsNone(_verification(12, 3).pre_rewrite_support_rate)


class TestQualityBlock(unittest.TestCase):
    def test_quality_records_the_pre_rewrite_figures(self):
        quality = _quality(_run71_rewritten())
        self.assertEqual(quality["claim_support_rate"], 1.0)
        self.assertTrue(quality["claims_rewritten"])
        self.assertEqual(quality["pre_rewrite_unsupported_count"], 7)
        self.assertAlmostEqual(quality["pre_rewrite_support_rate"], 0.417, places=3)

    def test_clean_run_has_no_rewrite_keys(self):
        quality = _quality(_verification(12, 0))
        self.assertNotIn("claims_rewritten", quality)
        self.assertNotIn("pre_rewrite_support_rate", quality)


class TestGraveyardCodesSeeHedgedRuns(unittest.TestCase):
    """The #52 codes read claim_support_rate — which a rewrite launders to 1.0."""

    def test_run71_now_earns_thin_facts(self):
        quality = _quality(_run71_rewritten())
        self.assertIn("thin_facts", reason_codes_for_quality(quality))

    def test_a_genuinely_clean_run_still_does_not(self):
        quality = _quality(_verification(12, 0))
        self.assertNotIn("thin_facts", reason_codes_for_quality(quality))

    def test_a_light_rewrite_stays_above_the_floor(self):
        after = _verification(12, 0)
        after.rewritten = True
        after.pre_rewrite_unsupported = 1  # 11/12 = 0.917, not thin
        after.pre_rewrite_total = 12
        quality = _quality(after)
        self.assertNotIn("thin_facts", reason_codes_for_quality(quality))


class TestOperatorSurface(unittest.TestCase):
    def test_the_run71_line_now_says_it_was_hedged(self):
        lines: list[str] = []
        needs_review = display_claim_verification(
            _run71_rewritten().to_dict(), print_fn=lines.append
        )
        text = "\n".join(lines)
        self.assertTrue(needs_review)
        self.assertIn("12/12", text)  # the old, true-but-misleading line still prints
        self.assertIn("7 of those were restated", text)
        self.assertIn("not evidenced", text)

    def test_a_clean_run_prints_only_the_ok_line(self):
        lines: list[str] = []
        needs_review = display_claim_verification(
            _verification(12, 0).to_dict(), print_fn=lines.append
        )
        self.assertFalse(needs_review)
        self.assertNotIn("restated", "\n".join(lines))

    def test_unsupported_claims_still_report_normally(self):
        lines: list[str] = []
        needs_review = display_claim_verification(
            _verification(12, 3).to_dict(), print_fn=lines.append
        )
        self.assertTrue(needs_review)
        self.assertIn("3 of 12", "\n".join(lines))


class TestRewriteStampedAtTheSource(unittest.TestCase):
    """The stamp must come from the adopted-rewrite branch, not the test's own hand."""

    def test_adopted_rewrite_sets_provenance(self):
        from unittest.mock import patch

        import core.content_engine as ce

        before = _verification(12, 7)
        after = _verification(12, 0)
        with patch.object(ce, "_call_content_llm", return_value={"script": "w " * 400}):
            with patch("core.claim_verifier.verify_claims", return_value=after):
                script, result = ce._maybe_rewrite_unsupported_claims(
                    "w " * 400, before, "corpus", "topic", None
                )
        self.assertTrue(result.rewritten)
        self.assertEqual(result.pre_rewrite_unsupported, 7)
        self.assertEqual(result.pre_rewrite_total, 12)

    def test_rejected_rewrite_leaves_the_original_unstamped(self):
        from unittest.mock import patch

        import core.content_engine as ce

        before = _verification(12, 7)
        no_better = _verification(12, 7)
        with patch.object(ce, "_call_content_llm", return_value={"script": "w " * 400}):
            with patch("core.claim_verifier.verify_claims", return_value=no_better):
                _, result = ce._maybe_rewrite_unsupported_claims(
                    "w " * 400, before, "corpus", "topic", None
                )
        self.assertFalse(result.rewritten)


if __name__ == "__main__":
    unittest.main()
