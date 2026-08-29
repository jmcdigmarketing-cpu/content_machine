"""Tests for per-run cost estimation (v0)."""

import unittest
from unittest.mock import patch

from core.cost_meter import (
    escaped_free_first,
    estimate_run_cost,
    format_cost_line,
    format_standard_billed_line,
    llm_cost_by_provider,
    llm_cost_by_stage,
    llm_cost_from_usage,
    merge_render_cost,
    standard_would_have_billed,
    thumbnail_cost,
)


class TestCostMeter(unittest.TestCase):
    def test_breakdown_keys_and_total(self):
        cost = estimate_run_cost(script="word " * 150, signals={}, rendered=False)
        for key in ("llm", "tts", "apify", "web_search", "render", "total"):
            self.assertIn(key, cost)
        self.assertAlmostEqual(
            cost["total"],
            cost["llm"] + cost["tts"] + cost["apify"] + cost["web_search"] + cost["render"],
            places=3,
        )

    def test_tts_only_when_rendered(self):
        script = "word " * 200
        unrendered = estimate_run_cost(script=script, rendered=False)
        rendered = estimate_run_cost(script=script, rendered=True)
        self.assertEqual(unrendered["tts"], 0.0)
        self.assertGreater(rendered["tts"], 0.0)

    def test_local_tts_provider_is_zero_cost(self):
        # Pillar 6: a local voice (Kokoro/XTTS/Piper) has no marginal TTS cost.
        script = "word " * 200
        for provider in ("kokoro", "xtts", "piper", "qwen", "edge"):
            with patch.dict("os.environ", {"TTS_PROVIDER": provider}, clear=False):
                cost = estimate_run_cost(script=script, rendered=True)
            self.assertEqual(cost["tts"], 0.0, provider)
        # Default (ElevenLabs) stays billed.
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            self.assertGreater(estimate_run_cost(script=script, rendered=True)["tts"], 0.0)

    def test_apify_and_web_search_counted(self):
        signals = {
            "reddit": {"active": True},
            "twitter": {"active": True},
            "tiktok_trends": {"active": False},
            "web_search": {"active": True},
        }
        cost = estimate_run_cost(script="hi", signals=signals)
        self.assertGreater(cost["apify"], 0.0)
        self.assertGreater(cost["web_search"], 0.0)

    def test_rates_overridable_via_env(self):
        with patch.dict("os.environ", {"COST_LLM_PER_1K_TOKENS": "1.0"}, clear=False):
            cost = estimate_run_cost(script="word " * 1000)
        self.assertGreater(cost["llm"], 5.0)


class TestLLMCostFromUsage(unittest.TestCase):
    def test_empty_ledger_is_zero(self):
        self.assertEqual(llm_cost_from_usage(None), 0.0)
        self.assertEqual(llm_cost_from_usage([]), 0.0)

    def test_prices_by_model_prefix(self):
        # 1M input + 1M output on deepseek-chat = 0.27 + 1.10
        calls = [{"model": "deepseek-chat", "input_tokens": 1_000_000, "output_tokens": 1_000_000}]
        self.assertAlmostEqual(llm_cost_from_usage(calls), 1.37, places=4)

    def test_doubao_far_cheaper_than_gpt4o(self):
        doubao = [{"model": "ep-x doubao-lite", "input_tokens": 1_000_000, "output_tokens": 0}]
        gpt = [{"model": "gpt-4o", "input_tokens": 1_000_000, "output_tokens": 0}]
        self.assertLess(llm_cost_from_usage(doubao), llm_cost_from_usage(gpt))

    def test_unknown_model_uses_default(self):
        calls = [{"model": "mystery-llm", "input_tokens": 1_000_000, "output_tokens": 0}]
        self.assertGreater(llm_cost_from_usage(calls), 0.0)

    def test_local_ollama_is_free(self):
        # Local provider has no marginal cost regardless of model name.
        calls = [
            {
                "provider": "ollama",
                "model": "llama3.1",
                "input_tokens": 5_000_000,
                "output_tokens": 5_000_000,
            }
        ]
        self.assertEqual(llm_cost_from_usage(calls), 0.0)

    def test_openrouter_free_suffix_is_zero(self):
        calls = [
            {
                "provider": "openrouter",
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "input_tokens": 5_000_000,
                "output_tokens": 5_000_000,
            }
        ]
        self.assertEqual(llm_cost_from_usage(calls), 0.0)

    def test_estimate_uses_real_ledger_when_present(self):
        from core import llm_router

        llm_router.reset_usage()
        llm_router._record_usage("deepseek", "deepseek-chat", "premium", 1_000_000, 1_000_000)
        try:
            cost = estimate_run_cost(script="word " * 50, rendered=False)
            self.assertAlmostEqual(cost["llm"], 1.37, places=4)
        finally:
            llm_router.reset_usage()


