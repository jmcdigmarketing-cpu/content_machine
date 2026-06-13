import unittest

from core.seo import normalize_youtube_tags, tags_from_topic


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
