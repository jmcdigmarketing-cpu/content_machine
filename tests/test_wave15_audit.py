"""Audit of waves 14/15 (run 76). Each test was observed failing on unmodified b872736.

Defects the wave-14/15 tests could not see: they only asserted the run 76 strings, so an
edit that deleted working behaviour next to the fix stayed green.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch


class TestQuestionWordsStillTrimFromEntities(unittest.TestCase):
    """Wave 14 added Start/Read/Compare/Restricted by *replacing* what/why/how/who/which/
    that/this/these (run 66's fix), so "Why Jason Duval" became an entity again."""

    def test_sentence_initial_question_words_are_not_part_of_the_name(self):
        from core.fact_grounding import extract_entities

        cases = {
            "Why Jason Duval matters.": "Jason Duval",
            "What Rockstar Games did next shocked everyone.": "Rockstar Games",
            "This Rockstar Games move is bold.": "Rockstar Games",
            "Who Jon Jones fights next is the question.": "Jon Jones",
        }
        for sentence, name in cases.items():
            self.assertEqual(extract_entities(sentence), [name], sentence)

    def test_the_wave_14_verbs_still_trim(self):
        from core.fact_grounding import extract_entities

        self.assertEqual(extract_entities("Compare Red Dead to it."), ["Red Dead"])


class TestHeuristicTitleCheckReadsTitleCase(unittest.TestCase):
    """#748's fallback ran proper-noun extraction on a Title Case title, so a title that
    says exactly what the script says came back 'failed' — every word looks like a name."""

    SCRIPT = (
        "Rockstar is fighting drones and hackers to protect GTA 6 secrets. "
        "Leaks keep coming, and the studio is spending on security."
    )

    def _check(self, title: str, script: str):
        from core.youtube_meta import check_title_script_consistency

        with patch("core.llm_router.complete_json", side_effect=RuntimeError("extract down")):
            return check_title_script_consistency(title, script, topic="GTA 6 leaks")

    def test_a_title_case_title_the_script_backs_passes(self):
        result = self._check(
            "Rockstar Fights Drones And Hackers To Protect GTA 6 Secrets", self.SCRIPT
        )
        self.assertEqual(result["status"], "passed", result)

    def test_a_name_the_script_never_mentions_still_fails(self):
        result = self._check(
            "Pereira Knocks Out Jones In Round One", "Jones beat Ankalaev at UFC 320."
        )
        self.assertEqual(result["status"], "failed", result)
        self.assertIn("Pereira", " ".join(result["warnings"]))


class TestChromeFilterKeepsRealFacts(unittest.TestCase):
    """#741's substring markers dropped any fact containing 'affiliate' or 'about the
    author' — including operator-pinned finance facts and 'about the authorities'."""

    def test_facts_that_merely_contain_a_marker_word_are_kept(self):
        from core.operator_facts import is_article_chrome

        for fact in (
            "Amazon's affiliate program cut commission rates to 1% in 2020.",
            "Residents complained about the authorities' response to the flood.",
        ):
            self.assertFalse(is_article_chrome(fact), fact)

    def test_real_disclosure_chrome_is_still_dropped(self):
        from core.operator_facts import is_article_chrome

        for chrome in (
            "This article contains affiliate links.",
            "We may earn an affiliate commission when you buy through links.",
            "About the author",
        ):
            self.assertTrue(is_article_chrome(chrome), chrome)


class TestAngleJudgeIsOptOutAndSuiteSilent(unittest.TestCase):
    """Wave 14 wired the cheap LLM judge into every run_discovery. The suite's discovery
    tests made 8 real `complete()` calls; there was no way to turn it off."""

    def _discover(self, topic: str, env: str):
        from core import pipeline

        with (
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.pipeline.build_registry", return_value={"youtube": {"score": 1}}),
            patch("core.pipeline.generate_variants", return_value=["v one", "v two"]),
            patch("core.angle_ranker._cheap_judge", return_value=None) as judge,
            patch.dict(
                os.environ,
                {"COMPETITOR_SYNC_ON_DISCOVERY": "off", "ANGLE_LLM_JUDGE": env},
            ),
        ):
            pipeline.run_discovery(topic, variant_limit=2, channel_id="tapin")
        return judge

    def test_flag_off_skips_the_llm_judge(self):
        self.assertFalse(self._discover("audit judge off topic", "false").called)

    def test_flag_on_asks_the_judge(self):
        self.assertTrue(self._discover("audit judge on topic", "true").called)

    def test_the_suite_defaults_the_judge_off(self):
        self.assertEqual(os.environ.get("ANGLE_LLM_JUDGE"), "false")


class TestThesisStemsNeedAWholeWord(unittest.TestCase):
    """`(?:is|...)\\b` had no leading boundary, so "This"/"analysis" opened a question stem."""

    def test_is_inside_a_word_is_not_a_question(self):
        from core.angle_ranker import _thesis_terms

        terms = _thesis_terms("This budgeting habit stays short and focused on facts")
        self.assertFalse([t for t in terms if t.startswith("is ")], terms)


if __name__ == "__main__":
    unittest.main()
