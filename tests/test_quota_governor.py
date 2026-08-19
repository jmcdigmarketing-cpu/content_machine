"""Tests for core/quota_governor.py — persisted signal breaker records with
key-hash invalidation, plus the Apify/LLM facades and unified snapshot (O11).
State file always isolated."""

import os
import tempfile
import unittest
from unittest.mock import patch

from core import quota_governor as qg
from core import quota_state


class GovernorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_patch = patch.object(
            quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp.name, "q.json")
        )
        self._state_patch.start()

    def tearDown(self):
        self._state_patch.stop()
        self._tmp.cleanup()


class TestPersistRoundtrip(GovernorCase):
    def test_disable_then_read_back(self):
        qg.disable_signal("finnhub", "no_key: missing FINNHUB_API_KEY")
        out = qg.persisted_disabled_signals()
        self.assertEqual(out, {"finnhub": "no_key: missing FINNHUB_API_KEY"})

    def test_clear_signal(self):
        qg.disable_signal("finnhub", "no_key")
        qg.clear_signal("finnhub")
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_clear_all_signals(self):
        qg.disable_signal("finnhub", "no_key")
        qg.disable_signal("rawg", "quota_exceeded")
        qg.clear_all_signals()
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_ttl_expiry(self):
        qg.disable_signal("finnhub", "no_key", ttl_seconds=-1)
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_persist_disabled_via_env(self):
        with patch.dict("os.environ", {"SIGNAL_BREAKER_PERSIST": "false"}):
            qg.disable_signal("finnhub", "no_key")
            self.assertEqual(qg.persisted_disabled_signals(), {})
        # Nothing was written while off.
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_signal_scope_does_not_leak_into_apify_scope(self):
        qg.disable_signal("reddit", "quota_exceeded")
        exhausted, _ = quota_state.is_exhausted("apify", "main")
        self.assertFalse(exhausted)


class TestKeyHashInvalidation(GovernorCase):
    def test_stable_key_keeps_record(self):
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k1"}):
            qg.disable_signal("finnhub", "auth_error")
            self.assertIn("finnhub", qg.persisted_disabled_signals())
            self.assertIn("finnhub", qg.persisted_disabled_signals())  # still there

    def test_changed_key_clears_record(self):
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k1"}):
            qg.disable_signal("finnhub", "auth_error")
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k2"}):
            self.assertEqual(qg.persisted_disabled_signals(), {})
        # Cleared permanently, not just filtered.
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k1"}):
            self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_any_env_in_the_tuple_invalidates(self):
        creds = {
            "APIFY_CONTENT_MACHINE_KEY": "a",
            "REDDIT_CLIENT_ID": "b",
            "REDDIT_CLIENT_SECRET": "c",
        }
        with patch.dict("os.environ", creds):
            qg.disable_signal("reddit", "auth_error")
        with patch.dict("os.environ", {**creds, "REDDIT_CLIENT_SECRET": "rotated"}):
            self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_unlisted_signal_is_ttl_only(self):
        # No credential mapping -> record holds regardless of env churn.
        qg.disable_signal("wikipedia", "upstream_error")
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "irrelevant-change"}):
            self.assertIn("wikipedia", qg.persisted_disabled_signals())


class TestApifyFacade(GovernorCase):
    def test_exhausted_roundtrip(self):
        qg.apify_mark_exhausted("main", "Apify monthly credits exhausted (402)", ttl_seconds=3600)
        exhausted, reason = qg.apify_is_exhausted("main")
        self.assertTrue(exhausted)
        self.assertIn("402", reason)

    def test_not_exhausted_by_default(self):
        self.assertEqual(qg.apify_is_exhausted("main"), (False, ""))

    def test_expired_record_reads_not_exhausted(self):
        qg.apify_mark_exhausted("main", "r", ttl_seconds=-1)
        self.assertEqual(qg.apify_is_exhausted("main"), (False, ""))

    def test_clear(self):
        qg.apify_mark_exhausted("main", "r", ttl_seconds=3600)
        qg.apify_clear("main")
        self.assertEqual(qg.apify_is_exhausted("main"), (False, ""))

    def test_purposes_are_isolated(self):
        qg.apify_mark_exhausted("tiktok", "r", ttl_seconds=3600)
        self.assertFalse(qg.apify_is_exhausted("main")[0])
        self.assertTrue(qg.apify_is_exhausted("tiktok")[0])

    def test_usage_cache_roundtrip(self):
        self.assertIsNone(qg.apify_get_usage("main"))
        qg.apify_set_usage("main", 1.25, 5.0, ttl_seconds=3600)
        self.assertEqual(qg.apify_get_usage("main"), {"usage": 1.25, "limit": 5.0})

    def test_usage_cache_expires(self):
        qg.apify_set_usage("main", 1.0, 5.0, ttl_seconds=-1)
        self.assertIsNone(qg.apify_get_usage("main"))


class TestLlmFacade(GovernorCase):
    def test_spend_accumulates_and_resets(self):
        self.assertEqual(qg.llm_spend_today(), 0.0)
        qg.llm_add_spend(0.10)
        qg.llm_add_spend(0.05)
        self.assertAlmostEqual(qg.llm_spend_today(), 0.15)
        qg.llm_reset_spend()
        self.assertEqual(qg.llm_spend_today(), 0.0)

    def test_zero_or_negative_spend_ignored(self):
        qg.llm_add_spend(0.0)
        qg.llm_add_spend(-1.0)
        self.assertEqual(qg.llm_spend_today(), 0.0)

    def test_key_is_date_scoped(self):
        self.assertTrue(qg.llm_today_spend_key().startswith("llm_spend:"))


