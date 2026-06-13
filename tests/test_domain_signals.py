import unittest
from unittest.mock import patch

from apis.anime_api import get_anime_signal
from apis.coingecko_api import get_coingecko_signal
from apis.sec_edgar_api import get_sec_edgar_signal
from apis.signal_chain import chain_signal
from apis.signal_contract import make_signal
from apis.topic_scorer import get_weights, infer_domain
from apis.trendingnow_api import get_trendingnow_signal


class TestDomainInference(unittest.TestCase):
    def test_infer_anime(self):
        self.assertEqual(infer_domain("One Piece episode 1100 review"), "anime")

    def test_infer_finance(self):
        self.assertEqual(infer_domain("Apple earnings beat estimates 2026"), "finance")

    def test_infer_music(self):
        self.assertEqual(infer_domain("New Kendrick Lamar album review"), "music")

    def test_infer_popculture_not_marvel_rivals(self):
        self.assertEqual(infer_domain("Marvel movie trailer breakdown"), "popculture")
        self.assertEqual(infer_domain("Marvel Rivals meta tier list"), "gaming")

    def test_anime_weights(self):
        weights = get_weights("anime", "default")
        self.assertGreater(weights.get("anime", 0), 0.2)


class TestDomainSignals(unittest.TestCase):
    @patch("apis.coingecko_api.get_cached", return_value=None)
    @patch("apis.coingecko_api.set_cache")
    @patch("apis.coingecko_api.requests.get")
    def test_coingecko_search(self, mock_get, _set, _cache):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"coins": [{"name": "Bitcoin", "id": "bitcoin"}]}
        sig = get_coingecko_signal("Bitcoin price outlook")
        self.assertTrue(sig["active"])

    @patch("apis.anilist_api.get_cached", return_value=None)
    @patch("apis.anilist_api.set_cache")
    @patch("apis.anilist_api.requests.post")
    def test_anime_chain_anilist(self, mock_post, _set, _cache):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "data": {
                "Page": {
                    "media": [
                        {
                            "title": {"english": "Naruto"},
                            "popularity": 9000,
                            "trending": 5,
                        }
                    ]
                }
            }
        }
        sig = get_anime_signal("Naruto shippuden analysis")
        self.assertTrue(sig["active"])
        self.assertEqual((sig.get("data") or {}).get("provider"), "anilist")

    @patch("apis.trendingnow_api.get_cached", return_value=None)
    @patch("apis.trendingnow_api.set_cache")
    @patch("apis.trendingnow_api.requests.get")
    def test_trendingnow_feed(self, mock_get, _set, _cache):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "Hollow Knight Silksong"},
            {"name": "Elden Ring"},
        ]
        sig = get_trendingnow_signal("Hollow Knight Silksong hype")
        self.assertTrue(sig["connected"])

    @patch("apis.sec_edgar_api.get_cached", return_value=None)
    @patch("apis.sec_edgar_api.set_cache")
    @patch("apis.sec_edgar_api.requests.get")
    def test_sec_edgar_filings(self, mock_get, _set, _cache):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "form": "8-K",
                            "file_date": "2026-05-01",
                            "display_names": ["TESLA INC"],
                        }
                    }
                ]
            }
        }
        sig = get_sec_edgar_signal("Tesla production numbers")
        self.assertTrue(sig["active"])


if __name__ == "__main__":
    unittest.main()
