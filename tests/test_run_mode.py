"""Free ($0) cost mode — the env bundle, readiness probe, and the three strict
never-pay guards (TTS / LLM / Apify).

No network, no GPU: readiness is driven by patched module/env probes, and the
guards are exercised with the paid backends mocked so a leak would fail loudly.
Every test isolates os.environ so the toggle can't poison a later test.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from core import run_mode


class TestApplyCostMode(unittest.TestCase):
    def _ready(self, **kw):
        base = {
            "tts_provider": "piper",
            "llm_provider": "openrouter",
            "llm_model": "meta-llama/llama-3.3-70b-instruct:free",
            "reddit_free": True,
            "youtube_free": True,
        }
        base.update(kw)
        return run_mode.Readiness(**base)

    def test_standard_is_a_noop(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_mode.apply_cost_mode("standard")
            self.assertEqual(result.mode, run_mode.COST_MODE_STANDARD)
            self.assertNotIn("FREE_MODE_STRICT", os.environ)
            self.assertNotIn("SIGNAL_BACKEND", os.environ)

    def test_free_sets_the_full_bundle(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_mode.apply_cost_mode("free", readiness=self._ready())
            self.assertEqual(result.mode, run_mode.COST_MODE_FREE)
            self.assertEqual(os.environ["FREE_MODE_STRICT"], "1")
            self.assertEqual(os.environ["TTS_PROVIDER"], "piper")
            self.assertEqual(os.environ["SIGNAL_BACKEND"], "free")
            for tier in ("CHEAP", "EXTRACT", "PREMIUM"):
                self.assertEqual(os.environ[f"LLM_{tier}_PROVIDER"], "openrouter")
                self.assertTrue(os.environ[f"LLM_{tier}_MODEL"].endswith(":free"))
            self.assertTrue(result.can_render)
            self.assertEqual(result.blockers, [])

    def test_free_merges_existing_skip_without_clobbering(self):
        with mock.patch.dict(os.environ, {"CONTENT_SKIP_SIGNALS": "trends,tapology"}, clear=True):
            run_mode.apply_cost_mode("free", readiness=self._ready())
            skip = set(os.environ["CONTENT_SKIP_SIGNALS"].split(","))
            self.assertIn("trends", skip)  # preserved
            self.assertIn("tapology", skip)  # preserved
            self.assertIn("twitter", skip)  # added
            self.assertIn("tiktok_trends", skip)
            self.assertIn("web_search", skip)

    def test_missing_local_tts_blocks_and_never_sets_paid(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_mode.apply_cost_mode("free", readiness=self._ready(tts_provider=None))
            # Strict: no paid provider is set as a fallback.
            self.assertNotEqual(os.environ.get("TTS_PROVIDER"), "elevenlabs")
            self.assertNotIn("TTS_PROVIDER", os.environ)
            self.assertEqual(os.environ["FREE_MODE_STRICT"], "1")  # still armed
            self.assertTrue(any(b.startswith("voice:") for b in result.blockers))
            self.assertFalse(result.can_render)

    def test_missing_free_llm_blocks(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_mode.apply_cost_mode(
                "free", readiness=self._ready(llm_provider=None, llm_model="")
            )
            self.assertNotIn("LLM_PREMIUM_PROVIDER", os.environ)
            self.assertTrue(any(b.startswith("llm:") for b in result.blockers))
            self.assertFalse(result.can_render)


class TestReadiness(unittest.TestCase):
    def test_piper_ready_needs_module_and_voice_file(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            voice = f.name
        try:
            with (
                mock.patch.object(run_mode, "_module_available", lambda m: m == "piper"),
                mock.patch.dict(os.environ, {"PIPER_VOICE": voice}, clear=True),
            ):
                self.assertEqual(run_mode._local_tts_available(), "piper")
            # Module present but no voice model -> not ready.
            with (
                mock.patch.object(run_mode, "_module_available", lambda m: m == "piper"),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                self.assertIsNone(run_mode._local_tts_available())
        finally:
            os.unlink(voice)

    def test_free_llm_prefers_openrouter_then_ollama(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-x"}, clear=True):
            provider, model = run_mode._free_llm()
            self.assertEqual(provider, "openrouter")
            self.assertTrue(model.endswith(":free"))
        with mock.patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1"}, clear=True):
            self.assertEqual(run_mode._free_llm(), ("ollama", "llama3.1"))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(run_mode._free_llm(), (None, ""))


class TestSkipSignalsPerCall(unittest.TestCase):
    def test_skip_signals_reads_env_each_call(self):
        from apis import register_signals

        with mock.patch.dict(
            os.environ, {"CONTENT_SKIP_SIGNALS": "twitter,tiktok_trends"}, clear=True
        ):
            self.assertEqual(register_signals._skip_signals(), {"twitter", "tiktok_trends"})
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(register_signals._skip_signals(), set())


class TestTtsStrictGuard(unittest.TestCase):
    def test_strict_blocks_instead_of_paid_fallback(self):
        from core import tts

        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "a.mp3")
            with (
                mock.patch.dict(os.environ, {"FREE_MODE_STRICT": "1"}, clear=True),
                mock.patch.object(tts, "ElevenLabs") as eleven,
            ):
                with self.assertRaises(RuntimeError):
                    tts.generate_audio("hello world", out, channel_id="tapin")
                eleven.assert_not_called()  # never touched the paid client


class TestLlmStrictChain(unittest.TestCase):
    def setUp(self):
        from core import llm_router

        self.router = llm_router
        llm_router.reset_llm_breaker()

    def test_strict_keeps_free_openrouter(self):
        env = {
            "FREE_MODE_STRICT": "1",
            "OPENROUTER_API_KEY": "sk-or-x",
            "LLM_PREMIUM_PROVIDER": "openrouter",
            "LLM_PREMIUM_MODEL": "meta-llama/llama-3.3-70b-instruct:free",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            provider, model = self.router.resolve_tier("premium")
            self.assertEqual(provider, "openrouter")
            self.assertTrue(model.endswith(":free"))

    def test_strict_drops_paid_and_raises_when_none_free(self):
        env = {
            "FREE_MODE_STRICT": "1",
            "DEEPSEEK_API_KEY": "sk-deep",
            "OPENAI_API_KEY": "sk-openai",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                self.router.resolve_tier("premium")

    def test_no_strict_still_allows_paid_fallback(self):
        env = {"DEEPSEEK_API_KEY": "sk-deep"}
        with mock.patch.dict(os.environ, env, clear=True):
            provider, _ = self.router.resolve_tier("premium")
            self.assertEqual(provider, "deepseek")  # unchanged behavior


if __name__ == "__main__":
    unittest.main()
