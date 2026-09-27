"""#895: stop before the voice line when no fact names the event the topic is about.

`docs/assessment.md` weakness 1: a topic about a just-happened event (UFC "Freedom 250")
produced "Topuria, the featherweight champion" and invented opponents - the event is
past the script model's training and the signals returned nothing about it. Three
generic UFC headlines still pass the thin-facts stop (it counts lines, not what they
are about). The guard asks one question: does any fact line name what the topic names?
The name is the one every signal searched for, `topic_tokens.search_query(mode="entity")`.
"""

from __future__ import annotations

import os
import unittest
from typing import ClassVar
from unittest.mock import patch

GENERIC_UFC = "\n".join(
    [
        "UFC/MMA headlines:",
        "- Dana White says the UFC will return to Abu Dhabi in October (espn.com)",
        "- UFC signs a new broadcast deal with Paramount (mmajunkie.com)",
        "- Three fighters removed from next month's card after medicals (mmafighting.com)",
    ]
)


class CoverageTests(unittest.TestCase):
    def test_the_freedom_250_case_is_uncovered(self):
        from core.event_coverage import coverage

        result = coverage("UFC Freedom 250 results: who won", GENERIC_UFC, [])
        self.assertEqual(result["name"], "UFC Freedom 250")
        self.assertFalse(result["covered"])

    def test_a_pasted_key_fact_covers_it(self):
        from core.event_coverage import coverage

        facts = ["UFC Freedom 250 took place on June 14 at the White House lawn."]
        self.assertTrue(coverage("UFC Freedom 250 results: who won", GENERIC_UFC, facts)["covered"])

    def test_a_signal_line_covers_it(self):
        from core.event_coverage import coverage

        lines = GENERIC_UFC + "\n- Freedom 250 card: Topuria headlines the UFC event (espn.com)"
        self.assertTrue(coverage("UFC Freedom 250 results", lines, [])["covered"])

    def test_the_number_must_match(self):
        from core.event_coverage import coverage

        lines = "- UFC 319 results: du Plessis retains (espn.com)"
        self.assertFalse(coverage("UFC 320 results", lines, [])["covered"])

    def test_a_fighter_line_covers_a_rematch_topic(self):
        from core.event_coverage import coverage

        lines = "Fighter record: Topuria 17-0, featherweight"
        self.assertTrue(coverage("Topuria vs Holloway 2", lines, [])["covered"])

    def test_an_acronym_and_a_roman_numeral(self):
        from core.event_coverage import coverage

        lines = "- Grand Theft Auto VI is delayed to November 2026 (ign.com)"
        self.assertTrue(coverage("GTA 6 trailer 3 breakdown", lines, [])["covered"])

    def test_a_lowercase_topic(self):
        from core.event_coverage import coverage

        result = coverage("ufc freedom 250 results", GENERIC_UFC, [])
        self.assertFalse(result["covered"])
        self.assertTrue(
            coverage("ufc freedom 250 results", GENERIC_UFC, ["Freedom 250 ..."])["covered"]
        )

    def test_the_number_alone_is_not_the_name(self):
        """A line that shares only the number is about something else."""
        from core.event_coverage import covered

        self.assertFalse(covered("Madden 26", ["- Version 26 of the app ships today"]))

    def test_a_name_with_no_words_is_not_judged(self):
        from core.event_coverage import covered

        self.assertTrue(covered("", ["- anything"]))

    def test_no_name_means_no_verdict(self):
        from core.event_coverage import coverage

        self.assertIsNone(coverage("", GENERIC_UFC, []))


class GateTests(unittest.TestCase):
    UNCOVERED: ClassVar[dict] = {
        "event_coverage": {"name": "UFC Freedom 250", "covered": False, "lines": 4}
    }

    def test_the_reason_names_the_event(self):
        from core.event_coverage import abort_reason

        reason = abort_reason(self.UNCOVERED)
        self.assertIn("UFC Freedom 250", reason)

    def test_covered_or_missing_is_no_reason(self):
        from core.event_coverage import abort_reason

        self.assertIsNone(abort_reason({"event_coverage": {"name": "x", "covered": True}}))
        self.assertIsNone(abort_reason({}))
        self.assertIsNone(abort_reason(None))

    def test_the_gate_can_be_turned_off(self):
        from core.event_coverage import abort_reason

        with patch.dict(os.environ, {"EVENT_COVERAGE_GATE": "false"}):
            self.assertIsNone(abort_reason(self.UNCOVERED))

    def test_ops_blocking_lists_it(self):
        from core.publish_blockers import blocking_publish_reasons

        with (
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
            patch("core.cadence.cadence_status") as cadence,
        ):
            cadence.return_value.ok = True
            reasons = blocking_publish_reasons(channel_id="tapin", features=self.UNCOVERED)
        self.assertTrue(any("UFC Freedom 250" in r for r in reasons), reasons)

    def test_selftest_runs_the_gate(self):
        from core.selftest import run_selftest

        [row] = [r for r in run_selftest() if r.name == "event_coverage"]
        self.assertTrue(row.works, row)


