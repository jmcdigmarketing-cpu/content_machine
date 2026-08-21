"""Tests for the multi-provider LLM router (core/llm_router)."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from core import llm_router, quota_state

# Module-level isolation of the persisted store.
#
# Several classes here drive dead-model persistence and the daily-spend ledger.
# Un-isolated they wrote 24h dead-model records for the project's LIVE cheap and
# extract anchors into the operator's real data/quota_state.json - the exact
# poisoning tests/CLAUDE.md forbids. Bisected from a full-suite run that left an
# "openrouter/some:free" record - a pure test fixture - sitting in live state.
#
# Done at module scope so it also covers any class added later; the per-class
# QUOTA_STATE_FILE patches below still work (they just nest inside this one).
_MODULE_STATE_TMP: str | None = None
_MODULE_STATE_PATCH = None


def setUpModule() -> None:
    global _MODULE_STATE_TMP, _MODULE_STATE_PATCH
    _MODULE_STATE_TMP = tempfile.mkdtemp()
    _MODULE_STATE_PATCH = patch.object(
        quota_state, "QUOTA_STATE_FILE", os.path.join(_MODULE_STATE_TMP, "module_q.json")
    )
    _MODULE_STATE_PATCH.start()


def tearDownModule() -> None:
    if _MODULE_STATE_PATCH is not None:
        _MODULE_STATE_PATCH.stop()
    if _MODULE_STATE_TMP:
        shutil.rmtree(_MODULE_STATE_TMP, ignore_errors=True)


def _clear_router_env(env: dict[str, str]) -> dict[str, str]:
    """Return env overrides that blank every provider key + tier override."""
    base = {
        "OPENAI_API_KEY": "",
        "DEEPSEEK_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "GROQ_API_KEY": "",
        "OLLAMA_API_KEY": "",
        "DOUBAO_API_KEY": "",
        "ARK_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "DOUBAO_MODEL": "",
        "DOUBAO_MODEL_CHEAP": "",
        "DOUBAO_MODEL_EXTRACT": "",
        "DOUBAO_MODEL_PREMIUM": "",
        "OLLAMA_MODEL": "",
        "OLLAMA_MODEL_CHEAP": "",
        "OLLAMA_MODEL_EXTRACT": "",
        "OLLAMA_MODEL_PREMIUM": "",
        "OPENROUTER_MODEL": "",
        "OPENROUTER_MODEL_CHEAP": "",
        "OPENROUTER_MODEL_EXTRACT": "",
        "OPENROUTER_MODEL_PREMIUM": "",
        "GROQ_MODEL": "",
        "GROQ_MODEL_CHEAP": "",
        "GROQ_MODEL_EXTRACT": "",
        "GROQ_MODEL_PREMIUM": "",
        "DEEPSEEK_MODEL": "",
        "DEEPSEEK_MODEL_CHEAP": "",
        "LLM_CHEAP_PROVIDER": "",
        "LLM_EXTRACT_PROVIDER": "",
        "LLM_PREMIUM_PROVIDER": "",
        "LLM_CHEAP_MODEL": "",
        "LLM_EXTRACT_MODEL": "",
        "LLM_PREMIUM_MODEL": "",
        "LLM_DAILY_BUDGET_USD": "",
    }
    base.update(env)
    return base


class TestTierResolution(unittest.TestCase):
    def test_deepseek_anchors_extract_and_premium(self):
        with patch.dict("os.environ", _clear_router_env({"DEEPSEEK_API_KEY": "x"}), clear=False):
            self.assertEqual(llm_router.resolve_tier("extract"), ("deepseek", "deepseek-chat"))
            self.assertEqual(llm_router.resolve_tier("premium"), ("deepseek", "deepseek-chat"))
            # Cheap prefers Groq but falls back to DeepSeek when Groq absent.
            self.assertEqual(llm_router.resolve_tier("cheap"), ("deepseek", "deepseek-chat"))

    def test_openrouter_anchors_cheap_tier(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})
        with patch.dict("os.environ", env, clear=False):
            # OpenRouter wins cheap (free models); DeepSeek owns extract/premium.
            # Asserts the routing and that the model stays zero-cost — NOT a specific
            # slug. Pinning one is what hid the retirement of
            # meta-llama/llama-3.3-70b-instruct:free: OpenRouter rotates `:free` ids,
            # and a test naming one goes green while production 404s daily.
            provider, model = llm_router.resolve_tier("cheap")
            self.assertEqual(provider, "openrouter")
            self.assertTrue(model.endswith(":free"), f"cheap tier must stay free, got {model}")
            self.assertEqual(llm_router.resolve_tier("extract"), ("deepseek", "deepseek-chat"))
            self.assertEqual(llm_router.resolve_tier("premium"), ("deepseek", "deepseek-chat"))

    def test_openrouter_model_override(self):
        env = _clear_router_env(
            {"OPENROUTER_API_KEY": "x", "OPENROUTER_MODEL_CHEAP": "qwen/qwen-2.5-72b-instruct:free"}
        )
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(
                llm_router.resolve_tier("cheap"),
                ("openrouter", "qwen/qwen-2.5-72b-instruct:free"),
            )

    def test_groq_anchors_cheap_when_no_openrouter(self):
        env = _clear_router_env({"GROQ_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})
        with patch.dict("os.environ", env, clear=False):
            # Groq still beats DeepSeek for cheap when OpenRouter absent.
            self.assertEqual(llm_router.resolve_tier("cheap"), ("groq", "llama-3.1-8b-instant"))

    def test_legacy_openai_model_env_does_not_pin_tiers(self):
        # A bare OPENAI_MODEL (legacy single-model config) must NOT override the
        # per-tier openai defaults (cheap=mini, premium=4o).
        env = _clear_router_env({"OPENAI_API_KEY": "x", "OPENAI_MODEL": "gpt-4o"})
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(llm_router.resolve_tier("cheap"), ("openai", "gpt-4o-mini"))

    def test_ollama_available_only_with_model(self):
        # Local: no key needed, but unavailable until a model id is set AND that model
        # is actually pulled. The daemon reported ready with an empty model list, so a
        # configured-but-absent model cost a 404 probe every day.
        with patch.dict("os.environ", _clear_router_env({}), clear=False):
            self.assertFalse(llm_router._provider_available("ollama", "cheap"))
        env = _clear_router_env({"OLLAMA_MODEL": "llama3.1"})
        with (
            patch.dict("os.environ", env, clear=False),
            patch.object(llm_router, "ollama_installed_models", return_value=["llama3.1"]),
        ):
            self.assertTrue(llm_router._provider_available("ollama", "cheap"))
            self.assertEqual(llm_router.resolve_tier("cheap"), ("ollama", "llama3.1"))

    def test_ollama_unavailable_when_the_model_is_not_pulled(self):
        env = _clear_router_env({"OLLAMA_MODEL": "llama3.1"})
        with (
            patch.dict("os.environ", env, clear=False),
            patch.object(llm_router, "ollama_installed_models", return_value=[]),
        ):
            self.assertFalse(llm_router._provider_available("ollama", "cheap"))

    def test_doubao_wins_cheap_only_when_model_set(self):
        # Key without a model id -> Doubao not yet usable, falls through.
        with patch.dict("os.environ", _clear_router_env({"DOUBAO_API_KEY": "x"}), clear=False):
            provider, _ = llm_router.resolve_tier("cheap")
            self.assertNotEqual(provider, "doubao")
        # Key + model -> Doubao anchors cheap.
        env = _clear_router_env({"DOUBAO_API_KEY": "x", "DOUBAO_MODEL": "ep-123"})
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(llm_router.resolve_tier("cheap"), ("doubao", "ep-123"))

    def test_ark_api_key_alias(self):
        env = _clear_router_env({"ARK_API_KEY": "x", "DOUBAO_MODEL": "ep-9"})
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(llm_router.resolve_tier("cheap"), ("doubao", "ep-9"))

    def test_openai_only_behaves_like_old_code(self):
        with patch.dict("os.environ", _clear_router_env({"OPENAI_API_KEY": "x"}), clear=False):
            self.assertEqual(llm_router.resolve_tier("cheap"), ("openai", "gpt-4o-mini"))
            self.assertEqual(llm_router.resolve_tier("premium"), ("openai", "gpt-4o"))

    def test_explicit_override_wins(self):
        env = _clear_router_env(
            {
                "DEEPSEEK_API_KEY": "x",
                "LLM_PREMIUM_PROVIDER": "openai",
                "LLM_PREMIUM_MODEL": "gpt-4o",
            }
        )
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(llm_router.resolve_tier("premium"), ("openai", "gpt-4o"))

    def test_nothing_configured_falls_back_to_openai(self):
        with patch.dict("os.environ", _clear_router_env({}), clear=False):
            provider, model = llm_router.resolve_tier("premium")
            self.assertEqual(provider, "openai")
            self.assertTrue(model)

    def test_unknown_tier_treated_as_cheap(self):
        with patch.dict("os.environ", _clear_router_env({"DEEPSEEK_API_KEY": "x"}), clear=False):
            self.assertEqual(llm_router.resolve_tier("bogus"), llm_router.resolve_tier("cheap"))


class TestUsageLedger(unittest.TestCase):
    def setUp(self):
        llm_router.reset_usage()

    def test_record_and_read(self):
        llm_router._record_usage("deepseek", "deepseek-chat", "premium", 100, 50)
        usage = llm_router.get_usage()
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0]["provider"], "deepseek")
        self.assertEqual(usage[0]["input_tokens"], 100)
        self.assertEqual(usage[0]["output_tokens"], 50)

    def test_reset_clears(self):
        llm_router._record_usage("openai", "gpt-4o", "premium", 10, 10)
        llm_router.reset_usage()
        self.assertEqual(llm_router.get_usage(), [])


class TestComplete(unittest.TestCase):
    def setUp(self):
        llm_router.reset_usage()
        llm_router.reset_llm_breaker()

    def test_complete_routes_and_records_usage(self):
        captured = {}

        def fake_openai(provider, model, messages, **kwargs):
            captured["provider"] = provider
            captured["model"] = model
            captured["messages"] = messages
            return "hello", 12, 7

        env = _clear_router_env({"DEEPSEEK_API_KEY": "x"})
        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake_openai):
                out = llm_router.complete("hi there", tier="premium", system="be terse")
        self.assertEqual(out, "hello")
        self.assertEqual(captured["provider"], "deepseek")
        # System prompt is prepended as a system-role message.
        self.assertEqual(captured["messages"][0]["role"], "system")
        usage = llm_router.get_usage()
        self.assertEqual(usage[0]["input_tokens"], 12)
        self.assertEqual(usage[0]["output_tokens"], 7)
        self.assertEqual(usage[0]["stage"], "premium")  # default stage = tier

    def test_complete_records_pipeline_stage(self):
        def fake_openai(provider, model, messages, **kwargs):
            return "ok", 1, 1

        env = _clear_router_env({"DEEPSEEK_API_KEY": "x"})
        llm_router.reset_usage()
        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake_openai):
                llm_router.complete("hi", tier="cheap", stage="title")
        self.assertEqual(llm_router.get_usage()[0]["stage"], "title")

    def test_complete_json_parses(self):
        def fake_openai(provider, model, messages, **kwargs):
            return '{"facts": ["a", "b"]}', 1, 1

        env = _clear_router_env({"DEEPSEEK_API_KEY": "x"})
        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake_openai):
                data = llm_router.complete_json("go", tier="extract")
        self.assertEqual(data, {"facts": ["a", "b"]})

    def test_parse_json_payload_extracts_embedded_object(self):
        self.assertEqual(llm_router.parse_json_payload('noise {"x": 1} trailing'), {"x": 1})
        self.assertIsNone(llm_router.parse_json_payload("no json here"))


class _HTTPTestError(Exception):
    """Carries a status_code so _classify_llm_error can read it (like SDK errors)."""

    def __init__(self, status: int):
        super().__init__(f"http {status}")
        self.status_code = status


def _status_error(status: int) -> _HTTPTestError:
    return _HTTPTestError(status)


class TestFailover(unittest.TestCase):
    def setUp(self):
        llm_router.reset_usage()
        llm_router.reset_llm_breaker()

    def tearDown(self):
        llm_router.reset_llm_breaker()

    def test_rate_limit_fails_over_to_next_provider(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})
        calls = []

        def fake(provider, model, messages, **kwargs):
            calls.append(provider)
            if provider == "openrouter":
                raise _status_error(429)
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                out = llm_router.complete("hi", tier="cheap")
        self.assertEqual(out, "ok")
        self.assertEqual(calls, ["openrouter", "deepseek"])
        # Rate-limit is transient → openrouter is NOT disabled.
        self.assertFalse(llm_router._llm_disabled("openrouter"))

    def test_auth_error_disables_provider_for_session(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})

        def fake(provider, model, messages, **kwargs):
            if provider == "openrouter":
                raise _status_error(401)
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                out = llm_router.complete("hi", tier="cheap")
            self.assertEqual(out, "ok")
            self.assertTrue(llm_router._llm_disabled("openrouter"))
            # Subsequent resolution routes around the disabled provider.
            self.assertEqual(llm_router.resolve_tier("cheap")[0], "deepseek")

    def test_non_retryable_error_propagates(self):
        env = _clear_router_env({"DEEPSEEK_API_KEY": "x"})

        def fake(provider, model, messages, **kwargs):
            raise _status_error(400)  # bad request — don't mask with failover

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                with self.assertRaises(_HTTPTestError):
                    llm_router.complete("hi", tier="cheap")

    def test_all_candidates_fail_raises(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})

        def fake(provider, model, messages, **kwargs):
            raise _status_error(429)

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router.time, "sleep"):  # don't wait out retries in a test
                with patch.object(llm_router, "_openai_complete", side_effect=fake):
                    with self.assertRaises(llm_router.LLMUnavailableError):
                        llm_router.complete("hi", tier="cheap")

    def test_free_only_provider_retries_then_raises_unavailable(self):
        # Strict Free mode pins one free provider with no fallback; a persistent 429
        # must retry briefly then raise a catchable LLMUnavailableError, not crash.
        env = _clear_router_env(
            {
                "FREE_MODE_STRICT": "1",
                "OPENROUTER_API_KEY": "x",
                "LLM_CHEAP_PROVIDER": "openrouter",
                "LLM_CHEAP_MODEL": "meta-llama/llama-3.3-70b-instruct:free",
            }
        )
        calls = []

        def fake(provider, model, messages, **kwargs):
            calls.append(provider)
            raise _status_error(429)

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router.time, "sleep") as slept:
                with patch.object(llm_router, "_openai_complete", side_effect=fake):
                    with self.assertRaises(llm_router.LLMUnavailableError):
                        llm_router.complete("hi", tier="cheap")
        self.assertEqual(len(calls), 3)  # 1 initial + 2 bounded retries
        self.assertEqual(slept.call_count, 2)

    def test_free_only_provider_recovers_on_retry(self):
        env = _clear_router_env(
            {
                "FREE_MODE_STRICT": "1",
                "OPENROUTER_API_KEY": "x",
                "LLM_CHEAP_PROVIDER": "openrouter",
                "LLM_CHEAP_MODEL": "meta-llama/llama-3.3-70b-instruct:free",
            }
        )
        seq = [_status_error(429), None]  # rate-limited once, then recovers

        def fake(provider, model, messages, **kwargs):
            exc = seq.pop(0)
            if exc:
                raise exc
            return "recovered", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router.time, "sleep"):
                with patch.object(llm_router, "_openai_complete", side_effect=fake):
                    out = llm_router.complete("hi", tier="cheap")
        self.assertEqual(out, "recovered")

    def test_explicit_provider_does_not_failover(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})
        calls = []

        def fake(provider, model, messages, **kwargs):
            calls.append(provider)
            raise _status_error(429)

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                with self.assertRaises(_HTTPTestError):
                    llm_router.complete("hi", tier="cheap", provider="deepseek")
        self.assertEqual(calls, ["deepseek"])  # pinned — no failover


class _MessageError(Exception):
    """Provider error carrying both a status and a message (some report 400 for models)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status_code = status


