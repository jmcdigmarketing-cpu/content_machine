"""#369: refuse to start a run whose projected cost exceeds PROJECTED_COST_MAX_USD."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core import run_mode
from core.pipeline import run_pipeline


class TestProjectedCostGate(unittest.TestCase):
    def test_unset_never_blocks(self):
        with patch.dict(
            os.environ, {"PROJECTED_COST_MAX_USD": "", "FREE_MODE_STRICT": ""}, clear=False
        ):
            os.environ.pop("PROJECTED_COST_MAX_USD", None)
            self.assertIsNone(run_mode.projected_cost_block_reason())
            self.assertEqual(run_mode.guard_before_discovery(), [])

    def test_over_budget_blocks_before_discovery_fetch(self):
        with (
            patch.dict(os.environ, {"PROJECTED_COST_MAX_USD": "0.0001", "FREE_MODE_STRICT": ""}),
            patch("core.pipeline.run_discovery") as mock_discovery,
            patch("core.pipeline.generate_content_package") as mock_content,
            patch("core.pipeline.record_content_run", return_value=1),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.write_run_dossier"),
        ):
            with self.assertRaises(run_mode.CostModeBlocked) as ctx:
                run_pipeline("UFC 350", length_choice="1")
        mock_discovery.assert_not_called()
        mock_content.assert_not_called()
        self.assertIn("PROJECTED_COST_MAX_USD", str(ctx.exception))

    def test_gate_uses_estimate_not_post_run_actuals(self):
        with (
            patch.dict(os.environ, {"PROJECTED_COST_MAX_USD": "0.50"}),
            patch(
                "core.cost_meter.estimate_run_cost",
                return_value={"total": 0.10, "llm": 0.10, "tts": 0.0},
            ) as est,
        ):
            self.assertIsNone(run_mode.projected_cost_block_reason())
        kwargs = est.call_args.kwargs
        self.assertTrue(kwargs.get("rendered"))
        # Estimate, never post-run actuals -- but the stand-in script must carry
        # real length, or TTS estimates at $0 and no realistic cap can ever fire.
        from core.script_length import PRESETS, count_spoken_words

        self.assertGreaterEqual(
            count_spoken_words(kwargs.get("script") or ""),
            max(p.max_words for p in PRESETS.values()),
        )


class TestProjectedCostIsAWorstCaseNotZero(unittest.TestCase):
    """The docstring promises a "worst-case rendered estimate". Estimating from an
    empty script made it ~$0.0075 (LLM only, no TTS chars), so an operator capping
    at a realistic $0.50 was never stopped -- the guard measured the wrong thing
    and reported clean (decisions SS18/SS24)."""

    def test_a_realistic_cap_actually_blocks(self):
        from core.run_mode import projected_cost_block_reason

        with patch.dict(os.environ, {"PROJECTED_COST_MAX_USD": "0.50"}, clear=False):
            reason = projected_cost_block_reason()
        self.assertIsNotNone(reason, "a $0.50 cap must stop a run that renders for ~$1")
        self.assertIn("PROJECTED_COST_MAX_USD", reason)

    def test_a_generous_cap_still_lets_the_run_start(self):
        from core.run_mode import projected_cost_block_reason

        with patch.dict(os.environ, {"PROJECTED_COST_MAX_USD": "50"}, clear=False):
            self.assertIsNone(projected_cost_block_reason())

    def test_unset_is_still_off(self):
        from core.run_mode import projected_cost_block_reason

        with patch.dict(os.environ, {"PROJECTED_COST_MAX_USD": ""}, clear=False):
            self.assertIsNone(projected_cost_block_reason())
