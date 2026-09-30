"""#917: a fact conflict names the section of the corpus that lost.

`FactConflict` kept the operator line and the contradicting line, never where that line
came from, and the signal corpus is not persisted - so "your key fact beat the web search
three times this week" could never be counted. Signal lines carry no URL (web-search
lines are a title and a snippet), so the source a conflict can name is its section:
"Live web search", "News headlines", "Tapology". The run features keep
`conflict_sections`; `ops source-trust` shows the counts. Shown only - per the operator's
#342 rule, only post-publish corrections move a weight.
"""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

CORPUS = "\n".join(
    [
        "News headlines (last 48h):",
        "  • Pereira retains belt at UFC 320",
        "Live web search (tavily) — current facts on this topic (recent; verify):",
        "  Summary: busy week",
        "  • Jimmy Butler traded to the Warriors — reports say",
        "Card: Pereira vs Ankalaev",
    ]
)


class SectionTests(unittest.TestCase):
    def test_each_line_maps_to_its_section(self):
        from core.grounding_tiers import line_sections

        sections = line_sections(CORPUS)
        self.assertEqual(sections["• jimmy butler traded to the warriors — reports say"],
                         "Live web search")  # fmt: skip
        self.assertEqual(sections["• pereira retains belt at ufc 320"], "News headlines")
        self.assertEqual(sections["card: pereira vs ankalaev"], "Card")

    def test_a_conflict_names_where_the_losing_line_came_from(self):
        from core.facts.conflicts import find_fact_conflicts

        conflicts = find_fact_conflicts(
            ["Jimmy Butler was traded to the Heat"], CORPUS, sections=True
        )
        self.assertTrue(conflicts)
        self.assertEqual(conflicts[0].section, "Live web search")

    def test_vault_claims_have_no_section(self):
        from core.facts.conflicts import find_fact_conflicts

        conflicts = find_fact_conflicts(
            ["Jimmy Butler was traded to the Heat"], "Jimmy Butler traded to the Warriors"
        )
        self.assertEqual([c.section for c in conflicts], [""])

    def test_the_features_keep_the_sections(self):
        from core.facts.conflicts import features_from_conflicts, find_fact_conflicts

        conflicts = find_fact_conflicts(
            ["Jimmy Butler was traded to the Heat"], CORPUS, sections=True
        )
        self.assertEqual(
            features_from_conflicts(conflicts)["conflict_sections"], ["Live web search"]
        )
        self.assertEqual(features_from_conflicts([])["conflict_sections"], [])

    def test_the_pipeline_asks_for_sections(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "core" / "content_engine.py").read_text(
            encoding="utf-8"
        )
        call = "find_fact_conflicts(clean_key_facts, signal_facts, sections=True)"
        self.assertTrue(call in text, "the pipeline does not ask for conflict sections")


class FlowTests(unittest.TestCase):
    """The field, not the call: the sections must reach the stored run features."""

    def test_both_content_payloads_carry_them(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "core" / "content_engine.py").read_text(
            encoding="utf-8"
        )
        carried = text.count('"conflict_sections": conflict_features["conflict_sections"]')
        self.assertEqual(carried, 2, "a content payload drops conflict_sections")

    # No network (the CI reverse run caught this test fetching NBA stats and RSS feeds):
    # the research brief is built from live feeds and scrapers.
    @patch("core.pipeline.build_research_brief")
    @patch("core.pipeline.write_run_dossier")
    @patch("core.pipeline.write_run_trace")
    @patch("core.pipeline.persist_quality")
    @patch("core.pipeline.build_quality", return_value={})
    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=7)
    @patch("core.pipeline.generate_content_package")
    def test_the_pipeline_keeps_them(self, mock_content, *mocks):
        from core.pipeline import DiscoveryResult, run_pipeline
        from core.research_brief import ResearchBrief

        mocks[-1].return_value = ResearchBrief(topic="NBA trades")

        discovery = DiscoveryResult(
            input_topic="NBA trades", base_signals={},
            evaluated=[("NBA trades", 70.0, {})], channel_id="tapin",
        )  # fmt: skip
        mock_content.return_value = {
            "title": "T", "script": "S", "description": "D",
            "fact_conflicts": ["c"], "disputed": True, "disputed_claims": ["x"],
            "conflict_sections": ["Live web search"],
        }  # fmt: skip
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            result = run_pipeline(
                "NBA trades", discovery=discovery, proceed_video=False, channel_id="tapin"
            )
        self.assertEqual(result.features["conflict_sections"], ["Live web search"])


class ReportTests(unittest.TestCase):
    def test_ops_source_trust_counts_them(self):
        from scripts.ops import COMMANDS

        runs = [
            SimpleNamespace(id=1, features_json=json.dumps({"conflict_sections": ["Live web search", "News headlines"]})),
            SimpleNamespace(id=2, features_json=json.dumps({"conflict_sections": ["Live web search"]})),
        ]  # fmt: skip
        buf = io.StringIO()
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            redirect_stdout(buf),
        ):
            COMMANDS["source-trust"][1](Namespace(channel="tapin"))
        self.assertIn("contradicted by your key facts (shown only): Live web search 2, News headlines 1",
                      buf.getvalue())  # fmt: skip


if __name__ == "__main__":
    unittest.main()