class TestFormatCostLine(unittest.TestCase):
    def test_empty_when_no_cost(self):
        self.assertEqual(format_cost_line(None), "")
        self.assertEqual(format_cost_line({}), "")

    def test_total_and_nonzero_breakdown(self):
        line = format_cost_line(
            {
                "llm": 0.04,
                "tts": 0.02,
                "apify": 0.0,
                "web_search": 0.01,
                "render": 0.0,
                "total": 0.07,
            }
        )
        self.assertIn("Est. run cost: $0.0700", line)
        self.assertIn("llm $0.0400", line)
        self.assertIn("tts $0.0200", line)
        self.assertIn("web $0.0100", line)
        # Zero components are omitted from the breakdown.
        self.assertNotIn("apify", line)
        self.assertNotIn("render", line)

    def test_total_only_when_no_components(self):
        line = format_cost_line({"total": 0.0})
        self.assertEqual(line, "Est. run cost: $0.0000")


class TestLLMCostByProvider(unittest.TestCase):
    """Per-provider split (O12) — the free-first chain's whole point is that most
    calls land on a $0 provider, which the aggregate `llm $x` hides."""

    def test_free_providers_reported_at_zero_not_dropped(self):
        calls = [
            {
                "provider": "ollama",
                "model": "llama3.1:8b",
                "input_tokens": 900,
                "output_tokens": 90,
            },
            {
                "provider": "openrouter",
                "model": "some/model:free",
                "input_tokens": 800,
                "output_tokens": 80,
            },
        ]
        out = llm_cost_by_provider(calls)
        self.assertEqual(out, {"ollama": 0.0, "openrouter": 0.0})

    def test_splits_and_sums_to_the_aggregate(self):
        calls = [
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "input_tokens": 10_000,
                "output_tokens": 2_000,
            },
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "input_tokens": 5_000,
                "output_tokens": 1_000,
            },
            {
                "provider": "ollama",
                "model": "llama3.1:8b",
                "input_tokens": 9_000,
                "output_tokens": 900,
            },
        ]
        out = llm_cost_by_provider(calls)
        self.assertEqual(set(out), {"deepseek", "ollama"})
        self.assertEqual(out["ollama"], 0.0)
        self.assertGreater(out["deepseek"], 0.0)
        # The split must reconcile with the headline number.
        self.assertAlmostEqual(sum(out.values()), llm_cost_from_usage(calls), places=6)

    def test_empty_ledger(self):
        self.assertEqual(llm_cost_by_provider([]), {})
        self.assertEqual(llm_cost_by_provider(None), {})

    def test_cost_line_appends_provider_split(self):
        line = format_cost_line(
            {"llm": 0.004, "total": 0.004},
            llm_by_provider={"deepseek": 0.004, "openrouter": 0.0},
        )
        self.assertIn("llm $0.0040 [deepseek $0.0040 · openrouter $0]", line)

    def test_cost_line_unchanged_without_the_split(self):
        # Back-compat: existing callers that pass no split get the old format.
        line = format_cost_line({"llm": 0.004, "total": 0.004})
        self.assertEqual(line, "Est. run cost: $0.0040 (llm $0.0040)")

    def test_cost_line_appends_stage_split(self):
        line = format_cost_line(
            {"llm": 0.004, "total": 0.004},
            llm_by_stage={"script": 0.003, "title": 0.001},
        )
        self.assertIn("stages[script $0.0030 · title $0.0010]", line)

    def test_llm_cost_by_stage(self):
        calls = [
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "stage": "script",
                "input_tokens": 1000,
                "output_tokens": 1000,
            }
        ]
        by_stage = llm_cost_by_stage(calls)
        self.assertIn("script", by_stage)
        self.assertGreater(by_stage["script"], 0.0)


