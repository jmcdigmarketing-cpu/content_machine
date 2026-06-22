import unittest
from unittest.mock import patch

from config.seo import default_tags_for_channel
from core.seo import normalize_youtube_tags, tags_from_topic


class TestDefaultTagsForChannel(unittest.TestCase):
    def _tags(self, topic):
        profile = {"default_tags": ["TapIn", "gaming", "UFC", "MMA", "shorts", "esports"]}
        hints = {"trending_tags": ["Strickland", "Gaethje", "Rousey", "Tsarukyan", "MVP"]}
        with (
            patch("config.seo.get_seo_profile", return_value=profile),
            patch("config.seo.load_seo_hints", return_value=hints),
        ):
            return default_tags_for_channel("tapin", topic)

    def test_trending_fighter_names_not_force_injected(self):
        # Regression: stale UFC fighter trending tags must not bleed onto a gaming
        # video. They are offered to the LLM separately (relevance-gated).
        tags = self._tags("GTA VI pre-order prices")
        for polluted in ("Strickland", "Gaethje", "Rousey", "Tsarukyan", "MVP"):
            self.assertNotIn(polluted, tags)

    def test_ufc_dropped_on_gaming_topic(self):
        tags = self._tags("Marvel Rivals new season meta")
        self.assertNotIn("UFC", tags)
        self.assertNotIn("MMA", tags)
        self.assertIn("gaming", tags)

    def test_ufc_kept_on_ufc_topic(self):
        tags = self._tags("UFC 320 main card predictions")
        self.assertIn("UFC", tags)
        self.assertIn("MMA", tags)


class TestSeoTags(unittest.TestCase):
    def test_normalize_dedupes_and_caps_count(self):
        tags = normalize_youtube_tags(
            ["UFC", "ufc", "MMA", "gaming", "TapIn"],
            extra=["MMA", "shorts"],
            max_tags=5,
        )
        self.assertEqual(len(tags), 5)
        self.assertEqual(tags[0].lower(), "ufc")

    def test_tags_from_topic(self):
        tags = tags_from_topic("Topuria will DOMINATE at UFC 250")
        self.assertTrue(any("Topuria" in t or "Ufc" in t or "UFC" in t for t in tags))


if __name__ == "__main__":
    unittest.main()
