"""#1038 the TTS request can name either model in the experiment.

The operator's blind listen on three scripts is not done here. This only wires
the arm onto the request.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core import tts
from core.experiment_levers import arms


class TestTtsModelArm(unittest.TestCase):
    def test_the_model_lever_names_both_ids(self):
        from core.experiment_levers import tts_model_for_arm

        self.assertEqual(arms("tts_model"), ["multilingual_v2", "v3"])
        self.assertEqual(tts_model_for_arm("multilingual_v2"), "eleven_multilingual_v2")
        self.assertEqual(tts_model_for_arm("v3"), "eleven_v3")

    def test_an_active_arm_is_the_model_on_the_request(self):
        with (
            patch(
                "core.experiments.next_arm",
                return_value=("tts_model", "v3", "eleven_v3"),
            ),
            tts.voice_context({}),
        ):
            _voice, model = tts.resolve_tts_config("tapin")
        self.assertEqual(model, "eleven_v3")

    def test_without_an_experiment_the_channel_model_is_kept(self):
        with (
            patch("core.experiments.next_arm", return_value=None),
            tts.voice_context({}),
        ):
            _voice, model = tts.resolve_tts_config("tapin")
        self.assertEqual(model, "eleven_multilingual_v2")


if __name__ == "__main__":
    unittest.main()
