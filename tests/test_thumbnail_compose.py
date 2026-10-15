"""#1047 thumbnail plate: a short headline, inside the margins, refused when unreadable."""

from __future__ import annotations

import os
import tempfile
import unittest

from PIL import Image

from assets.thumbnail_compose import compose_thumbnail, headline_words


class TestHeadlineWords(unittest.TestCase):
    def test_a_long_title_becomes_three_to_five_words(self):
        words = headline_words("The Knicks Beat The Spurs In Overtime Tonight")
        self.assertGreaterEqual(len(words), 3)
        self.assertLessEqual(len(words), 5)
        self.assertEqual(words, ["The", "Knicks", "Beat", "The"])


class TestThumbnailPlate(unittest.TestCase):
    def _base(self, color: tuple[int, int, int]) -> Image.Image:
        return Image.new("RGB", (1280, 720), color)

    def test_dark_plate_keeps_size_margins_and_contrast(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "plate.jpg")
            plate = compose_thumbnail(
                self._base((18, 22, 42)),
                "The Knicks Beat The Spurs In Overtime Tonight",
                dest,
            )
            self.assertEqual(plate.refused, "")
            self.assertEqual((plate.width, plate.height), (1280, 720))
            self.assertGreaterEqual(len(plate.words), 3)
            self.assertLessEqual(len(plate.words), 5)
            self.assertGreaterEqual(plate.contrast, 4.5)
            x0, y0, x1, y1 = plate.text_box
            self.assertGreaterEqual(x0, plate.margin)
            self.assertGreaterEqual(y0, plate.margin)
            self.assertLessEqual(x1, plate.width - plate.margin)
            self.assertLessEqual(y1, plate.height - plate.margin)
            with Image.open(dest) as saved:
                self.assertEqual(saved.size, (1280, 720))

    def test_white_on_white_gets_a_dark_plate(self):
        # #1178 (was "is refused and not written"): 4 of 8 thumbnails went out with no words.
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "bad.jpg")
            plate = compose_thumbnail(
                self._base((250, 250, 250)),
                "Knicks Beat Spurs Tonight",
                dest,
            )
            self.assertEqual(plate.refused, "")
            self.assertTrue(plate.backed)
            self.assertTrue(os.path.isfile(dest))

    def test_a_subject_image_is_pasted_inside_the_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "cut.jpg")
            subject = Image.new("RGB", (80, 80), (220, 20, 20))
            plate = compose_thumbnail(
                self._base((18, 22, 42)),
                "Knicks Beat Spurs Tonight",
                dest,
                subject=subject,
            )
            self.assertEqual(plate.refused, "")
            with Image.open(dest) as saved:
                rgb = saved.convert("RGB")
                # The cutout sits against the right margin. JPEG shifts the
                # red a little; it must still read as the subject, not the plate.
                r, g, b = rgb.getpixel((1280 - 64 - 40, 360))
            self.assertGreater(r, 180)
            self.assertLess(g, 80)
            self.assertLess(b, 80)


if __name__ == "__main__":
    unittest.main()
