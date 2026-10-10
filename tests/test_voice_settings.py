"""#1037 the ElevenLabs request carries the channel's voice settings.

The numbers come from the shipped ``tts`` block. A two-arm experiment can
replace them. The client is a fake.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core import tts
from core.experiment_levers import arms


class TestChannelVoiceSettings(unittest.TestCase):
    def test_the_request_settings_include_stability_style_and_similarity(self):
        from config.channels import get_channel_profile

        profile = get_channel_profile("tapin")
        client = MagicMock()
        client.voices.settings.get.return_value = MagicMock(
            model_dump=lambda: {"stability": 0.1, "similarity_boost": 0.1, "style": 0.9}
        )
        with patch.object(tts, "get_channel_profile", return_value=profile):
            settings = tts._elevenlabs_voice_settings(
                client, "voice", profile.tts_speed or 1.05, channel_id="tapin"
            )
        self.assertEqual(settings.stability, profile.tts_stability)
        self.assertEqual(settings.style, profile.tts_style)
        self.assertEqual(settings.similarity_boost, profile.tts_similarity_boost)

    def test_voice_delivery_is_a_two_arm_experiment(self):
        self.assertEqual(arms("voice_delivery"), ["steady", "expressive"])

    def test_the_expressive_arm_replaces_the_channel_numbers(self):
        from config.channels import get_channel_profile

        profile = get_channel_profile("tapin")
        client = MagicMock()
        client.voices.settings.get.return_value = MagicMock(model_dump=lambda: {})
        with (
            patch.object(tts, "get_channel_profile", return_value=profile),
            patch(
                "core.experiments.next_arm",
                return_value=("voice_delivery", "expressive", "expressive"),
            ),
        ):
            settings = tts._elevenlabs_voice_settings(client, "voice", 1.05, channel_id="tapin")
        self.assertNotEqual(settings.stability, profile.tts_stability)
        self.assertEqual(settings.style, 0.45)


if __name__ == "__main__":
    unittest.main()
