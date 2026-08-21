"""Pronunciation lexicon for local TTS — ears, not captions.

Captions/retext keep the script spelling; Piper needs a spoken form. ElevenLabs
is not rewritten (it already handles names).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core import tts


class TestPronunciationLexicon(unittest.TestCase):
    def test_known_replacements(self):
        table = {"Salkilld": "Sal-killed", "Gamrot": "GAM-rot"}
        with patch.object(tts, "_lexicon_for_channel", return_value=table):
            out = tts.apply_pronunciation_lexicon(
                "Quillan Salkilld just submitted Mateusz Gamrot.", "tapin"
            )
        self.assertIn("Sal-killed", out)
        self.assertIn("GAM-rot", out)
        self.assertNotIn("Salkilld", out)

    def test_empty_lexicon_is_noop_and_preserves_identity(self):
        script = "Salkilld submitted Gamrot."
        with patch.object(tts, "_lexicon_for_channel", return_value={}):
            out = tts.apply_pronunciation_lexicon(script, "tapin")
        self.assertIs(out, script)

    def test_does_not_mutate_the_original_string(self):
        script = "Salkilld submitted Gamrot."
        with patch.object(tts, "_lexicon_for_channel", return_value={"Salkilld": "Sal-killed"}):
            spoken = tts.apply_pronunciation_lexicon(script, "tapin")
        self.assertEqual(script, "Salkilld submitted Gamrot.")
        self.assertIn("Sal-killed", spoken)

    def test_longest_key_wins(self):
        table = {"Topuria": "short", "Ilia Topuria": "EE-lee-ah toh-POO-ree-ah"}
        with patch.object(tts, "_lexicon_for_channel", return_value=table):
            out = tts.apply_pronunciation_lexicon("Ilia Topuria won.", "tapin")
        self.assertIn("EE-lee-ah", out)
        self.assertNotIn("short", out)

    def test_channel_overlay_overrides_default(self):
        data = {
            "default": {"Salkilld": "default-form"},
            "channels": {"tapin": {"Salkilld": "tapin-form"}},
        }
        with patch.object(tts, "_load_pronunciation_lexicon", return_value=data):
            self.assertEqual(tts.apply_pronunciation_lexicon("Salkilld", "tapin"), "tapin-form")
            self.assertEqual(
                tts.apply_pronunciation_lexicon("Salkilld", "moneywise"),
                "default-form",
            )

    def test_local_tts_applies_lexicon_without_mutating_script(self):
        script = "Salkilld wins."
        captured: dict[str, str] = {}

        def fake_alt(spoken, output_path, channel_id):
            captured["spoken"] = spoken
            with open(output_path, "wb") as f:
                f.write(b"x")
            return output_path

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "piper"}, clear=False),
                patch.object(tts, "_lexicon_for_channel", return_value={"Salkilld": "Sal-killed"}),
                patch.object(tts, "_try_alt_tts_provider", side_effect=fake_alt),
            ):
                tts.generate_audio(script, out, channel_id="tapin")
        self.assertEqual(script, "Salkilld wins.")
        self.assertIn("Sal-killed", captured["spoken"])

    def test_elevenlabs_path_does_not_apply_lexicon(self):
        env = {
            "TTS_PROVIDER": "elevenlabs",
            "ELEVEN_API_KEY": "k",
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "apply_pronunciation_lexicon") as apply_lex,
                patch.object(tts, "ElevenLabs") as eleven,
                patch.object(tts, "_word_timestamps_enabled", return_value=False),
                patch.object(tts, "_elevenlabs_quota_would_exceed", return_value=False),
                patch.object(tts, "_elevenlabs_record_chars"),
                patch.object(tts, "resolve_tts_config", return_value=("v", "m")),
            ):
                eleven.return_value.text_to_speech.convert.return_value = [b"x"]
                tts.generate_audio("Salkilld wins.", out, channel_id="tapin")
        apply_lex.assert_not_called()


if __name__ == "__main__":
    unittest.main()