class ContentEngineTests(unittest.TestCase):
    """The engine feeds the check: the helper alone proves nothing (#694's shape)."""

    def _package(self, key_facts: list[str]):
        from core import content_engine as ce

        script = (
            "The UFC is heading back to Abu Dhabi in October, and the new broadcast deal "
            "changes how fans will watch it. Three fighters are already off next month's "
            "card after medicals, so the lineup is still moving."
        )
        payload = {"script": script, "title": "x", "description": "d", "tags": ["ufc"]}
        with (
            patch.object(ce, "enrich_facts", return_value=GENERIC_UFC),
            patch.object(ce, "_call_content_llm", return_value=payload) as llm,
            patch.object(ce, "find_ungrounded_entities", return_value=[]),
            patch("core.claim_verifier.verify_claims", return_value=None),
            patch("core.title_generator.generate_title", return_value="UFC Freedom 250"),
            patch(
                "core.youtube_meta.check_title_script_consistency",
                return_value={"status": "passed", "passed": True, "warnings": [], "total": 1},
            ),
        ):
            pkg = ce.generate_content_package(
                "UFC Freedom 250 results: who won",
                {},
                (20, 200),
                "2026-09-27",
                channel_id="tapin",
                length_choice="1",
                key_facts=key_facts,
            )
        return pkg, llm.call_args_list[0].args[1]

    def test_uncovered_reaches_the_package_and_the_prompt(self):
        pkg, prompt = self._package([])
        self.assertEqual(pkg["event_coverage"]["name"], "UFC Freedom 250")
        self.assertFalse(pkg["event_coverage"]["covered"])
        self.assertIn("EVENT NOT IN FACTS", prompt)

    def test_a_pasted_fact_covers_it_and_the_prompt_is_quiet(self):
        pkg, prompt = self._package(["Freedom 250 was held on June 14 at the White House."])
        self.assertTrue(pkg["event_coverage"]["covered"])
        self.assertNotIn("EVENT NOT IN FACTS", prompt)


class RunWindowTests(unittest.TestCase):
    def test_the_desktop_window_treats_the_stop_as_a_gate(self):
        """The run window keys gate prompts by their exact text (Stage 1 ask bridge)."""
        from pathlib import Path

        from core.ask_bridge import EVENT_PROMPT, classify_prompt

        self.assertEqual(classify_prompt(EVENT_PROMPT), ("confirm", "event_coverage"))
        main_py = Path(__file__).resolve().parents[1] / "main.py"
        self.assertIn(repr(EVENT_PROMPT)[1:-1], main_py.read_text(encoding="utf-8"))


class PromptTests(unittest.TestCase):
    def _prompt(self, uncovered: str) -> str:
        from core.content_engine import _build_prompts

        _system, user = _build_prompts(
            topic="UFC Freedom 250 results",
            signals={},
            min_words=120,
            max_words=160,
            today="2026-09-27",
            channel_id="tapin",
            script_brief="",
            seo_block="",
            signal_facts=GENERIC_UFC,
            signal_summary="",
            brief_block="",
            length_choice="1",
            uncovered_event=uncovered,
        )
        return user

    def test_the_block_appears_only_when_uncovered(self):
        self.assertIn("EVENT NOT IN FACTS", self._prompt("UFC Freedom 250"))
        self.assertIn("'UFC Freedom 250'", self._prompt("UFC Freedom 250"))
        self.assertNotIn("EVENT NOT IN FACTS", self._prompt(""))

    def test_a_covered_run_gets_the_same_prompt_as_before(self):
        from core.content_engine import _build_prompts

        base = {
            "topic": "UFC Freedom 250 results",
            "signals": {},
            "min_words": 120,
            "max_words": 160,
            "today": "2026-09-27",
            "channel_id": "tapin",
            "script_brief": "",
            "seo_block": "",
            "signal_facts": GENERIC_UFC,
            "signal_summary": "",
            "brief_block": "",
            "length_choice": "1",
        }
        self.assertEqual(_build_prompts(**base), _build_prompts(**base, uncovered_event=""))


if __name__ == "__main__":
    unittest.main()
