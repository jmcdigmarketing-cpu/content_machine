"""Run 74: link facts carried no date, so "weight recency heavily" had no input.

Every fact scraped from a URL was stamped with nothing at all, which meant the
selector could not tell yesterday's preview from a two-year-old explainer. The
page almost always says: `article:published_time`, JSON-LD `datePublished`, or a
`<time datetime=...>` element.

Fail-open throughout — a page with no date yields `None`, which the selector
treats as neutral, not stale.
"""

from __future__ import annotations

import unittest
from datetime import date

from bs4 import BeautifulSoup

from core.link_facts import _published_date


def _soup(head: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><head>{head}</head><body><p>x</p></body></html>", "html.parser")


class TestPublishedDate(unittest.TestCase):
    def test_open_graph_article_published_time(self):
        html = '<meta property="article:published_time" content="2026-08-28T18:08:00-05:00">'
        self.assertEqual(_published_date(_soup(html)), date(2026, 8, 28))

    def test_json_ld_date_published(self):
        html = (
            '<script type="application/ld+json">'
            '{"@type":"NewsArticle","datePublished":"2026-08-27T09:00:00Z"}'
            "</script>"
        )
        self.assertEqual(_published_date(_soup(html)), date(2026, 8, 27))

    def test_time_element_datetime_attribute(self):
        soup = BeautifulSoup(
            '<html><body><time datetime="2026-08-26">Aug 26</time></body></html>', "html.parser"
        )
        self.assertEqual(_published_date(soup), date(2026, 8, 26))

    def test_a_page_with_no_date_is_none_not_an_error(self):
        self.assertIsNone(_published_date(_soup("<title>No date here</title>")))

    def test_malformed_json_ld_is_ignored(self):
        html = '<script type="application/ld+json">{not json at all</script>'
        self.assertIsNone(_published_date(_soup(html)))

    def test_a_nonsense_date_string_is_ignored(self):
        html = '<meta property="article:published_time" content="soon">'
        self.assertIsNone(_published_date(_soup(html)))

    def test_open_graph_wins_over_a_stray_time_element(self):
        soup = BeautifulSoup(
            '<html><head><meta property="article:published_time" content="2026-08-28">'
            '</head><body><time datetime="2019-01-01">old</time></body></html>',
            "html.parser",
        )
        self.assertEqual(_published_date(soup), date(2026, 8, 28))


if __name__ == "__main__":
    unittest.main()
