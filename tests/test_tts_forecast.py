"""#371: TTS char forecast is recorded before synth; actual + delta after."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core.tts_char_cap import forecast_tts, last_tts_forecast, reset_tts_forecast


class TestTtsForecast(unittest.TestCase):
    def setUp(self):
        reset_tts_forecast()

    def tearDown(self):
        reset_tts_forecast()

    def test_forecast_is_recorded_before_synth(self):
        script = "Hook line about the fight. " * 20
        snap = forecast_tts(script)
        self.assertGreater(snap["forecast_chars"], 0)
        self.assertGreater(snap["forecast_usd"], 0.0)
        self.assertIsNone(snap.get("actual_chars"))

    def test_generate_audio_records_forecast_and_actual(self):
        from core.tts import generate_audio

        script = "Short hook about the card."
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = os.path.join(tmp.name, "out.mp3")

        def fake_alt(spoken, output_path, channel_id=None):
            with open(output_path, "wb") as f:
                f.write(b"ID3")
            return output_path

        with (
            patch.dict(
                "os.environ", {"TTS_PROVIDER": "piper", "FREE_MODE_STRICT": ""}, clear=False
            ),
            patch("core.tts._try_alt_tts_provider", side_effect=fake_alt),
            patch("core.tts.tts_cache_lookup", return_value=False),
        ):
            generate_audio(script, out, channel_id="tapin")
        snap = last_tts_forecast()
        self.assertIsNotNone(snap)
        self.assertGreater(snap["forecast_chars"], 0)
        self.assertGreater(snap["actual_chars"], 0)
        self.assertIn("delta_chars", snap)
