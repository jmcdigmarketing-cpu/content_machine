"""#899: when no fact names the event, go and look before stopping the run.

Wave 43's guard (#895) can only notice that no verified fact names what the topic names
("UFC Freedom 250") and stop before the voice. The operator asked the obvious next
question: shouldn't it pull more data first? The web search signal searches the whole
typed topic, returns six results with no recency window (Tavily ran without `days`,
DuckDuckGo without a time limit), and auto-research only reads those pages. Nothing
fetched Wikipedia text or searched news by the event's name.

`core/event_research` runs only on a miss: Wikipedia (the article whose title names the
event), Google News RSS for the last seven days, and the configured web provider with
the name and a seven-day window. It keeps only lines about the event, attaches them at
web tier, and re-checks. No network here: every source is a fixture.
"""

from __future__ import annotations

import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apis.signal_contract import make_signal

TOPIC = "UFC Freedom 250 results: who won"
NAME = "UFC Freedom 250"

GENERIC = make_signal(
    connected=True,
    active=True,
    score=40,
    data={
        "headlines": [
            {"title": "Dana White says the UFC will return to Abu Dhabi", "source": "espn.com"},
            {"title": "UFC signs a new broadcast deal", "source": "mmajunkie.com"},
            {"title": "Three fighters removed from next month's card", "source": "mmafighting.com"},
        ]
    },
)
SIGNALS = {"news": GENERIC}

