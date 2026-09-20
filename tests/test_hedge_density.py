"""#800: hedge density sits beside claim support and the grade falls.

decisions.md §25 left '12/12 backed' as 'no bare assertions left' after the
claim rewriter restated unsupported claims as attributed speculation. Wave 26
decides that: count hedge phrases per 100 spoken words, print the number, and
let grounding drop. Grade-only — #345 still lets a hedged rumor through the
render gate.

Run 58 shipped four consecutive weasel sentences at 30% support. Those strings
are the fixture, not a paraphrase.
"""

from __future__ import annotations

import unittest

from core.claim_types import hedge_density
from core.claim_verifier import ClaimVerification, VerifiedClaim, display_claim_verification
from core.run_quality import build_quality
from core.video_grade import _grounding_score

# Diagnosis §4.1 / run 58: consecutive weasel sentences, not a clean rewrite.
RUN58_HEDGED = (
    "Reports claim a hacker breached the studio last night. Unconfirmed, but "
    "supposedly a build leaked to YouTube. The rumor is that the trailer drops "
    "Friday. Rockstar reportedly denied it. The footage allegedly showed Vice City."
)
RUN58_BARE = (
    "A hacker breached the studio last night. A build appeared on YouTube. "
    "The trailer drops Friday. Rockstar denied it. The footage showed Vice City."
)


def _verification(total: int, unsupported: int) -> ClaimVerification:
    v = ClaimVerification()
    for i in range(total):
        v.claims.append(VerifiedClaim(claim=f"claim {i}", supported=i >= unsupported))
    return v


class TestHedgeDensity(unittest.TestCase):
    def test_run58_weasel_script_is_dense(self) -> None:
        self.assertGreater(hedge_density(RUN58_HEDGED), 5.0)

    def test_the_bare_twin_is_not(self) -> None:
        self.assertEqual(hedge_density(RUN58_BARE), 0.0)

    def test_empty_script_is_zero_not_a_warning(self) -> None:
        self.assertEqual(hedge_density(""), 0.0)


class TestGroundingFallsWithHedgeDensity(unittest.TestCase):
    def test_run58_grounds_below_the_bare_twin(self) -> None:
        """On unmodified code both score 100 because grounding ignored hedges."""
        hedged = _grounding_score(
            {
                "ungrounded_count": 0,
                "trade_warning_count": 0,
                "unsupported_claim_count": 0,
                "fact_conflict_count": 0,
                "tier_warning_count": 0,
                "hedge_density": hedge_density(RUN58_HEDGED),
            }
        )[0]
        bare = _grounding_score(
            {
                "ungrounded_count": 0,
                "trade_warning_count": 0,
                "unsupported_claim_count": 0,
                "fact_conflict_count": 0,
                "tier_warning_count": 0,
                "hedge_density": hedge_density(RUN58_BARE),
            }
        )[0]
        self.assertEqual(bare, 100.0)
        self.assertLess(hedged, bare)

    def test_zero_density_does_not_change_a_clean_score(self) -> None:
        score, note = _grounding_score(
            {
                "ungrounded_count": 0,
                "trade_warning_count": 0,
                "unsupported_claim_count": 0,
                "hedge_density": 0.0,
            }
        )
        self.assertEqual(score, 100.0)
        self.assertEqual(note, "fully grounded")


class TestDensityIsPrintedAndPersisted(unittest.TestCase):
    def test_build_quality_records_run58_density(self) -> None:
        quality = build_quality(script=RUN58_HEDGED, channel_id="tapin")
        self.assertGreater(quality["hedge_density"], 5.0)

    def test_claim_check_prints_density_next_to_support(self) -> None:
        payload = _verification(12, 0).to_dict()
        payload["hedge_density"] = hedge_density(RUN58_HEDGED)
        lines: list[str] = []
        display_claim_verification(payload, print_fn=lines.append)
        text = "\n".join(lines)
        self.assertIn("12/12", text)
        self.assertIn("hedge density", text)
        self.assertNotIn("WARNING", text.upper().split("HEDGE")[0])

    def test_zero_density_is_silent_on_a_clean_check(self) -> None:
        payload = _verification(12, 0).to_dict()
        payload["hedge_density"] = 0.0
        lines: list[str] = []
        display_claim_verification(payload, print_fn=lines.append)
        self.assertNotIn("hedge density", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
