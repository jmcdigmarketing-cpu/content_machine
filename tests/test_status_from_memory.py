"""#966: the script cannot state where someone plays, or what they hold, from memory.

#963 puts "current team: Los Angeles Lakers (Wikidata, as of ...)" into VERIFIED FACTS. Three
gaps would still let a stale team through:

- the script prompt let real people and athletes in from memory (cross-genre framing) and
  its anti-memory rule named champion, record and ranking - not team, title or job;
- the claim verifier's extraction list had no affiliations, and an LLM-written research
  brief line counted as support, so a brief written from memory could "back" a stale claim;
- the length expansion asked for "more specific facts about what happened" with no facts.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

BASE = {
    "topic": "Is LeBron James done?",
    "signals": {},
    "min_words": 120,
    "max_words": 160,
    "today": "2026-10-05",
    "channel_id": "tapin",
    "script_brief": "brief",
    "seo_block": "",
    "signal_facts": "",
    "signal_summary": "",
    "brief_block": "",
    "length_choice": "2",
}


class PromptTests(unittest.TestCase):
    def test_current_team_or_title_only_from_the_facts(self):
        from core.content_engine import _build_prompts

        system, _user = _build_prompts(**BASE)
        self.assertIn("current team", system)
        self.assertRegex(system, r"current team[^\n]*only|only[^\n]*current team")

    def test_the_cross_genre_allowance_keeps_the_team_rule(self):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(**BASE, creative_brief="LeBron as a raid boss")
        exemption = next(line for line in system.splitlines() if "Cross-genre framing" in line)
        self.assertIn("current team", exemption)
        self.assertIn("current team", user.split("EDITORIAL ANGLE", 1)[1][:1200])


FACTS = (
    "Reference data - Wikidata, current as of 2026-10-05 (who plays where):\n"
    "  • LeBron James (American basketball player) - current team: Los Angeles Lakers "
    "(Wikidata, as of 2026-10-05)\n"
    "Research brief: LeBron James plays for the Cleveland Cavaliers"
)
BRIEF = {"Research brief: LeBron James plays for the Cleveland Cavaliers"}


def _verdict(claims):
    return {"claims": claims}


class VerifierTests(unittest.TestCase):
    def _verify(self, claims, weak):
        from core.claim_verifier import verify_claims

        with (
            patch("core.claim_verifier.verifier_enabled", return_value=True),
            patch("core.llm_router.complete_json", return_value=_verdict(claims)) as llm,
        ):
            result = verify_claims("LeBron James plays for the Cavaliers.", FACTS, topic="t",
                                   weak_lines=weak)  # fmt: skip
        return result, llm

    def test_a_claim_backed_only_by_the_brief_is_unsupported(self):
        result, _llm = self._verify(
            [{"claim": "LeBron James plays for the Cavaliers", "supported": True,
              "citation": 3, "type": "other"}], BRIEF)  # fmt: skip
        self.assertEqual([c.claim for c in result.unsupported],
                         ["LeBron James plays for the Cavaliers"])  # fmt: skip

    def test_a_claim_backed_by_wikidata_stays_supported(self):
        result, _llm = self._verify(
            [{"claim": "LeBron James plays for the Lakers", "supported": True,
              "citation": 2, "type": "other"}], BRIEF)  # fmt: skip
        self.assertEqual(result.unsupported, [])

    def test_a_hedged_rumor_on_the_brief_is_left_alone(self):
        result, _llm = self._verify(
            [{"claim": "LeBron reportedly could join the Cavaliers", "supported": True,
              "citation": 3, "type": "rumor"}], BRIEF)  # fmt: skip
        self.assertEqual(result.unsupported, [])

    def test_the_verifier_is_asked_about_affiliations(self):
        _result, llm = self._verify([], BRIEF)
        system = llm.call_args.kwargs["system"]
        self.assertIn("plays for", system)


class ExpandTests(unittest.TestCase):
    def test_the_expansion_sees_the_verified_facts_and_not_youtube_titles(self):
        from core.content_engine import _expand_script

        facts = (
            "Reference data - Wikidata, current as of 2026-10-05:\n"
            "  • LeBron James - current team: Los Angeles Lakers\n"
            "YouTube — real video titles (context only):\n"
            "  → LEBRON TO THE KNICKS?? (shocking)\n"
        )
        with patch("core.content_engine.complete_json", return_value={"script": ""}) as llm:
            _expand_script(script="Short.", topic="t", min_words=100, max_words=150,
                           length_choice="2", facts=facts)  # fmt: skip
        prompt = llm.call_args.args[0]
        self.assertIn("current team: Los Angeles Lakers", prompt)
        self.assertNotIn("KNICKS", prompt)
        self.assertIn("VERIFIED FACTS", prompt)


if __name__ == "__main__":
    unittest.main()
