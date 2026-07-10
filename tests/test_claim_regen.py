"""Claim-slop rewrite: acting on the claim verifier's verdict (core/content_engine).

Live-run regression: a Palworld script asserted 5 invented patch details; the verifier
flagged them but nothing acted on it. `_maybe_rewrite_unsupported_claims` must rewrite
them out (or attribute them) and adopt the rewrite only when the re-verified unsupported
count actually drops.
"""

import unittest
from unittest.mock import patch

from core import content_engine as ce
from core.claim_verifier import ClaimVerification, VerifiedClaim

_FACTS = "Palworld's 1.0 patch notes hit 65,000 characters; Steam's limit is 32,000."
_ORIGINAL = (
    "Steam's limit is 32,000 characters and Palworld's notes hit 65,000. "
    "The patch adds an oil extraction system, new weapons, and a raid boss. "
    "My take: this is a bet on depth over accessibility and it will pay off."
)
_TOPIC = "Palworld 1.0 patch notes"


def _verification(unsupported_claims: list[str], total: int = 6) -> ClaimVerification:
    v = ClaimVerification()
    for c in unsupported_claims:
        v.claims.append(VerifiedClaim(claim=c, supported=False))
    for i in range(total - len(unsupported_claims)):
        v.claims.append(VerifiedClaim(claim=f"supported {i}", supported=True))
    return v


_DIRTY = _verification(["The patch adds an oil extraction system.", "The patch adds a raid boss."])


class TestClaimRewrite(unittest.TestCase):
    def test_adopts_rewrite_when_unsupported_count_drops(self):
        clean_script = (
            "Steam's limit is 32,000 characters and Palworld's notes hit 65,000. "
            "Reports claim the patch adds big new systems, but that's unconfirmed. "
            "My take: this is a bet on depth over accessibility and it will pay off."
        )
        with (
            patch.object(ce, "_call_content_llm", return_value={"script": clean_script}),
            patch("core.claim_verifier.verify_claims", return_value=_verification([])),
        ):
            script, verification = ce._maybe_rewrite_unsupported_claims(
                _ORIGINAL, _DIRTY, _FACTS, _TOPIC, []
            )
        self.assertEqual(script, clean_script)
        self.assertEqual(len(verification.unsupported), 0)

    def test_keeps_original_when_rewrite_does_not_improve(self):
        with (
            patch.object(ce, "_call_content_llm", return_value={"script": _ORIGINAL + " More."}),
            patch("core.claim_verifier.verify_claims", return_value=_DIRTY),
        ):
            script, verification = ce._maybe_rewrite_unsupported_claims(
                _ORIGINAL, _DIRTY, _FACTS, _TOPIC, []
            )
        self.assertEqual(script, _ORIGINAL)
        self.assertIs(verification, _DIRTY)

    def test_rejects_gutted_rewrite(self):
        with patch.object(ce, "_call_content_llm", return_value={"script": "Patch big."}):
            script, verification = ce._maybe_rewrite_unsupported_claims(
                _ORIGINAL, _DIRTY, _FACTS, _TOPIC, []
            )
        self.assertEqual(script, _ORIGINAL)  # <60% of original words → rejected pre-verify

    def test_llm_failure_keeps_original(self):
        with patch.object(ce, "_call_content_llm", side_effect=RuntimeError("router down")):
            script, verification = ce._maybe_rewrite_unsupported_claims(
                _ORIGINAL, _DIRTY, _FACTS, _TOPIC, []
            )
        self.assertEqual(script, _ORIGINAL)
        self.assertIs(verification, _DIRTY)

    def test_disabled_is_noop(self):
        with (
            patch.dict("os.environ", {"CLAIM_REGEN_ENABLED": "false"}, clear=False),
            patch.object(ce, "_call_content_llm") as llm,
        ):
            script, verification = ce._maybe_rewrite_unsupported_claims(
                _ORIGINAL, _DIRTY, _FACTS, _TOPIC, []
            )
        llm.assert_not_called()
        self.assertEqual(script, _ORIGINAL)

    def test_no_unsupported_is_noop(self):
        clean = _verification([])
        with patch.object(ce, "_call_content_llm") as llm:
            script, verification = ce._maybe_rewrite_unsupported_claims(
                _ORIGINAL, clean, _FACTS, _TOPIC, []
            )
        llm.assert_not_called()
        self.assertIs(verification, clean)


if __name__ == "__main__":
    unittest.main()
