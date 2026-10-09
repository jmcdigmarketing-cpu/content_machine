"""#1004: news and auto-research search the subject, not the sentence.

Run 118: auto-research read Los Angeles ballot-measure pages for an NFL topic, and the "News
headlines" fact block was iPhone, Apple Watch and Uber stories - `news` sent NewsAPI the
whole typed sentence (`apis/news_api.get_news_score(topic)`), and fed 0 of the last 4
scripts. Run 124 sent "How the 0-4 chargers can turn it around this year".

- `apis.topic_tokens.subject_terms`: the teams a topic names (lower-case too) and its real
  name phrases; `subject_markers` adds each name's distinctive last word ("Chargers").
- `news` queries the quoted names (`"A" OR "B"`), else the topic's keywords, and keeps only
  headlines that name the subject; the rest are counted in the status line.
- Auto-research drops a page none of whose lines names the subject (counted off-topic).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from apis.signal_contract import make_signal

TOPIC = "How the 0-4 chargers can turn it around this year"


class SubjectTermsTests(unittest.TestCase):
    def test_terms(self):
        from apis.topic_tokens import subject_markers, subject_terms

        self.assertEqual(subject_terms(TOPIC), ["Los Angeles Chargers"])
        self.assertIn("Chargers", subject_markers(subject_terms(TOPIC)))
        self.assertEqual(subject_terms("best budget gaming mice"), [])


def _articles(*titles):
    return {"status": "ok", "articles": [
        {"title": t, "source": {"name": "S"}, "description": ""} for t in titles]}  # fmt: skip


class NewsTests(unittest.TestCase):
    def _news(self, topic, payload):
        from apis import news_api

        calls: list[dict] = []

        def fake_get(url, params=None, timeout=None):
            calls.append({"url": url, "params": params or {}})
            return SimpleNamespace(status_code=200, json=lambda: payload, text="")

        with (
            patch.dict("os.environ", {"NEWS_API_KEY": "k"}),
            patch.object(news_api.requests, "get", side_effect=fake_get),
            patch.object(news_api, "drift", return_value=None),
        ):
            return news_api.get_news_score(topic), calls

    def test_run_124_asks_for_the_team_and_keeps_its_headlines(self):
        payload = _articles(
            "Apple's new iPhone lineup leaks ahead of launch",
            "Chargers' Herbert vows to fix turnovers before Broncos game",
            "Uber cuts prices in Los Angeles",
        )
        signal, calls = self._news(TOPIC, payload)
        self.assertEqual(calls[0]["params"]["q"], '"Los Angeles Chargers"')
        titles = [h["title"] for h in signal["data"]["headlines"]]
        self.assertEqual(len(titles), 1)
        self.assertIn("Herbert", titles[0])
        self.assertIn("2 off-topic", signal["status_detail"])

    def test_no_names_falls_back_to_keywords(self):
        _signal, calls = self._news("best budget gaming mice", _articles("Budget gaming mice"))
        self.assertEqual(calls[0]["params"]["q"], "best budget gaming mice")


PAGES = {
    "https://la.example.com/ballot": ["Los Angeles voters weigh Measure ULA changes this fall."],
    "https://nfl.example.com/chargers": [
        "The Chargers are 0-4 for the first time since 2017.",
        "Herbert has thrown six interceptions.",
    ],
}


class AutoResearchTests(unittest.TestCase):
    def test_a_page_that_never_names_the_subject_is_dropped(self):
        from core.auto_research import attach_web_research

        results = [{"title": "LA ballot", "url": "https://la.example.com/ballot", "snippet": ""},
                   {"title": "Chargers", "url": "https://nfl.example.com/chargers",
                    "snippet": ""}]  # fmt: skip
        signals = {"web_search": make_signal(connected=True, active=True, score=90,
                                             data={"results": results})}  # fmt: skip

        def extract(url, *, max_lines=None):
            return list(PAGES.get(url, [])), {"title": url}

        with (
            patch("core.link_facts._article_extract", side_effect=extract),
            patch("core.auto_research.get_cached", return_value=None),
            patch("core.auto_research.set_cache"),
            patch.dict("os.environ", {"AUTO_RESEARCH_ENABLED": "true"}),
        ):
            _new, report = attach_web_research(signals, angle=TOPIC, topic=TOPIC)
        kept = "\n".join(report.get("kept_lines") or [])
        self.assertIn("0-4", kept)
        self.assertNotIn("Measure ULA", kept)
        self.assertGreaterEqual(report["off_topic"], 1)


if __name__ == "__main__":
    unittest.main()