class TestSnapshot(GovernorCase):
    def test_empty_store_shape(self):
        # The YouTube scope (O12) reads apis/youtube_quota, which is a separate
        # per-day store the governor only *reports*. Stub it so this test asserts a
        # shape instead of whatever the operator's real quota file happens to hold
        # (tests/CLAUDE.md: never read or write the real data/ stores).
        with patch(
            "apis.youtube_quota.get_usage_summary",
            return_value={"used": 0, "limit": 10000, "remaining": 10000, "day": "2026-01-01"},
        ):
            snap = qg.snapshot()
        self.assertEqual(
            snap,
            {
                "apify": {"exhausted": False, "reason": "", "usage": None},
                "llm": {"spend_today": 0.0, "dead_models": {}},
                "signals": {"persisted": {}},
                "youtube": {
                    "used": 0,
                    "limit": 10000,
                    "remaining": 10000,
                    "pct": 0.0,
                    "day": "2026-01-01",
                },
            },
        )

    def test_populated_snapshot(self):
        qg.apify_mark_exhausted("main", "402", ttl_seconds=3600)
        qg.apify_set_usage("main", 2.0, 5.0, ttl_seconds=3600)
        qg.llm_add_spend(0.25)
        qg.disable_signal("finnhub", "no_key")
        snap = qg.snapshot()
        self.assertTrue(snap["apify"]["exhausted"])
        self.assertEqual(snap["apify"]["usage"], {"usage": 2.0, "limit": 5.0})
        self.assertAlmostEqual(snap["llm"]["spend_today"], 0.25)
        self.assertEqual(snap["signals"]["persisted"], {"finnhub": "no_key"})


class TestDeadModelPersistence(GovernorCase):
    """Cross-run dead-model records (O12).

    Live runs on 2026-08-14 re-probed the same two retired free slugs on every run
    because the router's dead-model set was session-only.
    """

    def test_roundtrip(self):
        qg.llm_mark_model_dead("openrouter", "meta-llama/llama-3.3-70b:free", "NotFoundError")
        out = qg.persisted_dead_models()
        self.assertEqual(out, {"openrouter/meta-llama/llama-3.3-70b:free": "NotFoundError"})

    def test_fingerprint_mismatch_clears_record(self):
        # Operator rotates the key or repoints the tier -> re-probe, don't stay pinned off.
        qg.llm_mark_model_dead("ollama", "llama3.1:8b", "NotFoundError", fingerprint="OLD")
        self.assertEqual(qg.persisted_dead_models({"ollama/llama3.1:8b": "NEW"}), {})
        self.assertEqual(qg.persisted_dead_models(), {})  # cleared, not just filtered

    def test_matching_fingerprint_is_kept(self):
        qg.llm_mark_model_dead("ollama", "llama3.1:8b", "NotFoundError", fingerprint="SAME")
        out = qg.persisted_dead_models({"ollama/llama3.1:8b": "SAME"})
        self.assertEqual(out, {"ollama/llama3.1:8b": "NotFoundError"})

    def test_clear_all(self):
        qg.llm_mark_model_dead("openrouter", "a:free", "NotFoundError")
        qg.llm_mark_model_dead("ollama", "b", "NotFoundError")
        qg.llm_clear_dead_models()
        self.assertEqual(qg.persisted_dead_models(), {})

    def test_persistence_switch_off(self):
        with patch.dict(os.environ, {"SIGNAL_BREAKER_PERSIST": "false"}, clear=False):
            qg.llm_mark_model_dead("openrouter", "a:free", "NotFoundError")
            self.assertEqual(qg.persisted_dead_models(), {})


class TestRouterDeadModelWiring(GovernorCase):
    """The router must survive a process boundary — the point of the change."""

    def setUp(self):
        super().setUp()
        from core import llm_router

        self.router = llm_router
        llm_router.reset_llm_breaker()

    def tearDown(self):
        self.router.reset_llm_breaker()
        super().tearDown()

    def test_dead_model_survives_a_new_process(self):
        self.router._mark_model_dead("openrouter", "dead:free", "NotFoundError", "cheap")
        # Simulate a fresh run: drop session state only, keep the persisted store.
        self.router._dead_models.clear()
        self.router._dead_models_loaded = False
        self.assertTrue(self.router._model_is_dead("openrouter", "dead:free"))

    def test_live_model_unaffected(self):
        self.router._mark_model_dead("openrouter", "dead:free", "NotFoundError", "cheap")
        self.router._dead_models.clear()
        self.router._dead_models_loaded = False
        self.assertFalse(self.router._model_is_dead("openrouter", "alive:free"))

    def test_reset_clears_the_persisted_layer(self):
        self.router._mark_model_dead("openrouter", "dead:free", "NotFoundError", "cheap")
        self.router.reset_llm_breaker()
        self.assertFalse(self.router._model_is_dead("openrouter", "dead:free"))
        self.assertEqual(qg.persisted_dead_models(), {})


if __name__ == "__main__":
    unittest.main()
