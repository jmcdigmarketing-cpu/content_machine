"""#964: settled or fresh - decided from evidence, and a fresh topic researched deeper.

Operator, 2026-10-05: a known topic should need no paste, "vs if a game has just come out it
may be harder to get accurate and useful info so i would paste articles. obviously not
hardcoded". Nothing told the two apart: the facts prompt asked the same way for both, and
the recent-news research (#899) ran only when no fact named the topic's event.

`core/facts/freshness.assess` reads what the run already found: a release date in the last
`FRESH_DAYS` (Wikidata or RAWG), no Wikipedia article or one created in the last 30 days,
a burst of Google News items in 48 hours, or event research having run on a miss. A fresh
topic gets the recent-news research for its main name without waiting for a miss. And when
web search is off or skipped, auto-research reads Google News headlines instead of nothing.
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apis.signal_contract import make_signal

TODAY = date(2026, 10, 5)


def _entity_signal(**entity):
    base = {"name": "X", "label": "X", "description": "", "released": "", "created": "",
            "has_article": True, "wikipedia_title": "X"}  # fmt: skip
    base.update(entity)
    return make_signal(
        connected=True,
        active=True,
        score=0,
        data={"names": [base["name"]], "as_of": TODAY.isoformat(), "wikidata_lines": ["x"],
              "wikipedia_lines": [], "entities": [base]},
    )  # fmt: skip


class AssessTests(unittest.TestCase):
    def _need(self, signals, **kw):
        from core.facts.freshness import assess

        return assess("topic", signals, today=TODAY, **kw)

    def test_a_game_out_four_days_is_fresh(self):
        verdict = self._need({"entity_research": _entity_signal(
            name="Ghost of Yotei", label="Ghost of Yōtei", released="2026-10-01",
            created="2024-09-24")})  # fmt: skip
        self.assertEqual(verdict["need"], "fresh")
        self.assertTrue(any("released 2026-10-01" in why for why in verdict["why"]))
        self.assertEqual(verdict["main"], "Ghost of Yōtei")

    def test_a_long_known_player_is_settled(self):
        verdict = self._need({"entity_research": _entity_signal(
            name="LeBron James", label="LeBron James", created="2003-02-11")})  # fmt: skip
        self.assertEqual(verdict["need"], "settled")
        self.assertTrue(any("2003" in why for why in verdict["why"]))

    def test_an_old_release_is_settled(self):
        verdict = self._need({"entity_research": _entity_signal(
            name="GTA V", label="Grand Theft Auto V", released="2013-09-17",
            created="2011-10-25")})  # fmt: skip
        self.assertEqual(verdict["need"], "settled")

    def test_a_new_article_is_fresh(self):
        verdict = self._need({"entity_research": _entity_signal(created="2026-09-28")})
        self.assertEqual(verdict["need"], "fresh")

    def test_no_article_at_all_is_fresh(self):
        verdict = self._need({"entity_research": _entity_signal(has_article=False, created="")})
        self.assertEqual(verdict["need"], "fresh")
        self.assertTrue(any("no Wikipedia article" in why for why in verdict["why"]))

    def test_a_rawg_release_counts_too(self):
        rawg = make_signal(connected=True, active=True, score=50,
                           data=[{"name": "Silksong", "released": "2026-09-20"}])  # fmt: skip
        self.assertEqual(self._need({"rawg": rawg})["need"], "fresh")

    def test_a_news_burst_is_fresh(self):
        signals = {"entity_research": _entity_signal(created="2003-02-11")}
        self.assertEqual(self._need(signals, news_count=5)["need"], "fresh")
        self.assertEqual(self._need(signals, news_count=1)["need"], "settled")

    def test_research_on_a_miss_means_fresh(self):
        verdict = self._need({}, event_report={"name": "UFC Freedom 250", "lines": 0})
        self.assertEqual(verdict["need"], "fresh")
        self.assertEqual(verdict["main"], "UFC Freedom 250")

    def test_nothing_looked_up_is_settled_and_says_so(self):
        verdict = self._need({})
        self.assertEqual(verdict["need"], "settled")
        self.assertEqual(verdict["looked_up"], 0)


RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Ghost of Yotei patch 1.03 fixes stutter - IGN</title><pubDate>Sat, 04 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Ghost of Yotei sales pass 3 million - VGC</title><pubDate>Sat, 04 Oct 2026 09:00:00 GMT</pubDate></item>
<item><title>Stock markets close higher - Reuters</title><pubDate>Fri, 03 Oct 2026 20:00:00 GMT</pubDate></item>
</channel></rss>"""


def _rss_get(url, params=None, **_kw):
    assert "news.google.com" in url, url
    return SimpleNamespace(status_code=200, text=RSS, json=dict)


class NewsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._patches = [
            patch("core.event_research.get_cached", return_value=None),
            patch("core.event_research.set_cache"),
            patch("core.facts.freshness.get_cached", return_value=None),
            patch("core.facts.freshness.set_cache"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()

    def test_only_headlines_naming_it_count(self):
        from core.facts.freshness import recent_news_count

        with patch("core.event_research.requests.get", side_effect=_rss_get) as get:
            self.assertEqual(recent_news_count("Ghost of Yotei"), 2)
        self.assertIn("when:2d", get.call_args.kwargs["params"]["q"])

    def test_an_outage_counts_nothing(self):
        from core.facts.freshness import recent_news_count

        with patch("core.event_research.requests.get", side_effect=OSError("offline")):
            self.assertEqual(recent_news_count("Ghost of Yotei"), 0)


class DeeperResearchTests(unittest.TestCase):
    def _attach(self, signals, research):
        from core.facts.freshness import attach_fresh_research

        with (
            patch.dict(os.environ, {"ENTITY_RESEARCH_ENABLED": "true",
                                    "EVENT_RESEARCH_ENABLED": "true"}),
            patch("core.facts.freshness.recent_news_count", return_value=0),
            patch("core.facts.freshness._today", return_value=TODAY),
            patch("core.event_research.research_event", side_effect=research) as called,
        ):  # fmt: skip
            out, verdict = attach_fresh_research(signals, topic="Ghost of Yotei review",
                                                 event_report=None)  # fmt: skip
        return out, verdict, called

    def test_a_fresh_topic_gets_recent_news_research_for_its_name(self):
        found = {"lines": ["Ghost of Yotei patch 1.03 fixes stutter"], "sources": ["Google News"],
                 "seconds": 0.1}  # fmt: skip
        signals = {"entity_research": _entity_signal(
            name="Ghost of Yotei", label="Ghost of Yōtei", released="2026-10-01")}  # fmt: skip
        out, verdict, called = self._attach(signals, lambda name, **_k: found)
        called.assert_called_once()
        self.assertEqual(called.call_args.args[0], "Ghost of Yōtei")
        self.assertEqual(out["event_research"]["data"]["lines"], found["lines"])
        self.assertEqual(verdict["deeper"]["lines"], 1)

    def test_a_settled_topic_is_not_researched_again(self):
        signals = {"entity_research": _entity_signal(created="2003-02-11")}
        out, verdict, called = self._attach(signals, lambda name, **_k: {"lines": []})
        called.assert_not_called()
        self.assertEqual(verdict["need"], "settled")
        self.assertNotIn("event_research", out)


class NewsFallbackTests(unittest.TestCase):
    def test_no_web_results_reads_google_news_instead(self):
        from core.auto_research import attach_web_research

        with (
            patch.dict(os.environ, {"AUTO_RESEARCH_NEWS_FALLBACK": "true"}),
            patch("core.event_research.get_cached", return_value=None),
            patch("core.event_research.set_cache"),
            patch("core.event_research.requests.get", side_effect=_rss_get),
        ):
            signals, report = attach_web_research(
                {}, angle="Ghost of Yotei's first patch", topic="Ghost of Yotei"
            )
        self.assertEqual(report["reason"], "news fallback")
        lines = signals["web_research"]["data"]["lines"]
        self.assertEqual(len(lines), 2)
        self.assertFalse(any("Stock markets" in line for line in lines))

    def test_the_fallback_can_be_turned_off(self):
        from core.auto_research import attach_web_research

        with (
            patch.dict(os.environ, {"AUTO_RESEARCH_NEWS_FALLBACK": "false"}),
            patch("core.event_research.requests.get", side_effect=AssertionError("no fetch")),
        ):
            signals, report = attach_web_research({}, angle="a", topic="Ghost of Yotei")
        self.assertEqual(report["reason"], "no web results")
        self.assertNotIn("web_research", signals)


class PipelineTests(unittest.TestCase):
    def test_the_run_records_the_verdict(self):
        from core.pipeline import DiscoveryResult, run_pipeline

        topic = "Ghost of Yotei review"
        signals = {"news": make_signal(connected=True, active=True, score=40,
                                       data={"headlines": []})}  # fmt: skip
        discovery = DiscoveryResult(
            input_topic=topic, base_signals=signals, evaluated=[(topic, 90.0, signals)],
            channel_id="tapin",
        )  # fmt: skip
        with (
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=42),
            patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")),
            patch("core.pipeline.generate_content_package") as content,
        ):
            content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
            result = run_pipeline(
                topic, discovery=discovery, variant_index=0, proceed_video=False, channel_id="tapin"
            )
        self.assertIn(result.features["research"]["need"], ("settled", "fresh"))


if __name__ == "__main__":
    unittest.main()
