"""Candidate 321: the generated title is fact-checked like everything else.

`generate_title` runs *after* grounding and the claim verifier have passed on the
script, and is deliberately fail-open — so nothing ever read the string it returned.
Live-run 71 shipped:

    GTA 6 Leak Forces Rockstar to Subpoena Microsoft and Discord Records

when the operator's own key fact said the subpoenas came from Rockstar's *parent*,
Take-Two. The report card still printed grounding 100/100 and graded the run A.

The first test below is the reason this lint uses the claim verifier rather than
token grounding: every proper noun in that title IS in the facts, so the entity
gate passes it clean. The error is relational, not lexical.
"""

import unittest
from unittest.mock import patch

from core.fact_grounding import find_ungrounded_entities
from core.youtube_meta import lint_title_grounding, title_grounding_mode

# The real run-71 strings.
RUN71_TITLE = "GTA 6 Leak Forces Rockstar to Subpoena Microsoft and Discord Records"
RUN71_FACT = (
    "To find the Grand Theft Auto 6 leaker, the parent company of Rockstar Games has "
    "resorted to filing subpoenas in a US court to force Microsoft and Discord to hand "
    "over their records."
)


RUN71_CORPUS = (
    RUN71_FACT + "\n"
    "Take-Two Interactive filed subpoenas against Microsoft and Discord in the "
    "Southern District of New York.\n"
    "Rockstar Games Reportedly Remains In The Dark About Who Is Leaking GTA 6.\n"
)

# Same sentence, only the actor differs. One is what the facts say; one is run 71's error.
TITLE_WRONG_ACTOR = "Rockstar Subpoenas Microsoft and Discord Over the GTA 6 Leak"
TITLE_RIGHT_ACTOR = "Take-Two Subpoenas Microsoft and Discord Over the GTA 6 Leak"


class TestWhyTokenGroundingCannotCatchIt(unittest.TestCase):
    """Documents the gap this candidate exists to close.

    Measured, not assumed: token grounding gives the *same* verdict for the correct
    and the incorrect actor, so it cannot be the check that catches this class of
    error no matter how it is tuned.
    """

    def test_entity_grounding_cannot_tell_the_two_actors_apart(self):
        wrong = find_ungrounded_entities(TITLE_WRONG_ACTOR, RUN71_CORPUS)
        right = find_ungrounded_entities(TITLE_RIGHT_ACTOR, RUN71_CORPUS)
        self.assertEqual(wrong, right)
        self.assertEqual(wrong, [], "both ground cleanly — every proper noun is in the facts")


def _verification(claims):
    """Build a ClaimVerification the way verify_claims would return one."""
    from core.claim_verifier import ClaimVerification, VerifiedClaim

    v = ClaimVerification()
    for text, supported in claims:
        v.claims.append(VerifiedClaim(claim=text, supported=supported))
    return v


class TestLintFlagsTheRelationalError(unittest.TestCase):
    def test_unsupported_title_claim_warns(self):
        fake = _verification([("Rockstar filed subpoenas against Microsoft and Discord", False)])
        with patch("core.claim_verifier.verify_claims", return_value=fake):
            warnings = lint_title_grounding(
                RUN71_TITLE, facts_text=RUN71_FACT, priority_facts=[RUN71_FACT]
            )
        self.assertEqual(len(warnings), 1)
        self.assertIn("not backed", warnings[0])
        self.assertIn("Rockstar", warnings[0])

    def test_supported_title_is_silent(self):
        fake = _verification([("Take-Two subpoenaed Microsoft and Discord", True)])
        with patch("core.claim_verifier.verify_claims", return_value=fake):
            self.assertEqual(
                lint_title_grounding("Take-Two Subpoenas Microsoft", facts_text=RUN71_FACT), []
            )

    def test_only_the_unsupported_claims_are_reported(self):
        fake = _verification([("backed", True), ("invented", False), ("also backed", True)])
        with patch("core.claim_verifier.verify_claims", return_value=fake):
            warnings = lint_title_grounding("t", facts_text="f")
        self.assertEqual(len(warnings), 1)
        self.assertIn("invented", warnings[0])


class TestFailOpen(unittest.TestCase):
    """A missing verdict is 'no opinion', never 'ok' — and never an exception."""

    def test_none_verdict_is_silent(self):
        with patch("core.claim_verifier.verify_claims", return_value=None):
            self.assertEqual(lint_title_grounding(RUN71_TITLE, facts_text=RUN71_FACT), [])

    def test_verifier_raising_does_not_propagate(self):
        with patch("core.claim_verifier.verify_claims", side_effect=RuntimeError("router down")):
            self.assertEqual(lint_title_grounding(RUN71_TITLE, facts_text=RUN71_FACT), [])

    def test_empty_title_makes_no_llm_call(self):
        with patch("core.claim_verifier.verify_claims") as spy:
            self.assertEqual(lint_title_grounding("   ", facts_text=RUN71_FACT), [])
        spy.assert_not_called()


class TestFlag(unittest.TestCase):
    def test_default_is_warn(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("TITLE_GROUNDING", None)
            self.assertEqual(title_grounding_mode(), "warn")

    def test_off_skips_the_call_entirely(self):
        with patch.dict("os.environ", {"TITLE_GROUNDING": "off"}):
            with patch("core.claim_verifier.verify_claims") as spy:
                self.assertEqual(lint_title_grounding(RUN71_TITLE, facts_text=RUN71_FACT), [])
            spy.assert_not_called()

    def test_unknown_value_falls_back_to_warn(self):
        with patch.dict("os.environ", {"TITLE_GROUNDING": "banana"}):
            self.assertEqual(title_grounding_mode(), "warn")


class TestReportCardSurface(unittest.TestCase):
    def test_warnings_render_and_request_review(self):
        from core.ui import display_fact_engine_report

        lines = []
        needs_review = display_fact_engine_report(
            {"title_warnings": ["title claim not backed by the facts: Rockstar filed them"]},
            print_fn=lines.append,
        )
        text = "\n".join(lines)
        self.assertTrue(needs_review)
        self.assertIn("Title check", text)
        self.assertIn("Rockstar", text)

    def test_no_warnings_prints_nothing(self):
        from core.ui import display_fact_engine_report

        lines = []
        needs_review = display_fact_engine_report({"title_warnings": []}, print_fn=lines.append)
        self.assertFalse(needs_review)
        self.assertNotIn("Title check", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
