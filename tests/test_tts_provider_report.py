"""TTS provider Bayesian report — no auto-switch, no experiments.json write."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.experiment_levers import known
from core.tts_provider_report import arm_outcomes, infer_arm, render_report, report


class TestTtsProviderReport(unittest.TestCase):
    def test_not_a_startable_lever(self):
        self.assertFalse(known("tts_provider"))
        self.assertFalse(known("piper"))

    def test_infer_explicit_and_cost(self):
        self.assertEqual(infer_arm(tts_cost=0.3, tts_provider="elevenlabs"), "elevenlabs")
        self.assertEqual(infer_arm(tts_cost=0.0, tts_provider="piper"), "piper")
        self.assertEqual(infer_arm(tts_cost=0.22, tts_provider=""), "elevenlabs")
        self.assertEqual(infer_arm(tts_cost=0.0, tts_provider="", rendered=True), "piper")
        self.assertIsNone(infer_arm(tts_cost=0.0, rendered=False))

    def test_bayesian_gate_on_synthetic_rates(self):
        rows = [{"engaged_rate": 0.4, "tts_cost": 0.3} for _ in range(6)] + [
            {"engaged_rate": 0.1, "tts_cost": 0.0, "tts_provider": "piper"} for _ in range(6)
        ]
        data = report("tapin", rows=rows)
        self.assertFalse(data["auto_switch"])
        self.assertEqual(data["n"]["elevenlabs"], 6)
        self.assertEqual(data["n"]["piper"], 6)
        self.assertIn(data["status"], {"winner", "no_clear_winner", "collecting"})
        blob = render_report(data)
        self.assertIn("no auto-switch", blob.lower())
        self.assertIn("TTS_PROVIDER is unchanged", blob)

    def test_arm_outcomes_ignores_bad_rates(self):
        out = arm_outcomes([{"engaged_rate": "x", "tts_cost": 1}])
        self.assertEqual(out["elevenlabs"], [])

    def test_does_not_touch_experiments_file(self):
        import tempfile

        import config.paths as paths

        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "experiments.json")
            with patch.object(paths, "EXPERIMENTS_FILE", target):
                report("tapin", rows=[])
            self.assertFalse(
                os.path.exists(target), "the TTS provider report wrote experiments.json"
            )
        # known() already proves the lever cannot be started; this proves the report
        # does not write the store either way.


if __name__ == "__main__":
    unittest.main()
