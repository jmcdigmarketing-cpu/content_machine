"""Regression tests for the Apify client status handling."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import quota_state


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
        # Isolate cross-run quota state to a temp file so the 402/breaker tests
        # don't write (or read) the real data/quota_state.json.
        self._tmp = tempfile.mkdtemp()
        # Ensure a key is present so run_actor proceeds to the HTTP call.
        self._patches = [
            patch("apis.apify_client._key", return_value="apify_test_key"),
            patch("apis.apify_client.get_cached", return_value=None),
            patch("apis.apify_client.set_cache"),
            patch.object(quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp, "q.json")),
        ]
        for p in self._patches:
            p.start()
        quota_state.reset_all()

    def tearDown(self):
        from apis.apify_client import reset_apify_state

        quota_state.reset_all()
        for p in self._patches:
            p.stop()
        reset_apify_state()
        shutil.rmtree(self._tmp, ignore_errors=True)

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

    def test_403_message_distinguishes_auth_from_credits(self):
        from apis.apify_client import _apify_failure_reason, apify_disabled, run_actor

        self.assertIn("unauthorized", _apify_failure_reason(403).lower())
        self.assertIn("credits exhausted", _apify_failure_reason(402).lower())
        with patch("apis.apify_client.requests.post", return_value=_resp(403, {})):
            run_actor("user/actor", {"q": "x"})
        from apis.apify_client import apify_status

        self.assertIn("unauthorized", apify_status().lower())
        self.assertTrue(apify_disabled())

    def test_403_uses_shorter_auth_ttl(self):
        from apis.apify_client import _persist_ttl_for_status

        self.assertLess(_persist_ttl_for_status(403), _persist_ttl_for_status(402))

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


class TestActorFailureMemory(unittest.TestCase):
    """A broken actor must not be re-run (and re-billed) on every run.

    The non-2xx branch used to return without calling `_note_failure()` and without
    caching, unlike the timeout/exception branches. The reddit actor failed on 100% of
    the 2026-08-14 live runs and started a fresh billable Apify run each time.
    Needs a REAL cache (the class above stubs get_cached/set_cache).
    """

    def setUp(self):
        from apis import cache_manager
        from apis.apify_client import reset_apify_state

        reset_apify_state()
        self._tmp = tempfile.mkdtemp()
        self._patches = [
            patch("apis.apify_client._key", return_value="apify_test_key"),
            patch.object(cache_manager, "_cache_path", lambda: os.path.join(self._tmp, "c.json")),
            patch.object(quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp, "q.json")),
        ]
        for p in self._patches:
            p.start()
        quota_state.reset_all()

    def tearDown(self):
        from apis.apify_client import reset_apify_state

        quota_state.reset_all()
        for p in self._patches:
            p.stop()
        reset_apify_state()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _count_posts(self, status, runs=3):
        from apis.apify_client import run_actor

        calls = {"n": 0}

        def _post(*a, **k):
            calls["n"] += 1
            return _resp(status, {"error": {"type": "run-failed"}})

        with patch("apis.apify_client.requests.post", side_effect=_post):
            for _ in range(runs):
                self.assertIsNone(run_actor("user/broken", {"q": "x"}))
        return calls["n"]

    def test_400_is_remembered_so_the_actor_is_not_re_billed(self):
        self.assertEqual(self._count_posts(400), 1)

    def test_404_is_remembered(self):
        self.assertEqual(self._count_posts(404), 1)

    def test_5xx_stays_retryable(self):
        # Transient: never suppressed, so a working actor recovers next run. (Two
        # attempts, not three — 5xx counts toward the account-wide breaker, which
        # trips at _MAX_FAILS=2 and short-circuits the third.)
        self.assertEqual(self._count_posts(503, runs=3), 2)

    def test_5xx_counts_toward_the_account_breaker(self):
        from apis import apify_client

        self._count_posts(503, runs=1)
        self.assertGreater(apify_client._state["fails"], 0)

    def test_bad_input_does_not_trip_the_account_breaker(self):
        # One actor with bad input must NOT disable twitter/tiktok/youtube_competitors.
        from apis import apify_client

        self._count_posts(400, runs=1)
        self.assertEqual(apify_client._state["fails"], 0)
        self.assertFalse(apify_client._state["disabled"])

    def test_suppression_is_per_input(self):
        # A different input is a different actor call — it must still be attempted.
        from apis.apify_client import run_actor

        calls = {"n": 0}

        def _post(*a, **k):
            calls["n"] += 1
            return _resp(400, {"error": "bad"})

        with patch("apis.apify_client.requests.post", side_effect=_post):
            run_actor("user/broken", {"q": "one"})
            run_actor("user/broken", {"q": "two"})
        self.assertEqual(calls["n"], 2)

    def test_ttl_zero_disables_suppression(self):
        with patch.dict(os.environ, {"APIFY_ACTOR_FAIL_TTL_SECONDS": "0"}, clear=False):
            self.assertEqual(self._count_posts(400), 3)


class TestNoResultsSentinel(unittest.TestCase):
    """An actor that bills a run and answers "I found nothing" is broken, not quiet.

    `apidojo/tweet-scraper` returns 10 x {"noResults": true} instead of tweets. Because
    the signal only checked `if not items`, that read as a successful-but-empty search:
    `twitter` reported `inactive` on 19/19 traces across five weeks while costing ~32s
    and Apify credits every run, and nothing ever flagged it.
    """

    def test_detects_the_tweet_scraper_sentinel(self):
        from apis.apify_client import is_no_results

        self.assertTrue(is_no_results([{"noResults": True}] * 10))

    def test_detects_single_sentinel(self):
        from apis.apify_client import is_no_results

        self.assertTrue(is_no_results([{"noResults": True}]))

    def test_real_data_is_not_a_sentinel(self):
        from apis.apify_client import is_no_results

        self.assertFalse(is_no_results([{"text": "a real tweet", "likeCount": 5}]))

    def test_mixed_results_are_not_a_sentinel(self):
        # One real row means the actor worked; don't discard the run.
        from apis.apify_client import is_no_results

        self.assertFalse(is_no_results([{"noResults": True}, {"text": "real"}]))

    def test_empty_and_non_list_are_not_sentinels(self):
        # A genuinely empty dataset is "no match", which is different from "broken".
        from apis.apify_client import is_no_results

        self.assertFalse(is_no_results([]))
        self.assertFalse(is_no_results(None))
        self.assertFalse(is_no_results({"noResults": True}))

    def test_non_dict_rows_are_not_sentinels(self):
        from apis.apify_client import is_no_results

        self.assertFalse(is_no_results(["a string"]))


class TestTwitterSignalRetired(unittest.TestCase):
    def test_sentinel_reports_unavailable_not_inactive(self):
        from apis.signal_contract import STATUS_UNAVAILABLE
        from apis.twitter_signal import get_twitter_signal

        with (
            patch.dict(os.environ, {"APIFY_CONTENT_MACHINE_KEY": "k"}, clear=False),
            patch("apis.twitter_signal.run_actor", return_value=[{"noResults": True}] * 10),
            patch("apis.apify_client.apify_disabled", return_value=False),
        ):
            sig = get_twitter_signal("Marvel Rivals season 9")
        self.assertEqual(sig["status"], STATUS_UNAVAILABLE)
        self.assertFalse(sig["connected"])

    def test_real_tweets_still_work_if_re_enabled(self):
        from apis.signal_contract import STATUS_OK
        from apis.twitter_signal import get_twitter_signal

        tweets = [{"text": "Marvel Rivals season 9 is live", "likeCount": 5000}]
        with (
            patch.dict(os.environ, {"APIFY_CONTENT_MACHINE_KEY": "k"}, clear=False),
            patch("apis.twitter_signal.run_actor", return_value=tweets),
            patch("apis.apify_client.apify_disabled", return_value=False),
        ):
            sig = get_twitter_signal("Marvel Rivals season 9")
        self.assertEqual(sig["status"], STATUS_OK)

    def test_catalog_marks_twitter_disabled(self):
        from apis.register_signals import _catalog_disabled_signals

        self.assertIn("twitter", _catalog_disabled_signals())

    def test_disabled_signal_is_not_scheduled(self):
        # The real payoff: no actor call, and twitter no longer sets the wall-clock
        # floor for discovery (it was the slowest signal at ~32s).
        from apis.register_signals import _active_signal_sources

        names = dict(_active_signal_sources("Marvel Rivals season 9", "tapin"))
        self.assertNotIn("twitter", names)


if __name__ == "__main__":
    unittest.main()
