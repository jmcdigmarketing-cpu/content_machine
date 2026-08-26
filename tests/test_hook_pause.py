"""#124 200–400ms pause after line 1; skip is byte-identical."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestHookPause(unittest.TestCase):
    def test_skip_without_timings_leaves_audio_bytes_and_argv_unchanged(self):
        from video.hook_pause import maybe_insert_hook_pause

        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "voice.mp3")
            with open(audio, "wb") as fh:
                fh.write(b"FAKEMP3BYTES")
            with open(audio, "rb") as fh:
                before = fh.read()
            with patch("video.hook_pause.subprocess.run") as run:
                applied = maybe_insert_hook_pause(audio, words=None, script="Hook line. Body.")
            with open(audio, "rb") as fh:
                after = fh.read()
        self.assertFalse(applied)
        self.assertEqual(before, after)
        run.assert_not_called()

    def test_inserts_pause_after_first_line_when_timings_exist(self):
        from video.hook_pause import first_line_end_seconds, maybe_insert_hook_pause

        words = [
            {"word": "Hook", "start": 0.0, "end": 0.2},
            {"word": "line.", "start": 0.2, "end": 0.5},
            {"word": "Body", "start": 0.5, "end": 0.9},
        ]
        end = first_line_end_seconds(words, "Hook line. Body next.")
        self.assertIsNotNone(end)
        self.assertAlmostEqual(end, 0.5, places=2)

        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "voice.mp3")
            with open(audio, "wb") as fh:
                fh.write(b"FAKEMP3BYTES")
            sidecar = audio + ".words.json"
            with open(sidecar, "w", encoding="utf-8") as fh:
                json.dump(words, fh)
            with patch("video.hook_pause.subprocess.run") as run:
                run.return_value.returncode = 0
                applied = maybe_insert_hook_pause(
                    audio, words=words, script="Hook line. Body next."
                )
            self.assertTrue(applied)
            self.assertTrue(run.called)
            argv = run.call_args.args[0]
            joined = " ".join(str(x) for x in argv)
            self.assertIn("0.2", joined)  # 200–400ms as seconds
            # Later word timings must shift so captions stay honest.
            with open(sidecar, encoding="utf-8") as fh:
                shifted = json.loads(fh.read())
            self.assertGreater(shifted[-1]["start"], words[-1]["start"])

    def test_pause_duration_is_within_200_400ms(self):
        from video.hook_pause import HOOK_PAUSE_SECONDS

        self.assertGreaterEqual(HOOK_PAUSE_SECONDS, 0.2)
        self.assertLessEqual(HOOK_PAUSE_SECONDS, 0.4)


if __name__ == "__main__":
    unittest.main()
