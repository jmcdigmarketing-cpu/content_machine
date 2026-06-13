import inspect
import unittest

from publishing.base import Publisher, PublishRequest, PublishResult
from publishing.registry import get_publisher, list_platforms
from publishing.youtube_publisher import YouTubePublisher


class TestPublisherContract(unittest.TestCase):
    def test_youtube_publisher_implements_abc(self):
        pub = YouTubePublisher()
        self.assertIsInstance(pub, Publisher)
        self.assertEqual(pub.platform, "youtube")

    def test_publish_signature(self):
        sig = inspect.signature(YouTubePublisher.publish)
        params = list(sig.parameters)
        self.assertIn("request", params)
        self.assertIn("channel_id", params)

    def test_registry_youtube_only_for_now(self):
        self.assertEqual(list_platforms(), ["youtube"])
        self.assertIsInstance(get_publisher("youtube"), YouTubePublisher)
        self.assertIsNone(get_publisher("tiktok"))
        self.assertIsNone(get_publisher("instagram"))

    def test_publish_result_dataclass(self):
        r = PublishResult(video_id="x", status="uploaded", platform="youtube")
        self.assertEqual(r.platform, "youtube")


if __name__ == "__main__":
    unittest.main()
