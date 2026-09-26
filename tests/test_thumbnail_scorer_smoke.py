import os
import tempfile
import unittest
from unittest.mock import patch

from assets.thumbnail_scorer import score_thumbnail
from tests.optional_deps import requires_pillow


class TestThumbnailScorerSmoke(unittest.TestCase):
    def test_heuristic_when_disabled_returns_none(self):
        with patch.dict(os.environ, {"THUMBNAIL_SCORER_ENABLED": "false"}, clear=False):
            self.assertIsNone(score_thumbnail("nope.jpg", "topic"))

    @requires_pillow
    def test_heuristic_scores_file(self):
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            path = tmp.name
            Image.new("RGB", (1080, 1920), color=(40, 40, 200)).save(path, "JPEG")

        try:
            with patch.dict(os.environ, {"THUMBNAIL_SCORER_ENABLED": "true"}, clear=False):
                with patch("assets.thumbnail_scorer._vision_score", return_value=None):
                    result = score_thumbnail(
                        path,
                        "Marvel Rivals meta debate",
                        channel_id="tapin",
                        persist=False,
                    )
            self.assertIsNotNone(result)
            self.assertGreater(result.overall, 0)
            self.assertEqual(result.source, "heuristic")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
