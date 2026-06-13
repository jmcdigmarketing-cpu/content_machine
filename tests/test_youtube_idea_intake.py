"""Tests for YouTube video-id extraction + metadata fetch (option 5 idea intake)."""

import unittest
from unittest.mock import patch

from apis.youtube_api import extract_youtube_video_id, fetch_video_metadata


class TestExtractVideoId(unittest.TestCase):
    def test_watch_url(self):
        self.assertEqual(
            extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_short_url(self):
        self.assertEqual(extract_youtube_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_shorts_url(self):
        self.assertEqual(
            extract_youtube_video_id("https://youtube.com/shorts/abc123XYZ_-"),
            "abc123XYZ_-",
        )

    def test_watch_url_with_extra_params(self):
        self.assertEqual(
            extract_youtube_video_id(
                "https://www.youtube.com/watch?list=PLxxxx&v=dQw4w9WgXcQ&t=42"
            ),
            "dQw4w9WgXcQ",
        )

    def test_bare_id(self):
        self.assertEqual(extract_youtube_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_plain_text_is_not_an_id(self):
        self.assertIsNone(extract_youtube_video_id("Marvel Rivals season 3 tier list"))

    def test_empty(self):
        self.assertIsNone(extract_youtube_video_id(""))
        self.assertIsNone(extract_youtube_video_id(None))


class TestFetchVideoMetadata(unittest.TestCase):
    def test_no_api_key_returns_none(self):
        with patch("apis.youtube_api._youtube_key", return_value=""):
            self.assertIsNone(fetch_video_metadata("https://youtu.be/dQw4w9WgXcQ"))

    def test_unparseable_input_returns_none(self):
        with patch("apis.youtube_api._youtube_key", return_value="key"):
            self.assertIsNone(fetch_video_metadata("not a video"))

    def test_parses_snippet(self):
        fake_response = {
            "items": [
                {
                    "snippet": {
                        "title": "Marvel Rivals Season 3 Breakdown",
                        "channelTitle": "Necros",
                        "description": "patch notes here",
                    }
                }
            ]
        }

        class _Exec:
            def execute(self):
                return fake_response

        class _Videos:
            def list(self, **_kwargs):
                return _Exec()

        class _Client:
            def videos(self):
                return _Videos()

        with (
            patch("apis.youtube_api._youtube_key", return_value="key"),
            patch("apis.youtube_api._get_youtube_client", return_value=_Client()),
            patch("apis.youtube_api.record_usage"),
        ):
            meta = fetch_video_metadata("https://youtu.be/dQw4w9WgXcQ")

        self.assertIsNotNone(meta)
        self.assertEqual(meta["title"], "Marvel Rivals Season 3 Breakdown")
        self.assertEqual(meta["channel"], "Necros")
        self.assertEqual(meta["video_id"], "dQw4w9WgXcQ")


if __name__ == "__main__":
    unittest.main()
