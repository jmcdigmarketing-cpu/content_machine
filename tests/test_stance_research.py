"""#1095: a hope or plan idea's research looks for what the stance needs.

Measured on ecd737c: auto-research reads the pages of the topic's own web search, ranked by the
angle and topic words (`core/auto_research._rank`), and the news fallback searches the event name.
Nothing looks for the positives a hope idea asks for, so run 125's facts were the 0-4 record and
the losses - the writer had no fact to give as a reason for hope, and the idea check's rewrite
(#1016) may add none. Nothing measured it either.

Now every hope or plan run counts the fact lines that back the stance (`stance_support`, on the
run record and the facts preview), and when fewer than two do, makes one stance search
(`apis.web_search_api.search_recent`) and keeps the results that name the subject and back it.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apis.signal_contract import STATUS_OK, make_signal

IDEA = "Chargers Hopeium going into week 5"
LOSSES = [
    "The Chargers lost 27-10 to the Chiefs in week 4.",
    "Los Angeles is 0-4 for the first time since 2018.",
]


def _signals(lines):
    return {
        "web_research": make_signal(
            connected=True, active=True, score=0, confidence=0.6, status=STATUS_OK,
            status_detail="test", data={"lines": list(lines), "urls": []},
        )
    }  # fmt: skip


def _on(**extra):
    return patch.dict(os.environ, {"STANCE_RESEARCH": "true", **extra})


class LineTests(unittest.TestCase):
    def test_reasons_for_hope_are_found_and_losses_are_not(self):
        from core.facts.stance_support import stance_lines

        lines = [*LOSSES, "Joey Bosa returns from injury this week.",
                 "Herbert threw for a career-high 405 yards in the loss."]  # fmt: skip
        self.assertEqual(stance_lines(lines, "hope"), lines[2:])
        self.assertEqual(stance_lines(LOSSES, "hope"), [])

    def test_a_plan_looks_for_what_has_to_happen(self):
        from core.facts.stance_support import stance_lines

        line = "The Chargers need to win 8 of their remaining 13 games to reach .500."
        self.assertEqual(stance_lines([*LOSSES, line], "plan"), [line])
        self.assertEqual(stance_lines([line], "default"), [])


class ResearchTests(unittest.TestCase):
    def test_thin_support_makes_one_stance_search(self):
        from core.facts.stance_support import attach_stance_research

        results = [
            {"title": "Chargers get good news: Bosa returns for week 5", "snippet": "",
             "url": "https://example.com/a"},
            {"title": "Fantasy sleepers for week 5", "snippet": "Bosa returns.",
             "url": "https://example.com/b"},  # does not name the subject
        ]  # fmt: skip
        with (
            _on(),
            patch("core.facts.stance_support.search_recent", return_value=results) as search,
        ):
            signals, report = attach_stance_research(
                _signals(LOSSES), intent="hope", topic=IDEA, angle="Bosa is back"
            )
        search.assert_called_once()
        self.assertIn("Chargers", search.call_args.args[0])
        lines = signals["web_research"]["data"]["lines"]
        self.assertIn("Chargers get good news: Bosa returns for week 5", lines)
        self.assertNotIn("Bosa returns.", lines)
        self.assertEqual(report["intent"], "hope")
        self.assertTrue(report["searched"])
        self.assertEqual(report["added"], 1)
        self.assertEqual(report["lines"], 1)

    def test_enough_support_makes_no_search(self):
        from core.facts.stance_support import attach_stance_research

        backed = [*LOSSES, "Joey Bosa returns from injury.", "Herbert's career-high 405 yards."]
        with _on(), patch("core.facts.stance_support.search_recent") as search:
            _signals_out, report = attach_stance_research(
                _signals(backed), intent="hope", topic=IDEA, angle=""
            )
        search.assert_not_called()
        self.assertEqual((report["lines"], report["searched"]), (2, False))

    def test_neutral_and_off_make_no_search(self):
        from core.facts.stance_support import attach_stance_research

        with _on(), patch("core.facts.stance_support.search_recent") as search:
            _s, report = attach_stance_research(
                _signals(LOSSES), intent="default", topic="Chargers week 5", angle=""
            )
        search.assert_not_called()
        self.assertEqual(report, {})
        with (
            _on(STANCE_RESEARCH="false"),
            patch("core.facts.stance_support.search_recent") as search,
        ):
            _s, report = attach_stance_research(
                _signals(LOSSES), intent="hope", topic=IDEA, angle=""
            )
        search.assert_not_called()
        self.assertEqual((report["lines"], report["searched"]), (0, False))

    def test_a_search_outage_is_a_notice(self):
        from core.facts.stance_support import attach_stance_research

        with (
            _on(),
            patch("core.facts.stance_support.search_recent", side_effect=RuntimeError("down")),
        ):
            signals, report = attach_stance_research(
                _signals(LOSSES), intent="hope", topic=IDEA, angle=""
            )
        self.assertEqual(signals["web_research"]["data"]["lines"], LOSSES)
        self.assertEqual(report["added"], 0)


class NoteTests(unittest.TestCase):
    def test_the_preview_says_what_backs_the_stance(self):
        from core.facts.stance_support import stance_note

        self.assertIn("no fact here is a reason for hope", stance_note(
            {"intent": "hope", "lines": 0, "of": 9, "searched": True, "added": 0}))  # fmt: skip
        self.assertEqual(
            stance_note({"intent": "hope", "lines": 3, "of": 22, "searched": False, "added": 0}),
            "Facts for your hope: 3 of 22 lines read as reasons for hope",
        )
        self.assertEqual(stance_note({}), "")


class PipelineTests(unittest.TestCase):
    def test_the_run_passes_its_intent_and_records_the_count(self):
        from unittest.mock import MagicMock

        from core.pipeline import DiscoveryResult, run_pipeline

        discovery = DiscoveryResult(
            input_topic=IDEA, base_signals={}, evaluated=[("Bosa is back", 80.0, {})],
            channel_id="tapin",
        )  # fmt: skip
        report = {"intent": "hope", "lines": 1, "of": 3, "searched": True, "added": 1}
        with (
            patch.dict(os.environ, {"AUTO_RESEARCH_ENABLED": "false"}),
            patch(
                "core.facts.stance_support.attach_stance_research",
                side_effect=lambda signals, **_k: (signals, report),
            ) as attach,
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
                IDEA, discovery=discovery, proceed_video=False, channel_id="tapin"
            )
        self.assertEqual(attach.call_args.kwargs["intent"], "hope")
        self.assertEqual(result.features["stance_support"], report)


if __name__ == "__main__":
    unittest.main()
