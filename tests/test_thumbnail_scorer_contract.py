import inspect
import unittest

from assets.thumbnail_scorer import ThumbnailScore, score_thumbnail


class TestThumbnailScorerContract(unittest.TestCase):
    def test_score_thumbnail_signature(self):
        sig = inspect.signature(score_thumbnail)
        self.assertIn("image_path", sig.parameters)
        self.assertIn("topic", sig.parameters)
        self.assertIn("channel_id", sig.parameters)

    def test_thumbnail_score_fields(self):
        s = ThumbnailScore(
            curiosity=70,
            clarity=80,
            contrast=65,
            emotion=72,
            overall=71.75,
            suggestions=["Add contrast"],
            source="heuristic",
        )
        d = s.to_dict()
        self.assertEqual(d["overall"], 71.75)
        self.assertEqual(d["suggestions"], ["Add contrast"])


if __name__ == "__main__":
    unittest.main()
