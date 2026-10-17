"""#1208: an MMA Fighting headline was ranked on NBA's numbers.

Live best bets, 2026-10-15: "The next Sean O'Malley: Ranking the best prospects
from Season 10 of Contender Series" — "trending on MMA Fighting now · nba averages
168 views". The words match the NBA list on "contender". The feed is tagged ufc.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

TITLE = "The next Sean O'Malley: Ranking the best prospects from Season 10 of Contender Series"
FEED = {
    "name": "MMA Fighting",
    "url": "https://www.mmafighting.com/rss/index.xml",
    "domains": ["ufc", "mma"],
}
_ENTRIES = [
    {"topic": "old ufc topic", "engaged_rate": 0.2, "composite_score": 60, "domain": "ufc"},
    {"topic": "old nba topic", "engaged_rate": 0.11, "composite_score": 50, "domain": "nba"},
]


class FeedHeadlineDomainTests(unittest.TestCase):
    def test_the_contender_series_headline_is_ranked_on_ufc(self):
        from core.best_bet import get_best_bets

        def fetch(_url):
            return [{"title": TITLE, "published": "Thu, 15 Oct 2026 12:00:00 GMT"}]

        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("config.data_sources.rss_feeds_for_channel", return_value=[FEED]),
            patch("apis.rss_feeds._fetch_feed", side_effect=fetch),
            patch("core.topic_graph.follow_up_seed", return_value=None),
            patch("core.seasonal_calendar.due_topics", return_value=[]),
            patch("analytics.mailbag.top_question", return_value=None),
        ):
            bets = get_best_bets("tapin", 5)
        bet = next(b for b in bets if b.topic == TITLE)
        self.assertIn("MMA Fighting", bet.rationale)
        self.assertIn("ufc averages", bet.rationale)
        self.assertNotIn("nba averages", bet.rationale)
        self.assertEqual(bet.domain, "ufc")

    def test_the_same_title_with_no_feed_tag_is_ufc(self):
        """#1215: the live title, with no feed tag, was nba on the word "contender"."""
        from core.best_bet import _consider_candidate

        cand = _consider_candidate(
            TITLE,
            "somewhere",
            allowed={"gaming", "ufc", "nba"},
            exclude=set(),
            seen_local=set(),
        )
        self.assertIsNotNone(cand)
        self.assertEqual(cand["domain"], "ufc")

    def test_a_lakers_contender_stays_nba(self):
        """Bare "contender" is still NBA. Only "contender series" is the UFC show."""
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(
            infer_topic_domain("Why the Lakers are not a contender yet"),
            "nba",
        )
        self.assertEqual(infer_topic_domain("NBA title contenders this spring"), "nba")
