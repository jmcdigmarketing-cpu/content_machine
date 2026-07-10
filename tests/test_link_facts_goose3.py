"""goose3 grounding phase — goose3-first article-body extraction with BeautifulSoup fallback.

goose3 parses the already-fetched HTML (`raw_html`), so no test makes a network call and
existing `requests.get` mocks stay authoritative. goose3 is an optional dep exercised here
via a fake module injected into `sys.modules`. Verifies: cleaned text → body lines, empty /
error ⇒ [] (fallback), `_article_facts` prefers goose3 for normal articles but keeps the
BeautifulSoup path for trade-tracker pages, and `extract_facts_from_url` never raises.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

from core import link_facts


def _fake_goose3(cleaned_text: str, *, raises: bool = False) -> dict:
    """Build fake `goose3` + `goose3.configuration` modules for sys.modules patching."""

    class _Article:
        def __init__(self):
            self.cleaned_text = cleaned_text

    class Goose:
        def __init__(self, config=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract(self, url=None, raw_html=None):
            if raises:
                raise RuntimeError("goose3 parse failed")
            return _Article()

    class Configuration:
        def __init__(self):
            self.strict = True
            self.browser_user_agent = ""
            self.http_timeout = 0.0

    g_mod = types.ModuleType("goose3")
    g_mod.Goose = Goose
    cfg_mod = types.ModuleType("goose3.configuration")
    cfg_mod.Configuration = Configuration
    return {"goose3": g_mod, "goose3.configuration": cfg_mod}


class Goose3BodyLines(unittest.TestCase):
    def test_cleaned_text_split_into_lines(self):
        body = "The Lakers agreed to a three-year deal.\n\nIt reshapes their rotation.\n"
        with mock.patch.dict(sys.modules, _fake_goose3(body)):
            lines = link_facts._goose3_body_lines("https://example.com/x", "<html/>")
        self.assertEqual(
            lines, ["The Lakers agreed to a three-year deal.", "It reshapes their rotation."]
        )

    def test_empty_text_returns_empty(self):
        with mock.patch.dict(sys.modules, _fake_goose3("   ")):
            self.assertEqual(link_facts._goose3_body_lines("https://example.com/x", "<html/>"), [])

    def test_error_returns_empty(self):
        with mock.patch.dict(sys.modules, _fake_goose3("body", raises=True)):
            self.assertEqual(link_facts._goose3_body_lines("https://example.com/x", "<html/>"), [])


class ArticleFactsRouting(unittest.TestCase):
    _HTML = (
        "<html><head><title>Lakers news</title></head><body><article>"
        "<p>A BeautifulSoup fallback paragraph that runs well past the sixty character gate.</p>"
        "</article></body></html>"
    )

    def _resp(self):
        return mock.MagicMock(status_code=200, text=self._HTML)

    def test_prefers_goose3_body(self):
        goose_line = "A goose3-extracted body paragraph that also clears the sixty character gate."
        with (
            mock.patch.object(link_facts, "_goose3_body_lines", return_value=[goose_line]) as gm,
            mock.patch.object(link_facts.requests, "get", return_value=self._resp()),
        ):
            facts = link_facts._article_facts("https://sports.example.com/lakers")
        gm.assert_called_once()
        self.assertTrue(any(goose_line in f for f in facts))
        self.assertFalse(any("BeautifulSoup fallback" in f for f in facts))

    def test_falls_back_to_bs4_when_goose3_empty(self):
        with (
            mock.patch.object(link_facts, "_goose3_body_lines", return_value=[]),
            mock.patch.object(link_facts.requests, "get", return_value=self._resp()),
        ):
            facts = link_facts._article_facts("https://sports.example.com/lakers")
        self.assertTrue(any("BeautifulSoup fallback" in f for f in facts))

    def test_trade_tracker_bypasses_goose3(self):
        trade_html = (
            "<html><head><title>NBA Offseason Trade Tracker</title></head><body><article><ul>"
            "<li>Team A trades Player X to Team B in a blockbuster swap of picks</li>"
            "</ul></article></body></html>"
        )
        with (
            mock.patch.object(link_facts, "_goose3_body_lines") as gm,
            mock.patch.object(
                link_facts.requests,
                "get",
                return_value=mock.MagicMock(status_code=200, text=trade_html),
            ),
        ):
            link_facts._article_facts("https://www.cbssports.com/nba/offseason-trade-tracker/")
        gm.assert_not_called()  # trade pages keep the specialised BeautifulSoup extractor


class PublicContract(unittest.TestCase):
    def test_extract_never_raises(self):
        self.assertEqual(link_facts.extract_facts_from_url("not a url"), [])
        self.assertEqual(link_facts.extract_facts_from_url("https://www.bing.com/search?q=x"), [])


if __name__ == "__main__":
    unittest.main()
