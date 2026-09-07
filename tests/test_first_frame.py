"""#513. A black or frozen first frame is the worst auto-thumbnail YouTube can pick."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image


class TestFirstFrameCheck(unittest.TestCase):
    def test_a_black_frame_is_rejected(self):
        from core.first_frame import inspect_frame

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "black.png"
            Image.new("RGB", (64, 64), (0, 0, 0)).save(path)
            check = inspect_frame(path)
        self.assertTrue(check.black)
        self.assertIn("black", check.detail.lower())

    def test_a_busy_frame_is_accepted(self):
        from core.first_frame import inspect_frame

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "busy.png"
            img = Image.new("RGB", (64, 64), (40, 80, 120))
            for x in range(0, 64, 4):
                img.putpixel((x, x), (255, 200, 0))
            img.save(path)
            check = inspect_frame(path)
        self.assertFalse(check.black)
        self.assertFalse(check.frozen)

    def test_two_identical_frames_are_frozen(self):
        from core.first_frame import inspect_frames

        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.png"
            b = Path(tmp) / "b.png"
            Image.new("RGB", (32, 32), (10, 10, 10)).save(a)
            Image.new("RGB", (32, 32), (10, 10, 10)).save(b)
            check = inspect_frames(a, b)
        self.assertTrue(check.frozen)

    def test_publish_warns_and_does_not_skip_upload(self):
        """Advisory: fail-visible, never a silent skip of a real file."""
        from core.first_frame import FirstFrameCheck, render_check

        check = FirstFrameCheck(
            black=True,
            frozen=False,
            mean_luma=0.0,
            detail="first frame is black",
        )
        text = render_check(check)
        self.assertIn("BLACK", text)
        self.assertIn("advisory", text.lower())
