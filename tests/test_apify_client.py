"""Tests for the Apify HTTP client (run_actor) — status handling + caching."""

import unittest
from unittest.mock import MagicMock, patch

from apis import apify_client as ac


class TestRunActor(unittest.TestCase):
    @patch("apis.apify_client.set_cache")
    @patch("apis.apify_client.get_cached", return_value=None)
    @patch("apis.apify_client.requests.post")
    def test_201_returns_items_and_caches_with_ttl_seconds(self, mock_post, _get, mock_set):
        # Apify run-sync returns 201 (Created) with the dataset items.
        mock_post.return_value = MagicMock(status_code=201, json=lambda: [{"id": "1"}, {"id": "2"}])
        with patch.dict("os.environ", {"APIFY_CONTENT_MACHINE_KEY": "k"}, clear=False):
            items = ac.run_actor("user/actor", {"q": "x"}, ttl=123)
        self.assertEqual(items, [{"id": "1"}, {"id": "2"}])
        # Regression: must call set_cache with ttl_seconds (not ttl), or every
        # actor crashes after fetching and nothing caches.
        self.assertTrue(mock_set.called)
        _, kwargs = mock_set.call_args
        self.assertIn("ttl_seconds", kwargs)
        self.assertEqual(kwargs["ttl_seconds"], 123)

    @patch("apis.apify_client.get_cached", return_value=None)
    @patch("apis.apify_client.requests.post")
    def test_402_out_of_credits_returns_none(self, mock_post, _get):
        mock_post.return_value = MagicMock(status_code=402, text="no credits")
        with patch.dict("os.environ", {"APIFY_CONTENT_MACHINE_KEY": "k"}, clear=False):
            self.assertIsNone(ac.run_actor("user/actor", {}, ttl=10))

    def test_no_key_returns_none(self):
        with patch.dict(
            "os.environ", {"APIFY_CONTENT_MACHINE_KEY": "", "APIFY_BENABLE_BOT": ""}, clear=False
        ):
            self.assertIsNone(ac.run_actor("user/actor", {}))


if __name__ == "__main__":
    unittest.main()
