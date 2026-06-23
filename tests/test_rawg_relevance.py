"""RAWG result relevance filtering — kill fuzzy neighbors, keep the real game."""

import unittest
from unittest.mock import MagicMock, patch

from apis import rawg_api
from apis.rawg_api import _is_relevant, get_rawg_signal


class TestIsRelevant(unittest.TestCase):
    def test_exact_game_kept(self):
        topic = set(rawg_api._sig_tokens("Marvel Rivals update what needs fixing"))
        self.assertTrue(_is_relevant("Marvel Rivals", topic))

    def test_fuzzy_neighbor_dropped(self):
        # The run-#2 noise: RAWG ranked these above the real game.
        topic = set(rawg_api._sig_tokens("Marvel Rivals update what needs fixing"))
        self.assertFalse(_is_relevant("Need for Speed Rivals", topic))
        self.assertFalse(_is_relevant("Marvel's Avengers", topic))

    def test_acronym_match_survives(self):
        # Must NOT regress the GTA case that worked: GTA -> Grand Theft Auto.
        topic = set(rawg_api._sig_tokens("New GTA VI news, pre orders live soon"))
        self.assertTrue(_is_relevant("Grand Theft Auto VI", topic))

    def test_empty_name_not_relevant(self):
        self.assertFalse(_is_relevant("", {"marvel", "rivals"}))


class TestGetRawgSignalFiltering(unittest.TestCase):
    @patch("apis.rawg_api._rawg_key", return_value="k")
    @patch("apis.rawg_api.requests.get")
    def test_only_relevant_results_injected(self, mock_get, _key):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [
                    {"name": "Need for Speed Rivals"},
                    {"name": "Marvel Rivals"},
                    {"name": "Marvel's Avengers"},
                ]
            },
        )
        sig = get_rawg_signal("Marvel Rivals update")
        names = [g["name"] for g in sig["data"]]
        self.assertEqual(names, ["Marvel Rivals"])
        self.assertTrue(sig["active"])

    @patch("apis.rawg_api._rawg_key", return_value="k")
    @patch("apis.rawg_api.requests.get")
    def test_all_irrelevant_makes_signal_inactive(self, mock_get, _key):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"results": [{"name": "Need for Speed Rivals"}]},
        )
        sig = get_rawg_signal("Marvel Rivals update")
        self.assertFalse(sig["active"])
        self.assertEqual(sig["data"], [])


if __name__ == "__main__":
    unittest.main()
