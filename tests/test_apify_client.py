"""Regression tests for the Apify client status handling."""

import unittest
from unittest.mock import MagicMock, patch


def _resp(status_code, payload):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload
    r.text = str(payload)
    return r


class TestRunActorStatus(unittest.TestCase):
    def setUp(self):
        from apis.apify_client import reset_apify_state

        reset_apify_state()
        # Ensure a key is present so run_actor proceeds to the HTTP call.
        self._patches = [
            patch("apis.apify_client._key", return_value="apify_test_key"),
            patch("apis.apify_client.get_cached", return_value=None),
            patch("apis.apify_client.set_cache"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        from apis.apify_client import reset_apify_state

        for p in self._patches:
            p.stop()
        reset_apify_state()

    def test_accepts_201_with_items(self):
        # Apify run-sync-get-dataset-items returns 201 Created with the data.
        from apis.apify_client import run_actor

        items = [{"id": "1", "text": "hello"}]
        with patch("apis.apify_client.requests.post", return_value=_resp(201, items)):
            result = run_actor("user/actor", {"q": "x"})
        self.assertEqual(result, items)

    def test_accepts_200_with_items(self):
        from apis.apify_client import run_actor

        items = [{"id": "2"}]
        with patch("apis.apify_client.requests.post", return_value=_resp(200, items)):
            result = run_actor("user/actor", {"q": "x"})
        self.assertEqual(result, items)

    def test_rejects_400(self):
        from apis.apify_client import run_actor

        with patch(
            "apis.apify_client.requests.post",
            return_value=_resp(400, {"error": "invalid-input"}),
        ):
            result = run_actor("user/actor", {"q": "x"})
        self.assertIsNone(result)

    def test_rejects_402_out_of_credits(self):
        from apis.apify_client import run_actor

        with patch("apis.apify_client.requests.post", return_value=_resp(402, {})):
            result = run_actor("user/actor", {"q": "x"})
        self.assertIsNone(result)

    def test_402_trips_circuit_breaker(self):
        from apis.apify_client import apify_disabled, run_actor

        with patch("apis.apify_client.requests.post", return_value=_resp(402, {})):
            run_actor("user/actor", {"q": "x"})
        self.assertTrue(apify_disabled())

    def test_disabled_skips_http(self):
        from apis.apify_client import disable_apify, run_actor

        disable_apify("test")
        called = {"n": 0}

        def _post(*a, **k):
            called["n"] += 1
            return _resp(201, [])

        with patch("apis.apify_client.requests.post", side_effect=_post):
            result = run_actor("user/actor", {"q": "x"})
        self.assertIsNone(result)
        self.assertEqual(called["n"], 0)  # no HTTP call when disabled

    def test_passes_ttl_seconds_to_cache(self):
        # Regression: set_cache takes ttl_seconds, not ttl.
        from apis.apify_client import run_actor

        with (
            patch("apis.apify_client.requests.post", return_value=_resp(201, [{"a": 1}])),
            patch("apis.apify_client.set_cache") as mock_cache,
        ):
            run_actor("user/actor", {"q": "x"}, ttl=999)
        _, kwargs = mock_cache.call_args
        self.assertEqual(kwargs.get("ttl_seconds"), 999)

    def test_actor_id_uses_tilde_path(self):
        from apis.apify_client import run_actor

        captured = {}

        def _capture(url, **kwargs):
            captured["url"] = url
            return _resp(201, [])

        with patch("apis.apify_client.requests.post", side_effect=_capture):
            run_actor("trudax/reddit-scraper-lite", {"q": "x"})
        self.assertIn("trudax~reddit-scraper-lite", captured["url"])
        self.assertNotIn("trudax/reddit-scraper-lite", captured["url"])


if __name__ == "__main__":
    unittest.main()
