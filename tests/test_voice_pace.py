"""#400: each voice reads at its own pace.

`spoken_words_per_second` is 3.3 times the channel speed for every voice. A voice
that is measured from its own word timings should replace that rate once three
renders agree, and the length presets stay on the nominal 3.3.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core import tts


def _words(count: int = 24, seconds: float = 10.0) -> list[dict]:
    return [{"word": f"w{i}", "start": 0.0, "end": seconds} for i in range(count)]


class MeasuredPaceTests(unittest.TestCase):
    def setUp(self):
        from config.channels import get_channel_profile

        self.voice = str(get_channel_profile("tapin").tts_voice_id)
        self.tmp = tempfile.TemporaryDirectory()
        self.store = os.path.join(self.tmp.name, "voice_pace.json")
        self.env = patch.dict(os.environ, {"VOICE_PACE_FILE": self.store})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_three_samples_replace_the_nominal_rate(self):
        from core.script_length import WORDS_PER_SECOND, record_pace, spoken_words_per_second
        from core.tts import speech_speed

        nominal = WORDS_PER_SECOND * speech_speed("tapin")
        self.assertAlmostEqual(spoken_words_per_second("tapin"), nominal)
        record_pace(self.voice, _words())
        record_pace(self.voice, _words())
        self.assertAlmostEqual(spoken_words_per_second("tapin"), nominal)
        record_pace(self.voice, _words())
        self.assertAlmostEqual(spoken_words_per_second("tapin"), 2.4)
        self.assertNotAlmostEqual(spoken_words_per_second("tapin"), nominal)

    def test_presets_keep_the_nominal_rate(self):
        from core.script_length import PRESETS, WORDS_PER_SECOND, record_pace

        for _ in range(3):
            record_pace(self.voice, _words())
        for preset in PRESETS.values():
            self.assertEqual(preset.min_seconds, round(preset.min_words / WORDS_PER_SECOND))
            self.assertEqual(preset.max_seconds, round(preset.max_words / WORDS_PER_SECOND))

    def test_the_render_records_the_voice_that_spoke(self):
        from core.script_length import spoken_words_per_second

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            tts._note_voice_spoken(tts.resolve_tts_config(channel_id)[0])
            with open(output_path, "wb") as handle:
                handle.write(b"ID3")
            with open(output_path + ".words.json", "w", encoding="utf-8") as handle:
                json.dump(_words(), handle)
            return output_path

        with (
            patch.dict(os.environ, {"TTS_CACHE": "false", "TTS_PROVIDER": "elevenlabs"}),
            patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
        ):
            for index in range(3):
                dest = os.path.join(self.tmp.name, f"out{index}.mp3")
                tts.generate_audio(
                    "hello world",
                    dest,
                    channel_id="tapin",
                    voices={"narrator": self.voice},
                )
        self.assertAlmostEqual(spoken_words_per_second("tapin"), 2.4)


if __name__ == "__main__":
    unittest.main()
