"""Tests for the multi-provider LLM router (core/llm_router)."""

import unittest
from unittest.mock import patch

from core import llm_router


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
            self.assertEqual(
                llm_router.resolve_tier("cheap"),
                ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
            )
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
        # Local: no key needed, but unavailable until a model id is set.
        with patch.dict("os.environ", _clear_router_env({}), clear=False):
            self.assertFalse(llm_router._provider_available("ollama", "cheap"))
        env = _clear_router_env({"OLLAMA_MODEL": "llama3.1"})
        with patch.dict("os.environ", env, clear=False):
            self.assertTrue(llm_router._provider_available("ollama", "cheap"))
            self.assertEqual(llm_router.resolve_tier("cheap"), ("ollama", "llama3.1"))

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
            with patch.object(llm_router, "_openai_complete", side_effect=fake):
                with self.assertRaises(_HTTPTestError):
                    llm_router.complete("hi", tier="cheap")

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


if __name__ == "__main__":
    unittest.main()