WIKI_SEARCH = {"query": {"search": [{"title": "UFC Freedom 250"}, {"title": "UFC 250"}]}}
WIKI_EXTRACT = {
    "query": {
        "pages": {
            "1": {
                "title": "UFC Freedom 250",
                "extract": (
                    "UFC Freedom 250 was a mixed martial arts event produced by the Ultimate "
                    "Fighting Championship that took place on June 14, 2026, at the White House. "
                    "The event was headlined by a lightweight bout between Ilia Topuria and "
                    "Justin Gaethje."
                ),
            }
        }
    }
}
NEWS_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Topuria knocks out Gaethje at UFC Freedom 250 - ESPN</title>
<pubDate>Sun, 14 Jun 2026 23:10:00 GMT</pubDate><source url="https://espn.com">ESPN</source></item>
<item><title>Stock markets close higher on Friday - Reuters</title>
<pubDate>Fri, 12 Jun 2026 20:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
</channel></rss>"""


def _fake_get(url, params=None, **_kw):
    params = params or {}
    if "wikipedia.org" in url and params.get("list") == "search":
        return SimpleNamespace(status_code=200, json=lambda: WIKI_SEARCH, text="")
    if "wikipedia.org" in url:
        return SimpleNamespace(status_code=200, json=lambda: WIKI_EXTRACT, text="")
    if "news.google.com" in url:
        return SimpleNamespace(status_code=200, text=NEWS_RSS, json=dict)
    raise AssertionError(f"unexpected url {url}")


class ResearchCase(unittest.TestCase):
    def setUp(self) -> None:
        self._patches = [
            patch.dict(os.environ, {"EVENT_RESEARCH_ENABLED": "true"}),
            patch("core.event_research.get_cached", return_value=None),
            patch("core.event_research.set_cache"),
            patch("apis.web_search_api.search_recent", return_value=[]),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()


class ResearchTests(ResearchCase):
    def test_a_miss_is_researched_and_becomes_covered(self):
        from core.event_research import attach_event_research

        with patch("core.event_research.requests.get", side_effect=_fake_get):
            signals, report = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        self.assertEqual(report["name"], NAME)
        self.assertFalse(report["before"])
        self.assertTrue(report["after"])
        lines = signals["event_research"]["data"]["lines"]
        self.assertTrue(any("White House" in line for line in lines))
        self.assertTrue(any("Topuria knocks out Gaethje" in line for line in lines))
        self.assertEqual(set(report["sources"]), {"Wikipedia", "Google News"})

    def test_off_topic_results_are_dropped(self):
        from core.event_research import attach_event_research

        with patch("core.event_research.requests.get", side_effect=_fake_get):
            signals, _ = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        lines = signals["event_research"]["data"]["lines"]
        self.assertFalse(any("Stock markets" in line for line in lines))
        # "UFC 250" (2020) is a different event: its article is never read.
        self.assertEqual(
            [c.kwargs["params"].get("titles") for c in self._extract_calls()], ["UFC Freedom 250"]
        )

    def _extract_calls(self):
        from core.event_research import attach_event_research

        with patch("core.event_research.requests.get", side_effect=_fake_get) as get:
            attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        return [c for c in get.call_args_list if c.kwargs.get("params", {}).get("prop")]

    def test_a_covered_topic_makes_no_call(self):
        from core.event_research import attach_event_research

        covered = dict(SIGNALS, web_research=make_signal(
            connected=True, active=True, data={"lines": ["UFC Freedom 250 is set for June 14."]}
        ))  # fmt: skip
        with patch("core.event_research.requests.get") as get:
            signals, report = attach_event_research(covered, topic=TOPIC, key_facts=[])
        get.assert_not_called()
        self.assertIsNone(report)
        self.assertNotIn("event_research", signals)

    def test_every_source_failing_stays_uncovered_and_never_raises(self):
        from core.event_research import attach_event_research

        with patch("core.event_research.requests.get", side_effect=OSError("offline")):
            signals, report = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        self.assertFalse(report["after"])
        self.assertEqual(report["lines"], 0)
        self.assertNotIn("event_research", signals)

    def test_nothing_found_is_not_cached(self):
        """An outage must not hide the event for the cache's three hours."""
        from core import event_research

        with (
            patch("core.event_research.requests.get", side_effect=OSError("offline")),
            patch("core.event_research.set_cache") as store,
        ):
            event_research.research_event(NAME)
        store.assert_not_called()

    def test_a_find_is_cached(self):
        from core import event_research

        with (
            patch("core.event_research.requests.get", side_effect=_fake_get),
            patch("core.event_research.set_cache") as store,
        ):
            event_research.research_event(NAME)
        store.assert_called_once()

    def test_the_deadline_is_honoured(self):
        from core.event_research import attach_event_research

        def slow(url, params=None, **kw):
            time.sleep(2.0)
            return _fake_get(url, params, **kw)

        with (
            patch.dict(os.environ, {"EVENT_RESEARCH_DEADLINE_S": "0.3"}),
            patch("core.event_research.requests.get", side_effect=slow),
        ):
            started = time.monotonic()
            _signals, report = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertFalse(report["after"])

    def test_off_means_no_call(self):
        from core.event_research import attach_event_research

        with (
            patch.dict(os.environ, {"EVENT_RESEARCH_ENABLED": "false"}),
            patch("core.event_research.requests.get") as get,
        ):
            _signals, report = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        get.assert_not_called()
        self.assertIsNone(report)

    def test_the_lines_reach_the_facts_at_web_tier(self):
        from core.event_research import attach_event_research
        from core.facts.store import TIER_WEB
        from core.grounding_tiers import _tag_signal_facts
        from core.signal_facts import format_signal_facts

        with patch("core.event_research.requests.get", side_effect=_fake_get):
            signals, _ = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        text = format_signal_facts({"event_research": signals["event_research"]})
        self.assertIn("Event research", text)
        tiers = {tier for tier, line in _tag_signal_facts(text) if line.strip()}
        self.assertEqual(tiers, {TIER_WEB})