class TestModelUnavailable(unittest.TestCase):
    """A retired model slug (404) must fail over, not kill the run.

    Regression: OpenRouter retired `…:free`, returning 404. That classified as "other",
    which skipped failover and raised a raw provider error mid-pipeline.
    """

    def setUp(self):
        llm_router.reset_usage()
        llm_router.reset_llm_breaker()

    def tearDown(self):
        llm_router.reset_llm_breaker()

    def test_404_classifies_as_model_unavailable(self):
        self.assertEqual(llm_router._classify_llm_error(_status_error(404)), "model_unavailable")

    def test_400_with_model_message_classifies_as_model_unavailable(self):
        exc = _MessageError(400, "The model `foo:free` is not found or unavailable")
        self.assertEqual(llm_router._classify_llm_error(exc), "model_unavailable")

    def test_plain_400_still_propagates_as_other(self):
        # A genuine bad request must NOT be masked by failover.
        self.assertEqual(llm_router._classify_llm_error(_status_error(400)), "other")

    def test_404_fails_over_to_next_provider(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})
        calls = []

        def fake(provider, model, messages, **kwargs):
            calls.append(provider)
            if provider == "openrouter":
                raise _status_error(404)
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                out = llm_router.complete("hi", tier="cheap")
        self.assertEqual(out, "ok")
        self.assertEqual(calls, ["openrouter", "deepseek"])

        usage = llm_router.get_usage()
        self.assertTrue(usage[0].get("escaped_free_first"))

    def test_404_does_not_disable_whole_provider(self):
        # Only the dead *model* is skipped — OpenRouter's other models/tiers still work.
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})

        def fake(provider, model, messages, **kwargs):
            if provider == "openrouter":
                raise _status_error(404)
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("hi", tier="cheap")
        self.assertFalse(llm_router._llm_disabled("openrouter"))

    def test_dead_model_skipped_on_later_calls(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})
        calls = []

        def fake(provider, model, messages, **kwargs):
            calls.append(provider)
            if provider == "openrouter":
                raise _status_error(404)
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("one", tier="cheap")
                calls.clear()
                out = llm_router.complete("two", tier="cheap")
        self.assertEqual(out, "ok")
        # Second call must not repeat the known-dead 404 round-trip.
        self.assertEqual(calls, ["deepseek"])

    def test_all_models_dead_raises_unavailable(self):
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "DEEPSEEK_API_KEY": "x"})

        def fake(provider, model, messages, **kwargs):
            raise _status_error(404)

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                with self.assertRaises(llm_router.LLMUnavailableError):
                    llm_router.complete("hi", tier="cheap")

    def test_reset_clears_dead_models(self):
        llm_router._mark_model_dead("openrouter", "some:free", "NotFoundError", "cheap")
        self.assertTrue(llm_router._model_is_dead("openrouter", "some:free"))
        llm_router.reset_llm_breaker()
        self.assertFalse(llm_router._model_is_dead("openrouter", "some:free"))


