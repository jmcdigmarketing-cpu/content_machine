"""Tests for semantic trade validation (core/trade_validation.py)."""

import unittest
from unittest.mock import patch

from core.trade_validation import (
    display_trade_validation,
    extract_trade_claims,
    trade_validation_enabled,
    validate_trade_claims,
)


class TestExtractTradeClaims(unittest.TestCase):
    def test_player_traded_to_team(self):
        claims = extract_trade_claims("Giannis Antetokounmpo was traded to the Miami Heat today.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].player, "Giannis Antetokounmpo")
        self.assertEqual(claims[0].team, "Miami Heat")

    def test_team_acquired_player(self):
        claims = extract_trade_claims("The Celtics acquired Jimmy Butler in a blockbuster.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].player, "Jimmy Butler")
        self.assertEqual(claims[0].team, "Celtics")

    def test_multiple_claims_deduped(self):
        text = (
            "LeBron James was traded to the Lakers. "
            "LeBron James was traded to the Lakers again, sources say."
        )
        self.assertEqual(len(extract_trade_claims(text)), 1)

    def test_no_claims_in_plain_text(self):
        self.assertEqual(extract_trade_claims("The meta shifted after the patch."), [])

    def test_reportedly_and_filler_words(self):
        claims = extract_trade_claims("Kevin Durant is reportedly headed to the Spurs.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].team, "Spurs")


class TestValidateTradeClaims(unittest.TestCase):
    FACTS = (
        "Giannis Antetokounmpo traded to the Miami Heat for a package of picks (Jun 30)\n"
        "Jimmy Butler signed a 2-year extension with the Golden State Warriors\n"
        "The Lakers waived two bench players"
    )

    def test_confirmed_trade_passes(self):
        script = "Breaking: Giannis Antetokounmpo was traded to the Miami Heat."
        self.assertEqual(validate_trade_claims(script, self.FACTS), [])

    def test_fused_trade_is_flagged(self):
        # Butler IS in the facts (Warriors extension) — but never with the Celtics.
        script = "And Jimmy Butler was traded to the Celtics in a shock move."
        warnings = validate_trade_claims(script, self.FACTS)
        self.assertEqual(len(warnings), 1)
        self.assertIn("Jimmy Butler", warnings[0])
        self.assertIn("Celtics", warnings[0])

    def test_unknown_player_left_to_token_grounding(self):
        # Player absent from the corpus entirely → token grounding's job, no warning.
        script = "Nikola Jokic was traded to the Heat."
        self.assertEqual(validate_trade_claims(script, self.FACTS), [])

    def test_empty_facts_returns_nothing(self):
        script = "Giannis Antetokounmpo was traded to the Miami Heat."
        self.assertEqual(validate_trade_claims(script, ""), [])

    def test_partial_name_matches_fact_line(self):
        # Script says "Giannis"; the fact line has the full name — any-token match.
        script = "Giannis was traded to the Heat."
        self.assertEqual(validate_trade_claims(script, self.FACTS), [])


class TestEnableSwitch(unittest.TestCase):
    def test_disabled_by_default(self):
        # No env, no domain → off (the pre-domain default is preserved).
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("SEMANTIC_TRADE_VALIDATION", None)
            self.assertFalse(trade_validation_enabled())

    def test_enabled_via_env(self):
        with patch.dict("os.environ", {"SEMANTIC_TRADE_VALIDATION": "true"}):
            self.assertTrue(trade_validation_enabled())

    def test_default_on_for_sports_domains(self):
        # Env unset → auto-on for trade-bearing sports domains.
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("SEMANTIC_TRADE_VALIDATION", None)
            self.assertTrue(trade_validation_enabled("nba"))
            self.assertTrue(trade_validation_enabled("nfl"))

    def test_default_off_for_non_trade_domains(self):
        # Env unset → off everywhere trades don't occur (UFC excluded on purpose).
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("SEMANTIC_TRADE_VALIDATION", None)
            for domain in ("gaming", "finance", "ufc", None):
                self.assertFalse(trade_validation_enabled(domain))

    def test_explicit_off_overrides_sports_default(self):
        with patch.dict("os.environ", {"SEMANTIC_TRADE_VALIDATION": "false"}):
            self.assertFalse(trade_validation_enabled("nba"))

    def test_explicit_on_overrides_domain(self):
        with patch.dict("os.environ", {"SEMANTIC_TRADE_VALIDATION": "true"}):
            self.assertTrue(trade_validation_enabled(None))


class TestDomainGateWiring(unittest.TestCase):
    """The domain content_engine feeds the gate must come from key facts too.

    The flagship case is an operator pasting NBA trade facts on tapin (a gaming/UFC
    channel): topic + channel alone infer "gaming" and the check would stay off, so
    `generate_content_package` passes `key_facts=` through to `infer_domain`.
    """

    def test_pasted_nba_facts_enable_the_gate_on_a_gaming_channel(self):
        from apis.topic_scorer import infer_domain

        topic = "The biggest roster shakeup of the week"
        facts = ["Luka Doncic was traded to the Los Angeles Lakers, per ESPN."]

        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("SEMANTIC_TRADE_VALIDATION", None)
            # Without the facts, the gate stays off...
            bare = infer_domain(topic, channel_id="tapin")
            self.assertFalse(trade_validation_enabled(bare))
            # ...with them, the NBA domain wins and the check runs.
            with_facts = infer_domain(topic, channel_id="tapin", key_facts=facts)
            self.assertEqual(with_facts, "nba")
            self.assertTrue(trade_validation_enabled(with_facts))


class TestDisplay(unittest.TestCase):
    def test_no_warnings_prints_nothing(self):
        out = []
        self.assertFalse(display_trade_validation([], print_fn=out.append))
        self.assertEqual(out, [])

    def test_warnings_rendered(self):
        out = []
        needs_review = display_trade_validation(
            ["Jimmy Butler → Celtics — never on the same line"], print_fn=out.append
        )
        self.assertTrue(needs_review)
        self.assertTrue(any("Trade direction" in ln for ln in out))


if __name__ == "__main__":
    unittest.main()
