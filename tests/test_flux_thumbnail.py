import os
import tempfile
import unittest
from unittest.mock import patch

from assets.flux_thumbnail import (
    _thumbnail_basename,
    generate_thumbnail,
    list_channel_thumbnails,
)


class TestFluxThumbnail(unittest.TestCase):
    def test_unique_basenames(self):
        a = _thumbnail_basename("Same Title", "topic", suffix="pillow_run1")
        b = _thumbnail_basename("Same Title", "topic", suffix="pillow_run2")
        self.assertNotEqual(a, b)
        self.assertTrue(a.endswith(".jpg"))

    @patch.dict(os.environ, {"THUMBNAIL_FLUX_FIRST": "false"}, clear=False)
    def test_pillow_always_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_thumbnail(
                "NBA Finals",
                "Knicks vs Spurs",
                output_dir=tmp,
                content_run_id=99,
                channel_id="tapin",
            )
            self.assertTrue(result.path)
            self.assertTrue(os.path.isfile(result.path))
            self.assertGreaterEqual(len(list_channel_thumbnails(tmp)), 1)

    def test_grade_c_skips_flux(self):
        from assets.flux_thumbnail import ThumbnailResult

        paid = ThumbnailResult(path="paid.jpg", status="generated", detail="Flux", provider="flux")
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {"THUMBNAIL_MIN_GRADE": "B"}, clear=False),
                patch("assets.flux_thumbnail.is_flux_configured", return_value=True),
                patch("assets.flux_thumbnail._flux_thumbnail", return_value=paid) as fx,
            ):
                result = generate_thumbnail(
                    "NBA",
                    "Title",
                    output_dir=tmp,
                    grade_letter="C",
                )
            fx.assert_not_called()
            self.assertEqual(result.provider, "pillow")
            self.assertTrue(result.path)

    def test_paid_blocked_helper(self):
        from assets.flux_thumbnail import paid_thumbnail_blocked

        self.assertFalse(paid_thumbnail_blocked("A"))
        self.assertFalse(paid_thumbnail_blocked("B"))
        self.assertTrue(paid_thumbnail_blocked("C"))
        self.assertFalse(paid_thumbnail_blocked(None))


if __name__ == "__main__":
    unittest.main()
