"""Pillar 3 (Fact Engine) — tiered grounding corpus: section tagging,
full-text parity with the legacy corpus, and the two tier lint checks."""

import unittest

from core.fact_store import TIER_BRIEF, TIER_CONTEXT, TIER_OPERATOR, TIER_SIGNAL, TIER_WEB
from core.grounding_tiers import (
    TieredCorpus,
    build_tiered_corpus,
    context_grounded_entities,
    high_stakes_low_tier,
    tier_warnings_for_script,
)

_SIGNAL_FACTS = """Tapology event: UFC 350
Tapology date: 2026-07-04
Tapology bout: Justin Gaethje vs Ilia Topuria
News headlines:
- Gaethje stops Topuria in Vegas (ESPN)
Live web search (tavily) — current facts on this topic (recent; verify specifics before stating as certainty):
  Summary: Gaethje won by TKO in round two.
  • Gaethje TKOs Topuria — full recap
YouTube — real video titles on this topic (shows what creators are covering; use as topic evidence, NOT as facts about specific events):
  • Darren Till DESTROYS Chimaev in sparring
  • Topuria next fight prediction"""


def _corpus(key_facts=None) -> TieredCorpus:
    return build_tiered_corpus(
        signal_facts=_SIGNAL_FACTS,
        brief_block="RESEARCH BRIEF: fans debate the stoppage",
        topic="Gaethje vs Topuria recap",
        seed_topic="UFC 350",
        key_facts=key_facts or [],
    )


class TestBuildCorpus(unittest.TestCase):
    def test_full_text_matches_legacy_join(self):
        key_facts = ["Gaethje TKO'd Topuria in round 2 at UFC 350"]
        corpus = build_tiered_corpus(
            signal_facts=_SIGNAL_FACTS,
            brief_block="brief",
            topic="topic",
            seed_topic="seed",
            key_facts=key_facts,
        )
        legacy = "\n".join([_SIGNAL_FACTS, "brief", "topic", "seed", *key_facts])
        self.assertEqual(corpus.full_text, legacy)

    def test_section_tiers(self):
        corpus = _corpus()
        by_line = {line.strip(): tier for tier, line in corpus.lines if line.strip()}
        self.assertEqual(by_line["Tapology event: UFC 350"], TIER_SIGNAL)
        self.assertEqual(by_line["Tapology bout: Justin Gaethje vs Ilia Topuria"], TIER_SIGNAL)
        self.assertEqual(by_line["- Gaethje stops Topuria in Vegas (ESPN)"], TIER_WEB)
        self.assertEqual(by_line["Summary: Gaethje won by TKO in round two."], TIER_WEB)
        self.assertEqual(by_line["• Darren Till DESTROYS Chimaev in sparring"], TIER_CONTEXT)
        self.assertEqual(by_line["RESEARCH BRIEF: fans debate the stoppage"], TIER_BRIEF)

    def test_key_facts_are_operator_tier(self):
        corpus = _corpus(key_facts=["Operator fact line"])
        self.assertIn((TIER_OPERATOR, "Operator fact line"), corpus.lines)

    def test_factual_text_excludes_context(self):
        corpus = _corpus()
        self.assertNotIn("Darren Till", corpus.factual_text)
        self.assertIn("Tapology event", corpus.factual_text)

    def test_trusted_text_is_operator_plus_signal(self):
        corpus = _corpus(key_facts=["Operator fact line"])
        trusted = corpus.trusted_text
        self.assertIn("Operator fact line", trusted)
        self.assertIn("Tapology bout", trusted)
        self.assertNotIn("Gaethje stops Topuria in Vegas", trusted)  # web tier
        self.assertNotIn("Darren Till", trusted)  # context tier


class TestContextGroundedEntities(unittest.TestCase):
    def test_flags_entity_only_in_youtube_titles(self):
        corpus = _corpus()
        script = "Darren Till shocked everyone this week with a statement win."
        flagged = context_grounded_entities(script, corpus)
        self.assertIn("Darren Till", flagged)

    def test_entity_in_factual_text_not_flagged(self):
        corpus = _corpus()
        script = "Justin Gaethje made his case at UFC 350."
        self.assertEqual(context_grounded_entities(script, corpus), [])

    def test_fully_ungrounded_entity_not_flagged_here(self):
        # Token grounding owns entities absent from the whole corpus.
        corpus = _corpus()
        script = "Paddy Pimblett had thoughts as always."
        self.assertEqual(context_grounded_entities(script, corpus), [])


class TestHighStakesLowTier(unittest.TestCase):
    def test_result_claim_backed_only_by_web_warns(self):
        # "Emma Frost" style: entity exists only in web/news lines, and the
        # sentence asserts a result → verify nudge.
        corpus = build_tiered_corpus(
            signal_facts="News headlines:\n- Jiri Prochazka beat Ankalaev on points (ESPN)",
            topic="light heavyweight recap",
            key_facts=[],
        )
        script = "Jiri Prochazka beat Ankalaev in a classic."
        warnings = high_stakes_low_tier(script, corpus)
        self.assertTrue(any("Jiri Prochazka" in w for w in warnings))

    def test_operator_backed_claim_is_clean(self):
        corpus = build_tiered_corpus(
            signal_facts="News headlines:\n- Jiri Prochazka beat Ankalaev on points (ESPN)",
            topic="light heavyweight recap",
            key_facts=["Jiri Prochazka beat Ankalaev by decision at UFC 350"],
        )
        script = "Jiri Prochazka beat Ankalaev in a classic."
        self.assertEqual(high_stakes_low_tier(script, corpus), [])

    def test_structured_signal_backing_is_trusted(self):
        corpus = build_tiered_corpus(
            signal_facts=(
                "ESPN live/final (use as source of truth for score and winner): "
                "Heat 101 at Celtics 99 — Final — winner: Miami Heat"
            ),
            topic="NBA finals recap",
            key_facts=[],
        )
        script = "The Miami Heat won it on the road."
        self.assertEqual(high_stakes_low_tier(script, corpus), [])

    def test_non_high_stakes_sentence_ignored(self):
        corpus = _corpus()
        script = "Fans are talking about the event all week."
        self.assertEqual(high_stakes_low_tier(script, corpus), [])


class TestTierWarnings(unittest.TestCase):
    def test_context_warning_wins_over_high_stakes_duplicate(self):
        corpus = _corpus()
        # Till is context-grounded AND in a high-stakes sentence — one warning.
        script = "Darren Till beat everyone in sparring."
        warnings = tier_warnings_for_script(script, corpus)
        till = [w for w in warnings if "Darren Till" in w]
        self.assertEqual(len(till), 1)
        self.assertIn("YouTube titles", till[0])

    def test_clean_script_no_warnings(self):
        corpus = _corpus(key_facts=["Gaethje TKO'd Topuria in round 2"])
        script = "Justin Gaethje finished Ilia Topuria in round 2."
        self.assertEqual(tier_warnings_for_script(script, corpus), [])


if __name__ == "__main__":
    unittest.main()
