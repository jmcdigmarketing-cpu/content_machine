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
        # Run 98: the title is source metadata, not a fact line.
        self.assertFalse(any("Fed holds rates" in f for f in facts))
        self.assertEqual(lf.last_extract_report()["title"], "Fed holds rates")
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
    @patch("core.link_facts.requests.get")
    def test_waf_challenge_returns_empty_with_issue(self, mock_get, _ytid):
        html = (
            "<html><head><title></title></head><body>"
            "<script>window.awsWafCookieDomainList=[]</script></body></html>"
        )
        mock_get.return_value = MagicMock(status_code=202, text=html)
        self.assertEqual(lf.extract_facts_from_url("https://www.espn.com/nba/story"), [])
        issue = lf.link_fetch_issue("https://www.espn.com/nba/story")
        self.assertIsNotNone(issue)
        self.assertIn("blocked automated fetch", issue.lower())

    @patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
    @patch("core.link_facts.requests.get")
    def test_yahoo_sidebar_related_links_filtered(self, mock_get, _ytid):
        html = (
            "<html><head><title>Lakers rumors: Insider reveals LeBron plans</title></head>"
            "<body><article>"
            "<p>The Lakers reportedly wanted James to take a pay cut as an attempt to add a center.</p>"
            "<p>As free agent LeBron James ponders what is next, the Lakers will always be in the mix.</p>"
            "</article>"
            "<aside><ul>"
            "<li>Related: Rui Hachimura pens Lakers goodbye after Clippers signing</li>"
            "<li>USMNT's dream ends in rout</li>"
            "<li>Ronaldo fights back tears</li>"
            "<li>College &amp; High School</li>"
            "</ul></aside></body></html>"
        )
        mock_get.return_value = MagicMock(status_code=200, text=html)
        facts = lf.extract_facts_from_url("https://sports.yahoo.com/articles/lakers-rumors")
        joined = " ".join(facts)
        self.assertIn("pay cut", joined)
        self.assertNotIn("Rui Hachimura", joined)
        self.assertNotIn("USMNT", joined)
        self.assertNotIn("Ronaldo", joined)
        self.assertNotIn("College", joined)

    def test_non_url_returns_empty(self):
        self.assertEqual(lf.extract_facts_from_url("not a url"), [])

    def test_bing_search_url_blocked(self):
        url = "https://www.bing.com/search?q=nba+2027+predictions"
        self.assertEqual(lf.extract_facts_from_url(url), [])
        issue = lf.link_fetch_issue(url)
        self.assertIsNotNone(issue)
        self.assertIn("destination", issue.lower())

    @patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
    @patch("core.link_facts.requests.get")
    def test_captcha_title_rejected(self, mock_get, _ytid):
        html = "<html><head><title>Robot Challenge Screen</title></head><body></body></html>"
        mock_get.return_value = MagicMock(status_code=200, text=html)
        facts = lf.extract_facts_from_url("https://nbadraftroom.com/2027-nba-mock-draft/")
        self.assertEqual(facts, [])

    def test_unwrap_bing_redirect(self):
        wrapped = "https://www.bing.com/ck/a?!&&p=x&u=a1aHR0cHM6Ly93d3cuZXNwbi5jb20vbmJhLw=="
        self.assertIn("espn.com", lf._unwrap_redirect_url(wrapped))


class TestReaderProxyAndTitleOnly(unittest.TestCase):
    def test_is_title_only(self):
        self.assertTrue(lf.is_title_only(["Source: MSN"]))
        self.assertTrue(lf.is_title_only([]))
        self.assertFalse(lf.is_title_only(["Source: MSN", "A real body paragraph of facts here."]))

    @patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
    @patch("core.link_facts.requests.get")
    def test_reader_proxy_off_by_default(self, mock_get, _ytid):
        html = "<html><head><title>MSN Story</title></head><body></body></html>"
        mock_get.return_value = MagicMock(status_code=200, text=html)
        with (
            patch.dict("os.environ", {"LINK_READER_PROXY": ""}, clear=False),
            patch("core.link_facts._reader_proxy_facts") as proxy,
        ):
            lf.extract_facts_from_url("https://www.msn.com/en-au/story")
        proxy.assert_not_called()  # title-only, but proxy is opt-in

    @patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
    @patch("core.link_facts.requests.get")
    def test_reader_proxy_recovers_body_when_enabled(self, mock_get, _ytid):
        html = "<html><head><title>MSN Story</title></head><body></body></html>"
        mock_get.return_value = MagicMock(status_code=200, text=html)
        with (
            patch.dict("os.environ", {"LINK_READER_PROXY": "1"}, clear=False),
            patch(
                "core.link_facts._reader_proxy_facts",
                return_value=[
                    "A long recovered body paragraph well over the sixty character gate."
                ],
            ),
        ):
            facts = lf.extract_facts_from_url("https://www.msn.com/en-au/story")
        self.assertTrue(any("recovered body paragraph" in f for f in facts))


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
