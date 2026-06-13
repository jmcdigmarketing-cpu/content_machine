import unittest
from unittest.mock import patch

from apis.balldontlie_api import gather_balldontlie_context


class TestBalldontlie(unittest.TestCase):
    def test_nba_player_lines(self):
        with (
            patch("apis.balldontlie_api.get_cached", return_value=None),
            patch("apis.balldontlie_api.set_cache"),
            patch("apis.balldontlie_api._API_KEY", "test-key"),
            patch("apis.balldontlie_api._get") as mock_get,
        ):
            mock_get.side_effect = [
                {"data": [{"id": 1, "first_name": "Nikola", "last_name": "Jokic"}]},
                {
                    "data": [
                        {
                            "pts": 29,
                            "reb": 12,
                            "ast": 8,
                            "game": {"date": "2026-05-01"},
                        }
                    ]
                },
            ]
            ctx = gather_balldontlie_context("Jokic MVP race NBA 2026")
            lines = ctx.get("lines") or []
            self.assertTrue(any("Jokic" in line for line in lines))
            self.assertTrue(any("PTS" in line for line in lines))

    @patch("apis.balldontlie_api._API_KEY", "")
    def test_no_key_returns_empty(self):
        ctx = gather_balldontlie_context("Knicks NBA finals")
        self.assertEqual(ctx.get("lines") or [], [])


if __name__ == "__main__":
    unittest.main()
