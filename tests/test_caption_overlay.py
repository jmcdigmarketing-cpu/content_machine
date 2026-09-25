"""#182. Caption overlay on a still so names can be proofread before burn."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image


class TestCaptionOverlay(unittest.TestCase):
    def test_overlay_burns_the_script_token_onto_the_frame(self):
        from video.caption_overlay import overlay_captions_on_still

        script = "Quillan Salkilld just submitted Mateusz Gamrot in round one."
        with tempfile.TemporaryDirectory() as tmp:
            frame = Path(tmp) / "frame.png"
            Image.new("RGB", (540, 960), (20, 20, 20)).save(frame)
            dest = Path(tmp) / "proof.png"
            result = overlay_captions_on_still(
                str(frame),
                script,
                str(dest),
                channel_id="tapin",
            )
            self.assertTrue(Path(result.path).is_file())
            self.assertIn("Salkilld", result.lines[0])
            before = Image.open(frame).tobytes()
            after = Image.open(result.path).tobytes()
            self.assertNotEqual(before, after)

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("caption-still", ops.COMMANDS)