class WebProviderTests(unittest.TestCase):
    def test_tavily_is_asked_for_the_last_seven_days(self):
        from apis import web_search_api

        resp = SimpleNamespace(status_code=200, text="", json=lambda: {"results": []})
        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "k", "WEB_SEARCH_BACKEND": ""}),
            patch("apis.web_search_api.get_cached", return_value=None),
            patch("apis.web_search_api.set_cache"),
            patch.object(web_search_api.requests, "post", return_value=resp) as post,
        ):
            web_search_api.search_recent(NAME, days=7)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["query"], NAME)
        self.assertEqual(body["days"], 7)

    def test_no_provider_means_no_results(self):
        from apis import web_search_api

        with patch.dict(
            os.environ,
            {"TAVILY_API_KEY": "", "BRAVE_SEARCH_API_KEY": "", "BRAVE_API_KEY": "",
             "WEB_SEARCH_BACKEND": ""},
        ):  # fmt: skip
            self.assertEqual(web_search_api.search_recent(NAME), [])

    def test_web_results_naming_the_event_are_kept(self):
        from core.event_research import attach_event_research

        results = [
            {"title": "UFC Freedom 250 results: Topuria wins", "snippet": "Full card results.",
             "url": "https://example.com/a"},
            {"title": "Best budget laptops", "snippet": "Our picks.", "url": "https://example.com/b"},
        ]  # fmt: skip
        with (
            patch.dict(os.environ, {"EVENT_RESEARCH_ENABLED": "true"}),
            patch("core.event_research.get_cached", return_value=None),
            patch("core.event_research.set_cache"),
            patch("core.event_research.requests.get", side_effect=OSError("offline")),
            patch("apis.web_search_api.search_recent", return_value=results),
            patch("core.auto_research._read", return_value=[]),
        ):
            signals, report = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        lines = signals["event_research"]["data"]["lines"]
        self.assertTrue(any("Topuria wins" in line for line in lines))
        self.assertFalse(any("laptops" in line for line in lines))
        self.assertEqual(report["sources"], ["Web search"])


class PipelineTests(ResearchCase):
    def test_the_pipeline_feeds_the_lines_to_the_script(self):
        from core.pipeline import DiscoveryResult, run_pipeline

        discovery = DiscoveryResult(
            input_topic=TOPIC, base_signals=SIGNALS, evaluated=[(TOPIC, 90.0, SIGNALS)],
            channel_id="tapin",
        )  # fmt: skip
        with (
            patch("core.event_research.requests.get", side_effect=_fake_get),
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=42),
            patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")),
            patch("core.pipeline.generate_content_package") as content,
            patch.dict(os.environ, {"AUTO_RESEARCH_ENABLED": "false"}),
        ):
            content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
            result = run_pipeline(
                TOPIC, discovery=discovery, variant_index=0, proceed_video=False, channel_id="tapin"
            )
        sent = content.call_args.kwargs["signals"]
        self.assertIn("event_research", sent)
        self.assertTrue(result.features["event_research"]["after"])

    def test_the_content_engine_sees_them_as_covering_the_event(self):
        from core.content_engine import _split_facts_block
        from core.event_coverage import coverage
        from core.event_research import attach_event_research
        from core.signal_facts import format_signal_facts

        with patch("core.event_research.requests.get", side_effect=_fake_get):
            signals, _ = attach_event_research(SIGNALS, topic=TOPIC, key_facts=[])
        verified, _ = _split_facts_block(format_signal_facts(signals))
        self.assertTrue(coverage(TOPIC, verified, [])["covered"])


class PromptTests(ResearchCase):
    def _prompt(self, get):
        from core.ui import prompt_key_facts_result

        printed: list[str] = []
        with (
            patch("core.event_research.requests.get", side_effect=get),
            patch("core.obsidian_facts.load_fact_records", return_value=[]),
        ):
            prompt_key_facts_result(
                TOPIC,
                "tapin",
                signals=SIGNALS,
                print_fn=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: "",
            )
        return "\n".join(printed)

    def test_the_prompt_says_what_it_found(self):
        text = self._prompt(_fake_get)
        self.assertIn("naming 'UFC Freedom 250'", text)
        self.assertIn("Wikipedia", text)

    def test_the_prompt_asks_for_a_link_when_nothing_is_found(self):
        text = self._prompt(lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
        self.assertIn("Nothing online names 'UFC Freedom 250' yet", text)
        self.assertIn("paste a link", text)


if __name__ == "__main__":
    unittest.main()
