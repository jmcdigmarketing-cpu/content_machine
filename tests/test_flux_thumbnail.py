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


if __name__ == "__main__":
    unittest.main()
