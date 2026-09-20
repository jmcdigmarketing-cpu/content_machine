"""#822: the render gate waives claims and keeps no record of it.

The item was filed as a conflict: #345 lets an unsupported **rumor** through
the gate when the script hedges it, and #800 then docks the grade per hedge, so
"the cheapest route past the hard gate is what the soft score punishes".

Measured before changing anything (2026-09-20, `tapin`, 87 runs / 37 verified):

- the hedged-rumor escape has fired **0 times**;
- there is **1** unsupported rumor in the whole archive;
- hedge density is median **0.66**/100w, max **5.75**, one script at >= 5.0;
- only **10** runs (id 76+) carry per-claim types at all - the other 27 predate
  #345, the same historical-coverage shape as #818.

So the conflict is theoretical on this evidence and neither layer should move
on n=10. What is wrong is that the question cost a full replay and is still
unanswerable for 27 runs: `warn_only_unsupported` is shown once in
`core/batch_review.py:253` and **never persisted**. Record the waiver instead,
so the next ten runs answer it.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

_HEDGED_RUMOR = "Rockstar reportedly delayed the game again."
_HARD_STAT = "The game sold 40 million copies."


def _verification(*claims: tuple[str, str]) -> dict:
    return {
        "total": len(claims) + 1,
        "supported": 1,
        "support_rate": 1 / (len(claims) + 1),
        "unsupported": [c for c, _ in claims],
        "unsupported_types": [t for _, t in claims],
        "claims": [{"claim": c, "type": t, "supported": False} for c, t in claims],
    }


class TestTheWaiverIsRecorded(unittest.TestCase):
    def test_a_hedged_rumor_waved_through_is_persisted(self) -> None:
        from core.run_quality import build_quality

        with (
            patch("core.authenticity.evaluate_authenticity") as auth,
            patch("core.engagement_predictor.predict_engaged_rate", return_value=None),
        ):
            auth.return_value.score = 80
            auth.return_value.gate_score = 100
            auth.return_value.verdict = "ok"
            auth.return_value.semantic_overlap = 0.0
            auth.return_value.recurrence = {}
            quality = build_quality(
                script="A script. " + _HEDGED_RUMOR,
                channel_id="tapin",
                features={"claim_verification": _verification((_HEDGED_RUMOR, "rumor"))},
            )

        self.assertEqual(quality.get("gate_waived_count"), 1)
        waived = quality.get("gate_waived") or []
        self.assertEqual(waived[0]["type"], "rumor")
        self.assertTrue(waived[0]["hedged"])

    def test_a_blocking_claim_is_not_a_waiver(self) -> None:
        """An unsupported stat stops the render; it was never waved through."""
        from core.run_quality import build_quality

        with (
            patch("core.authenticity.evaluate_authenticity") as auth,
            patch("core.engagement_predictor.predict_engaged_rate", return_value=None),
        ):
            auth.return_value.score = 80
            auth.return_value.gate_score = 100
            auth.return_value.verdict = "ok"
            auth.return_value.semantic_overlap = 0.0
            auth.return_value.recurrence = {}
            quality = build_quality(
                script="A script. " + _HARD_STAT,
                channel_id="tapin",
                features={"claim_verification": _verification((_HARD_STAT, "stat"))},
            )

        self.assertEqual(quality.get("gate_waived_count", 0), 0)
        self.assertNotIn("gate_waived", quality)

    def test_nothing_recorded_when_the_verifier_did_not_run(self) -> None:
        from core.run_quality import build_quality

        with (
            patch("core.authenticity.evaluate_authenticity") as auth,
            patch("core.engagement_predictor.predict_engaged_rate", return_value=None),
        ):
            auth.return_value.score = 80
            auth.return_value.gate_score = 100
            auth.return_value.verdict = "ok"
            auth.return_value.semantic_overlap = 0.0
            auth.return_value.recurrence = {}
            quality = build_quality(script="A script.", channel_id="tapin", features={})

        self.assertNotIn("gate_waived", quality)
        self.assertNotIn("gate_waived_count", quality)


class TestTheWaiverIsReadBack(unittest.TestCase):
    """Last wave's lesson: a field nothing reads is not a record."""

    def test_the_card_names_the_waived_claim(self) -> None:
        from core.video_grade import waiver_line

        line = waiver_line(
            {
                "gate_waived_count": 1,
                "gate_waived": [{"claim": _HEDGED_RUMOR, "type": "rumor", "hedged": True}],
                "hedge_density": 3.2,
            }
        )
        self.assertIn("rumor", line)
        self.assertIn("hedg", line.lower())

    def test_no_line_without_a_waiver(self) -> None:
        from core.video_grade import waiver_line

        self.assertEqual(waiver_line({}), "")
        self.assertEqual(waiver_line({"gate_waived_count": 0}), "")


if __name__ == "__main__":
    unittest.main()
