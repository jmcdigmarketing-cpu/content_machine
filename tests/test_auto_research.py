"""#848 auto-research: read the pages the pipeline already found.

Run 98's operator asked "it should try and pull everything no?". The web_search
signal returned six results with URLs and nothing ever opened them; only pages the
operator pasted were read. `core/auto_research.attach_web_research` reads the top
result pages for the chosen angle, drops lines with no contact with the angle, and
attaches them as a `web_research` signal at web tier - never operator tier, never
pinned. On by default (operator decision 2026-09-26); the suite pins it off.
No network: the page extractor is always a fake.
"""

from __future__ import annotations

import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from apis.signal_contract import make_signal

ANGLE = "Premier League's future hinges on how City's violations are punished."
TOPIC = "Manchester City ofund guilty, what does this mean for the prem"

PAGES = {
    "https://news.example.com/city-verdict": [
        "Manchester City were found guilty of 114 of the 115 Premier League charges.",
        "Marvel Rivals Season 4 adds Blade to the roster with a new team-up.",
    ],
    "https://sport.example.com/sanctions": [
        "A separate commission will decide City's sanctions, which could include a points deduction.",
    ],
}


def _signals(results=None):
    results = (
        results
        if results is not None
        else [
            {
                "title": "City guilty verdict",
                "url": "https://news.example.com/city-verdict",
                "snippet": "114 charges",
            },
            {"title": "", "url": "", "snippet": "no url"},
            {"title": "Video", "url": "https://www.youtube.com/watch?v=abc", "snippet": "clip"},
            {"title": "Pasted page", "url": "https://pasted.example.com/a", "snippet": "City"},
            {
                "title": "City sanctions next",
                "url": "https://sport.example.com/sanctions",
                "snippet": "points deduction",
            },
        ]
    )
    return {
        "web_search": make_signal(
            connected=True,
            active=True,
            score=92,
            data={"provider": "tavily", "answer": "", "results": results},
        )
    }


def _fake_extract(url, *, max_lines=None):
    return list(PAGES.get(url, [])), {"title": url, "found": len(PAGES.get(url, []))}


def _attach(signals, **kwargs):
    from core.auto_research import attach_web_research

    with (
        patch("core.link_facts._article_extract", side_effect=_fake_extract) as extract,
        patch("core.auto_research.get_cached", return_value=None),
        patch("core.auto_research.set_cache"),
    ):
        new, report = attach_web_research(
            signals,
            angle=ANGLE,
            topic=TOPIC,
            exclude_urls=["https://pasted.example.com/a"],
            **kwargs,
        )
    return new, report, extract


class TestAttach(unittest.TestCase):
    def test_reads_result_pages_and_keeps_on_topic_lines(self) -> None:
        new, report, extract = _attach(_signals())
        fetched = {c.args[0] for c in extract.call_args_list}
        self.assertEqual(fetched, set(PAGES), "empty, YouTube and pasted URLs are skipped")
        lines = new["web_research"]["data"]["lines"]
        self.assertTrue(any("114 of the 115" in line for line in lines))
        self.assertTrue(any("points deduction" in line for line in lines))
        self.assertFalse(any("Marvel Rivals" in line for line in lines))
        self.assertEqual(report["pages"], 2)
        self.assertEqual(report["off_topic"], 1)

    def test_the_discovery_signals_are_not_mutated(self) -> None:
        signals = _signals()
        new, _report, _ = _attach(signals)
        self.assertNotIn("web_research", signals)
        self.assertIn("web_research", new)

    def test_no_web_results_is_a_no_op_without_network(self) -> None:
        signals = {}
        new, report, extract = _attach(signals)
        extract.assert_not_called()
        self.assertNotIn("web_research", new)
        self.assertEqual(report["reason"], "no web results")

    def test_the_composite_is_untouched(self) -> None:
        new, _report, _ = _attach(_signals())
        self.assertEqual(new["web_research"]["score"], 0)

    def test_a_slow_page_gives_a_partial_result(self) -> None:
        from core.auto_research import attach_web_research

        release = threading.Event()

        def slow(url, *, max_lines=None):
            if "sanctions" in url:
                release.wait(5)
            return _fake_extract(url)

        with (
            patch("core.link_facts._article_extract", side_effect=slow),
            patch("core.auto_research.get_cached", return_value=None),
            patch("core.auto_research.set_cache"),
            patch.dict(os.environ, {"AUTO_RESEARCH_DEADLINE_S": "0.3"}, clear=False),
        ):
            started = time.monotonic()
            new, report = attach_web_research(_signals(), angle=ANGLE, topic=TOPIC)
            elapsed = time.monotonic() - started
        release.set()
        self.assertLess(elapsed, 2.0)
        self.assertEqual(report["reason"], "deadline")
        self.assertTrue(
            any("114 of the 115" in line for line in new["web_research"]["data"]["lines"])
        )


class TestTiers(unittest.TestCase):
    def test_every_line_is_web_tier(self) -> None:
        from core.facts.store import TIER_WEB
        from core.grounding_tiers import _tag_signal_facts
        from core.signal_facts import format_signal_facts

        new, _report, _ = _attach(_signals())
        text = format_signal_facts({"web_research": new["web_research"]})
        self.assertIn("Web research", text)
        tiers = {tier for tier, line in _tag_signal_facts(text) if line.strip()}
        self.assertEqual(tiers, {TIER_WEB})


class TestPipelineHook(unittest.TestCase):
    def _run(self, flag: str):
        from core.pipeline import DiscoveryResult, run_pipeline

        discovery = DiscoveryResult(
            input_topic=TOPIC,
            base_signals=_signals(),
            evaluated=[(ANGLE, 94.6, _signals())],
            channel_id="tapin",
        )
        with (
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=42),
            patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")),
            patch("core.pipeline.generate_content_package") as content,
            patch(
                "core.pipeline.attach_web_research",
                side_effect=lambda s, **k: (dict(s), {"pages": 0, "reason": "test"}),
            ) as attach,
            patch.dict(os.environ, {"AUTO_RESEARCH_ENABLED": flag}, clear=False),
        ):
            content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
            result = run_pipeline(
                TOPIC, discovery=discovery, variant_index=0, proceed_video=False, channel_id="tapin"
            )
        return attach, result

    def test_on_reads_for_the_chosen_angle(self) -> None:
        attach, result = self._run("true")
        attach.assert_called_once()
        self.assertEqual(attach.call_args.kwargs["angle"], ANGLE)
        self.assertEqual(result.features.get("auto_research", {}).get("reason"), "test")

    def test_off_never_reads(self) -> None:
        attach, _result = self._run("false")
        attach.assert_not_called()


if __name__ == "__main__":
    unittest.main()