class TestThumbnailCost(unittest.TestCase):
    def test_paid_providers_bill(self):
        with patch.dict("os.environ", {"COST_THUMBNAIL_PER_IMAGE": "0.045"}, clear=False):
            for provider in ("flux", "ideogram", "recraft"):
                self.assertAlmostEqual(thumbnail_cost(provider), 0.045, places=4, msg=provider)

    def test_pillow_and_missing_are_zero(self):
        self.assertEqual(thumbnail_cost("pillow"), 0.0)
        self.assertEqual(thumbnail_cost(""), 0.0)
        self.assertEqual(thumbnail_cost(None), 0.0)
        self.assertEqual(thumbnail_cost("unknown"), 0.0)

    def test_merge_adds_thumbnail_only_when_asked(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "piper"}, clear=False):
            stored = {"llm": 0.01, "tts": 0.0, "total": 0.01}
            tts_only = merge_render_cost(stored, "x" * 100)
            self.assertNotIn("thumbnail", tts_only)
            billed = merge_render_cost(stored, "x" * 100, thumbnail_provider="flux")
            self.assertGreater(billed["thumbnail"], 0.0)
            pillow = merge_render_cost(stored, "x" * 100, thumbnail_provider="pillow")
            self.assertEqual(pillow["thumbnail"], 0.0)

    def test_cached_synth_is_zero_tts_line(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            billed = merge_render_cost({}, "x" * 1000, tts_cached=False)
            cached = merge_render_cost({}, "x" * 1000, tts_cached=True)
        self.assertGreater(billed["tts"], 0.0)
        self.assertEqual(cached["tts"], 0.0)

    def test_remerge_preserves_existing_thumbnail_line(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "piper"}, clear=False):
            once = merge_render_cost({"llm": 0.01}, "hi", thumbnail_provider="flux")
            twice = merge_render_cost(once, "hi")
        self.assertAlmostEqual(once["thumbnail"], twice["thumbnail"], places=4)


class TestEscapedFreeFirstFlag(unittest.TestCase):
    def test_helper_reads_usage_records(self):
        self.assertTrue(escaped_free_first([{"escaped_free_first": True}]))
        self.assertFalse(escaped_free_first([{"provider": "deepseek"}]))
        self.assertFalse(escaped_free_first([]))

    def test_cost_line_appends_flag(self):
        line = format_cost_line({"llm": 0.004, "total": 0.004}, escaped_free_first_llm=True)
        self.assertIn("escaped free-first LLM", line)
        plain = format_cost_line({"llm": 0.004, "total": 0.004})
        self.assertNotIn("escaped", plain)


class TestStandardWouldHaveBilled(unittest.TestCase):
    def test_prices_elevenlabs_even_when_piper_selected(self):
        script = "x" * 1000
        with patch.dict("os.environ", {"TTS_PROVIDER": "piper"}, clear=False):
            billed = standard_would_have_billed(script, include_thumbnail=True)
            line = format_standard_billed_line(script)
        self.assertGreater(billed["tts"], 0.0)
        self.assertGreater(billed["thumbnail"], 0.0)
        self.assertIn("Standard would have billed", line)
        self.assertAlmostEqual(billed["total"], billed["tts"] + billed["thumbnail"], places=4)

    def test_hidden_on_standard_elevenlabs_run(self):
        with patch.dict(
            "os.environ",
            {"TTS_PROVIDER": "elevenlabs", "FREE_MODE_STRICT": ""},
            clear=False,
        ):
            self.assertEqual(format_standard_billed_line("x" * 200), "")

    def test_empty_script_is_silent(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "piper"}, clear=False):
            self.assertEqual(format_standard_billed_line(""), "")


if __name__ == "__main__":
    unittest.main()
