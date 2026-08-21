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
            self.assertNotIn("web_search", skip)  # keyless DuckDuckGo backend -> not skipped
            self.assertEqual(os.environ["WEB_SEARCH_BACKEND"], "duckduckgo")

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

    def test_abort_if_blocked_raises_in_free(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_mode.apply_cost_mode("free", readiness=self._ready(tts_provider=None))
            with self.assertRaises(run_mode.CostModeBlocked):
                run_mode.abort_if_blocked(result)

    def test_abort_if_blocked_is_noop_in_standard(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_mode.apply_cost_mode("standard")
            run_mode.abort_if_blocked(result)  # must not raise

    def test_apply_and_guard_rejects_stale_ollama(self):
        ready = self._ready(llm_provider="ollama", llm_model="llama3.1:8b", llm_local=True)
        with (
            mock.patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1:8b"}, clear=True),
            mock.patch("core.llm_router.ollama_installed_models", return_value=[]),
        ):
            with self.assertRaises(run_mode.CostModeBlocked):
                run_mode.apply_and_guard("free", readiness=ready)

    def test_guard_before_discovery_is_noop_without_strict(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(run_mode.guard_before_discovery(), [])

    def test_guard_before_discovery_raises_in_free_strict(self):
        env = {"FREE_MODE_STRICT": "1", "TTS_PROVIDER": "elevenlabs"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(run_mode.CostModeBlocked):
                run_mode.guard_before_discovery()

    def test_qwen_ready_needs_module_and_voice(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav = f.name
        try:
            with (
                mock.patch.object(run_mode, "_module_available", lambda m: m == "qwen_tts"),
                mock.patch.dict(os.environ, {"QWEN_VOICE": wav}, clear=True),
            ):
                self.assertEqual(run_mode._local_tts_available(), "qwen")
            with (
                mock.patch.object(run_mode, "_module_available", lambda m: m == "qwen_tts"),
                mock.patch.dict(os.environ, {"QWEN_VOICE": "Vivian"}, clear=True),
            ):
                self.assertEqual(run_mode._local_tts_available(), "qwen")
            with (
                mock.patch.object(run_mode, "_module_available", lambda m: m == "qwen_tts"),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                self.assertIsNone(run_mode._local_tts_available())
            with (
                mock.patch.object(run_mode, "_module_available", lambda m: m == "qwen_tts"),
                mock.patch.dict(os.environ, {"QWEN_VOICE": "C:\\missing\\clone.wav"}, clear=True),
            ):
                self.assertIsNone(run_mode._local_tts_available())
        finally:
            os.unlink(wav)

    def test_qwen_does_not_outrank_piper(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            onnx = f.name
        try:
            with (
                mock.patch.object(
                    run_mode, "_module_available", lambda m: m in ("piper", "qwen_tts")
                ),
                mock.patch.dict(
                    os.environ, {"PIPER_VOICE": onnx, "QWEN_VOICE": "Vivian"}, clear=True
                ),
            ):
                self.assertEqual(run_mode._local_tts_available(), "piper")
        finally:
            os.unlink(onnx)


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

    def test_free_llm_is_local_first(self):
        # Ollama reachable -> preferred even when an OpenRouter key is also present.
        with mock.patch.dict(
            os.environ, {"OLLAMA_MODEL": "llama3.1", "OPENROUTER_API_KEY": "sk-or-x"}, clear=True
        ):
            with mock.patch.object(run_mode, "_ollama_ready", return_value=(True, "llama3.1")):
                self.assertEqual(run_mode._free_llm(), ("ollama", "llama3.1", ""))
        # Ollama down -> fall back to the (rate-limited) OpenRouter :free cloud tier.
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-x"}, clear=True):
            with mock.patch.object(run_mode, "_ollama_ready", return_value=(False, "")):
                provider, model, note = run_mode._free_llm()
                self.assertEqual(provider, "openrouter")
                self.assertTrue(model.endswith(":free"))
                self.assertEqual(note, "")
        # Neither -> none, with a reason the readiness line can show.
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(run_mode, "_ollama_ready", return_value=(False, "")):
                provider, model, note = run_mode._free_llm()
                self.assertIsNone(provider)
                self.assertEqual(model, "")
                self.assertIn("Ollama", note)

    def test_free_llm_does_not_claim_a_dead_openrouter_model(self):
        # Regression: readiness advertised "llm=openrouter OK" purely because the key was
        # set, while that free slug was 404-ing. A known-dead model must not read as OK.
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-x"}, clear=True):
            with (
                mock.patch.object(run_mode, "_ollama_ready", return_value=(False, "")),
                mock.patch.object(run_mode, "_model_known_dead", return_value=True),
            ):
                provider, _model, note = run_mode._free_llm()
        self.assertIsNone(provider)
        self.assertIn("OPENROUTER_MODEL_CHEAP", note)

    def test_ollama_ready_pings_the_server(self):
        from core import llm_router

        llm_router._ollama_probe_cache = None
        tags = mock.Mock(status_code=200)
        tags.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
        try:
            with mock.patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1"}, clear=True):
                with mock.patch.object(llm_router.requests, "get", return_value=tags) as g:
                    self.assertEqual(run_mode._ollama_ready(), (True, "llama3.1"))
                    g.assert_called_once()
                llm_router._ollama_probe_cache = None
                with mock.patch.object(
                    llm_router.requests, "get", side_effect=OSError("connection refused")
                ):
                    self.assertEqual(run_mode._ollama_ready(), (False, "llama3.1"))
            llm_router._ollama_probe_cache = None
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(llm_router.requests, "get") as g:
                    self.assertEqual(run_mode._ollama_ready(), (False, ""))
                    g.assert_not_called()
        finally:
            llm_router._ollama_probe_cache = None

    def test_readiness_llm_local_flag_and_line(self):
        with mock.patch.object(run_mode, "_free_llm", return_value=("ollama", "llama3.1", "")):
            with (
                mock.patch.object(run_mode, "_local_tts_available", return_value="piper"),
                mock.patch("apis.free_backends.reddit_available", return_value=False),
                mock.patch("apis.free_backends.youtube_available", return_value=True),
            ):
                r = run_mode.free_backend_readiness()
        self.assertTrue(r.llm_local)
        self.assertIn("local $0", run_mode.format_readiness_line(r))
        cloud = run_mode.Readiness(
            tts_provider="piper", llm_provider="openrouter", llm_model="x:free", llm_local=False
        )
        self.assertIn("throttled", run_mode.format_readiness_line(cloud))


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


class TestFreeDoctor(unittest.TestCase):
    def test_runs_clean_with_nothing_installed(self):
        import argparse

        from scripts import ops

        with (
            mock.patch.object(run_mode, "_ollama_ready", return_value=(False, "")),
            mock.patch.object(run_mode, "_local_tts_available", return_value=None),
            mock.patch("apis.free_backends.reddit_available", return_value=False),
            mock.patch("apis.free_backends.youtube_available", return_value=True),
            mock.patch.object(ops, "_ollama_server_probe", return_value=(False, 0)),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            rc = ops.cmd_free_doctor(argparse.Namespace())
        self.assertEqual(rc, 0)  # never raises, even with nothing installed


if __name__ == "__main__":
    unittest.main()
