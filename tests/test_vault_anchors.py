"""#1027 — a UFC card is not an anchor for a fighter it does not name."""

from __future__ import annotations

import unittest

from core.channel_context import anchor_families
from core.vault.relevance import _anchor_alignment

_TOPIC = "Long-term outlook: Can Illia Topuria adapt before UFC's next title cycle?"


class VaultAnchorTests(unittest.TestCase):
    def test_teams_leagues_and_fighters_are_anchors(self) -> None:
        self.assertIn("chargers", anchor_families("How the 0-4 chargers can turn it around"))
        self.assertIn("nfl", anchor_families("NFL week 5 slate"))
        self.assertIn("topuria", anchor_families(_TOPIC))
        self.assertEqual(anchor_families("best phone chargers 2026"), set())

    def test_a_vegas_card_does_not_anchor_a_topuria_idea(self) -> None:
        vegas = _anchor_alignment(_TOPIC, "UFC Vegas 122 co-main went to a decision", "")
        self.assertEqual(vegas[0], 0.0)
        named = _anchor_alignment(_TOPIC, "Topuria's path runs through Gaethje or Makhachev", "")
        self.assertEqual(named[0], 1.0)
