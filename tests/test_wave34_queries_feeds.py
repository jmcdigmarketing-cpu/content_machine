"""Wave 34: football topics get football feeds and name-shaped signal queries.

#859 - after wave 33 made soccer a TapIn domain, `rss_feeds_for_topic` returned no
football feed at all: the two global sports feeds are tagged nba/nfl/ufc/mma and
`domain_rss` had no `soccer` key.

#852 - signals still queried the raw typed sentence. API-SPORTS searched teams for
"Manchester City ofund guilty, what does this mea" (the topic cut at 48 characters),
and Wikipedia tried 6-, 3- and 1-word titles but never "Manchester_City", which is how
run 98 resolved to the city of Manchester.
"""

from __future__ import annotations

import unittest

RUN98 = "Manchester City ofund guilty, what does this mean for the prem"
BBC_FOOTBALL = "https://feeds.bbci.co.uk/sport/football/rss.xml"
GUARDIAN_FOOTBALL = "https://www.theguardian.com/football/rss"


class TestSoccerFeeds(unittest.TestCase):
    def test_a_football_topic_gets_football_feeds(self) -> None:
        from config.data_sources import rss_feeds_for_topic

        urls = {f["url"] for f in rss_feeds_for_topic(RUN98, "tapin")}
        self.assertIn(BBC_FOOTBALL, urls)
        self.assertIn(GUARDIAN_FOOTBALL, urls)

    def test_a_gaming_topic_does_not(self) -> None:
        from config.data_sources import rss_feeds_for_topic

        urls = {f["url"] for f in rss_feeds_for_topic("Marvel Rivals season 4 patch", "tapin")}
        self.assertNotIn(BBC_FOOTBALL, urls)
        self.assertNotIn(GUARDIAN_FOOTBALL, urls)


class TestTitlePhrases(unittest.TestCase):
    def test_run98_names_the_club(self) -> None:
        from apis.topic_tokens import title_phrases

        self.assertEqual(title_phrases(RUN98), ["Manchester City"])

    def test_several_names_and_no_sentence_starters(self) -> None:
        from apis.topic_tokens import title_phrases

        self.assertEqual(
            title_phrases("Liverpool vs Manchester United preview"),
            ["Liverpool", "Manchester United"],
        )
        self.assertEqual(title_phrases("What does Arsenal need now"), ["Arsenal"])

    def test_lower_case_has_none(self) -> None:
        from apis.topic_tokens import title_phrases

        self.assertEqual(title_phrases("manchester city found guilty"), [])


class TestApiSportsQuery(unittest.TestCase):
    def test_run98_searches_the_team_not_the_sentence(self) -> None:
        from apis.api_sports_api import _search_query

        self.assertEqual(_search_query(RUN98), "Manchester City")

    def test_a_lower_case_topic_still_gets_a_short_query(self) -> None:
        from apis.api_sports_api import _search_query

        self.assertEqual(_search_query("arsenal title race"), "arsenal title")


class TestWikipediaCandidates(unittest.TestCase):
    def test_the_club_page_is_tried_before_the_city(self) -> None:
        from apis.wikipedia_pageviews_api import _article_candidates

        cands = _article_candidates(RUN98)
        self.assertIn("Manchester_City", cands)
        self.assertLess(cands.index("Manchester_City"), cands.index("Manchester"))

    def test_franchise_pages_stay_first(self) -> None:
        from apis.wikipedia_pageviews_api import _article_candidates

        self.assertEqual(_article_candidates("GTA 6 delay news")[0], "Grand_Theft_Auto_VI")


if __name__ == "__main__":
    unittest.main()
