import unittest

from core.channel_context import (
    anchor_preservation_penalty,
    dominant_anchor,
    extract_anchors,
    mcu_drift_penalty,
    normalize_seed_topic,
    preserves_anchors,
)


class TestChannelContext(unittest.TestCase):
    def test_extract_marvel_rivals(self):
        self.assertEqual(extract_anchors("Marvel rivals update"), ["Marvel Rivals"])

    def test_preserves_anchors(self):
        self.assertTrue(
            preserves_anchors(
                "Marvel Rivals Cyclops patch breakdown",
                "Marvel rivals update",
            )
        )
        self.assertFalse(
            preserves_anchors(
                "Marvel's Game-Changing Rivalries",
                "Marvel rivals update",
            )
        )

    def test_mcu_drift_penalty(self):
        self.assertGreater(
            mcu_drift_penalty(
                "Loki joins the Avengers — epic Marvel rivalries",
                "Marvel rivals update",
            ),
            0,
        )
        self.assertEqual(
            mcu_drift_penalty(
                "Marvel Rivals Season 8 Cyclops",
                "Marvel rivals update",
            ),
            0,
        )

    def test_anchor_preservation_penalty(self):
        self.assertEqual(
            anchor_preservation_penalty(
                "Generic gaming news",
                "Marvel rivals update",
            ),
            25.0,
        )

    def test_dominant_anchor(self):
        topics = [
            "Marvel rivals meta dead",
            "Marvel rivals Cyclops update",
            "GTA VI wishlist",
        ]
        self.assertEqual(dominant_anchor(topics), "Marvel Rivals")

    def test_normalize_seed_topic(self):
        self.assertEqual(
            normalize_seed_topic(
                "Primary Storyline: Marvel's Game-Changing Rivalries: What's New?"
            ),
            "Marvel's Game-Changing Rivalries: What's New?",
        )


if __name__ == "__main__":
    unittest.main()
