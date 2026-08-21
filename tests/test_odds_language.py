"""Odds market voice (#126) + gambling-safe CTAs (#127)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.odds_language import apply_odds_language, soften_odds_certainty, strip_betting_ctas


class TestOddsMarketVoice(unittest.TestCase):
    def test_will_win_becomes_favored(self):
        script = "The odds have Topuria as the favorite. He will win this fight."
        with patch.dict(os.environ, {"ODDS_MARKET_VOICE": "true", "GAMBLING_SAFE": "false"}):
            out, notes = soften_odds_certainty(script, topic="UFC 319 odds")
        self.assertNotIn("will win", out.lower())
        self.assertIn("favored to win", out.lower())
        self.assertTrue(notes)

    def test_no_odds_context_leaves_will_alone(self):
        script = "This patch will win players back."
        with patch.dict(os.environ, {"ODDS_MARKET_VOICE": "true"}):
            out, notes = soften_odds_certainty(script, topic="GTA 6 leaks")
        self.assertEqual(out, script)
        self.assertEqual(notes, [])

    def test_gaming_favorite_will_win_is_not_odds_voice(self):
        script = "My favorite loadout will win you games this season."
        with patch.dict(os.environ, {"ODDS_MARKET_VOICE": "true"}):
            out, notes = soften_odds_certainty(script, topic="Marvel Rivals meta")
        self.assertEqual(out, script)
        self.assertEqual(notes, [])

    def test_env_off(self):
        script = "The odds say he will beat Pereira."
        with patch.dict(os.environ, {"ODDS_MARKET_VOICE": "false"}):
            out, notes = soften_odds_certainty(script, topic="odds")
        self.assertEqual(out, script)
        self.assertEqual(notes, [])


class TestGamblingSafe(unittest.TestCase):
    def test_strips_bet_now(self):
        script = "Pereira is the underdog. Bet now on the moneyline. Then watch."
        with patch.dict(os.environ, {"GAMBLING_SAFE": "true", "ODDS_MARKET_VOICE": "false"}):
            out, n = strip_betting_ctas(script)
        self.assertGreater(n, 0)
        self.assertNotIn("bet now", out.lower())
        self.assertIn("underdog", out.lower())

    def test_lock_it_in_gaming_copy_is_not_a_cta(self):
        script = "Lock it in before the patch. Then use code in the console."
        with patch.dict(os.environ, {"GAMBLING_SAFE": "true"}):
            out, n = strip_betting_ctas(script)
        self.assertEqual(n, 0)
        self.assertEqual(out, script)

    def test_apply_does_both(self):
        script = "Odds list him as the favorite. He will win. Bet now."
        with patch.dict(os.environ, {"GAMBLING_SAFE": "true", "ODDS_MARKET_VOICE": "true"}):
            out, notes = apply_odds_language(script, topic="UFC odds")
        self.assertNotIn("bet now", out.lower())
        self.assertNotIn("will win", out.lower())
        self.assertTrue(notes)


if __name__ == "__main__":
    unittest.main()
