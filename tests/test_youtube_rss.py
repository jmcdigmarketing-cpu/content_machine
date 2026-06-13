import unittest
from unittest.mock import patch

from analytics.youtube_rss import fetch_channel_uploads_rss

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>First upload</title>
    <published>2026-06-01T12:00:00+00:00</published>
    <yt:videoId>abc123</yt:videoId>
  </entry>
  <entry>
    <title>Second upload</title>
    <published>2026-06-02T12:00:00+00:00</published>
    <yt:videoId>def456</yt:videoId>
  </entry>
</feed>"""


class TestYoutubeRss(unittest.TestCase):
    @patch("analytics.youtube_rss.requests.get")
    def test_parses_atom_feed(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = SAMPLE_FEED.encode("utf-8")

        videos = fetch_channel_uploads_rss("UCtest123", max_results=5)
        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0]["title"], "First upload")
        self.assertEqual(videos[0]["video_id"], "abc123")
        self.assertEqual(videos[0]["source"], "youtube_rss")

    @patch("analytics.youtube_rss.requests.get")
    def test_non_200_returns_empty(self, mock_get):
        mock_get.return_value.status_code = 404
        self.assertEqual(fetch_channel_uploads_rss("UCmissing"), [])


if __name__ == "__main__":
    unittest.main()
