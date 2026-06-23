"""Tests for turning pasted links into fact lines."""

import unittest
from unittest.mock import MagicMock, patch

from core import link_facts as lf


class TestLooksLikeUrl(unittest.TestCase):
    def test_detects_urls(self):
        self.assertTrue(lf.looks_like_url("https://example.com/x"))
        self.assertTrue(lf.looks_like_url("http://youtu.be/abc"))

    def test_rejects_plain_text(self):
        self.assertFalse(lf.looks_like_url("Makhachev is the champ"))
        self.assertFalse(lf.looks_like_url("example.com without scheme"))


class TestYouTubeFacts(unittest.TestCase):
    @patch("apis.youtube_api.fetch_video_metadata")
    @patch("apis.youtube_api.extract_youtube_video_id", return_value="vid123")
    def test_youtube_link_returns_title_and_description(self, _id, mock_meta):
        mock_meta.return_value = {
            "video_id": "vid123",
            "title": "Gaethje shocks Topuria",
            "channel": "MMA Channel",
            "description": "Justin Gaethje defeated Ilia Topuria at the White House event.\nhttps://skip.me",
        }
        facts = lf.extract_facts_from_url("https://youtu.be/vid123")
        self.assertTrue(any("Gaethje shocks Topuria" in f for f in facts))
        self.assertTrue(any("defeated Ilia Topuria" in f for f in facts))
        self.assertFalse(any("http" in f for f in facts))


class TestArticleFacts(unittest.TestCase):
    @patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
    @patch("core.link_facts.requests.get")
    def test_article_extracts_title_and_paragraphs(self, mock_get, _ytid):
        html = (
            "<html><head><title>Fed holds rates</title>"
            '<meta name="description" content="The Federal Reserve held interest rates steady at 5 percent."></head>'
            "<body><p>Short.</p>"
            "<p>The decision was widely expected by economists tracking inflation data this quarter.</p>"
            "</body></html>"
        )
        mock_get.return_value = MagicMock(status_code=200, text=html)
        facts = lf.extract_facts_from_url("https://news.example.com/fed")
        self.assertTrue(any("Fed holds rates" in f for f in facts))
        self.assertTrue(any("held interest rates steady" in f for f in facts))
        self.assertFalse(any(f == "Short." for f in facts))  # too short to include

    @patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
    @patch("core.link_facts.requests.get")
    def test_filters_promo_and_teaser_questions(self, mock_get, _ytid):
        html = (
            "<html><head><title>NBA Trades</title>"
            '<meta name="description" content="CBS Sports has the latest NBA news and scores.">'
            "</head><body>"
            "<p>Will the Bucks finally move Giannis? Are the Lakers done dealing?</p>"
            "<p>Giannis Antetokounmpo was traded to the Miami Heat on Monday in a blockbuster deal.</p>"
            "</body></html>"
        )
        mock_get.return_value = MagicMock(status_code=200, text=html)
        facts = lf.extract_facts_from_url("https://news.example.com/nba")
        joined = " ".join(facts)
        self.assertNotIn("has the latest", joined)  # promo meta dropped
        self.assertNotIn("Will the Bucks", joined)  # teaser questions dropped
        self.assertTrue(any("traded to the Miami Heat" in f for f in facts))  # real fact kept

    @patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
    @patch("core.link_facts.requests.get", side_effect=Exception("network down"))
    def test_fetch_failure_returns_empty(self, mock_get, _ytid):
        self.assertEqual(lf.extract_facts_from_url("https://broken.example.com"), [])

    def test_non_url_returns_empty(self):
        self.assertEqual(lf.extract_facts_from_url("not a url"), [])


class TestJunkLine(unittest.TestCase):
    def test_flags_promo_and_questions(self):
        self.assertTrue(lf._is_junk_line("CBS Sports has the latest NBA news."))
        self.assertTrue(lf._is_junk_line("Will the Bucks move Giannis?"))
        self.assertTrue(lf._is_junk_line("Are they done? Is he leaving?"))
        self.assertTrue(lf._is_junk_line("Subscribe to our newsletter"))

    def test_allows_declarative_facts(self):
        self.assertFalse(
            lf._is_junk_line("Giannis Antetokounmpo was traded to the Miami Heat on Monday.")
        )
        self.assertFalse(
            lf._is_junk_line("The Federal Reserve held interest rates steady at 5 percent.")
        )


if __name__ == "__main__":
    unittest.main()