class TestEscapedFreeFirst(unittest.TestCase):
    def setUp(self):
        llm_router.reset_usage()
        llm_router.reset_llm_breaker()

    def tearDown(self):
        llm_router.reset_llm_breaker()
        llm_router.reset_usage()

    def test_premium_first_hit_deepseek_is_not_escaped(self):
        env = _clear_router_env({"DEEPSEEK_API_KEY": "x"})

        def fake(provider, model, messages, **kwargs):
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("hi", tier="premium")
        usage = llm_router.get_usage()
        self.assertEqual(usage[0]["provider"], "deepseek")
        self.assertFalse(usage[0].get("escaped_free_first"))

    def test_pinned_provider_never_flags(self):
        env = _clear_router_env({"DEEPSEEK_API_KEY": "x", "OPENROUTER_API_KEY": "x"})

        def fake(provider, model, messages, **kwargs):
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("hi", provider="deepseek", model="deepseek-chat")
        self.assertFalse(llm_router.get_usage()[0].get("escaped_free_first"))


class TestDailyBudget(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._patch = patch.object(
            quota_state, "QUOTA_STATE_FILE", os.path.join(self.tmp, "q.json")
        )
        self._patch.start()
        quota_state.reset_all()
        llm_router.reset_usage()
        llm_router.reset_llm_breaker()
        llm_router.reset_llm_spend()

    def tearDown(self):
        llm_router.reset_llm_spend()
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_budget_does_not_track_spend(self):
        env = _clear_router_env({"OPENAI_API_KEY": "x"})  # no LLM_DAILY_BUDGET_USD

        def fake(provider, model, messages, **kwargs):
            return "ok", 1_000_000, 0

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("hi", tier="premium")
        # Budget unset → no spend tracked, no file write.
        self.assertEqual(float(quota_state.get_value(llm_router._today_spend_key(), 0.0)), 0.0)

    def test_spend_accumulates_when_budget_set(self):
        env = _clear_router_env({"OPENAI_API_KEY": "x", "LLM_DAILY_BUDGET_USD": "100"})

        def fake(provider, model, messages, **kwargs):
            return "ok", 1_000_000, 0  # gpt-4o @ $2.50/M input

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("hi", tier="premium")
        self.assertGreater(float(quota_state.get_value(llm_router._today_spend_key(), 0.0)), 0.0)

    def test_over_budget_downgrades_premium_to_cheap(self):
        # Pre-seed today's spend above the budget.
        quota_state.set_value(llm_router._today_spend_key(), 99.0, 3600)
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "LLM_DAILY_BUDGET_USD": "1"})
        captured = {}

        def fake(provider, model, messages, **kwargs):
            captured["model"] = model
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("hi", tier="premium")
        # Downgraded to the cheap chain → OpenRouter's free model, not the premium one.
        self.assertIn(":free", captured["model"])

    def test_under_budget_keeps_premium(self):
        quota_state.set_value(llm_router._today_spend_key(), 0.1, 3600)
        env = _clear_router_env({"OPENROUTER_API_KEY": "x", "LLM_DAILY_BUDGET_USD": "100"})
        captured = {}

        def fake(provider, model, messages, **kwargs):
            captured["model"] = model
            return "ok", 1, 1

        with patch.dict("os.environ", env, clear=False):
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                llm_router.complete("hi", tier="premium")
        # Under budget → premium routing kept (OpenRouter's premium default model).
        self.assertEqual(captured["model"], "deepseek/deepseek-chat")

    def test_reset_usage_clears_budget_warned(self):
        llm_router._budget_warned = True
        llm_router.reset_usage()
        self.assertFalse(llm_router._budget_warned)


if __name__ == "__main__":
    unittest.main()
