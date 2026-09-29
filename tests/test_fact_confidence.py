"""#548: a confidence per fact, not only per source tier.

Every fact carried its tier (operator, link, web, signal, vault ...) and the vault lines
a relevance score, but nothing combined them, so a stale single-source vault line and a
freshly corroborated link line looked alike in the key-facts prompt. `core/facts/
confidence.fact_confidence` combines four things the system already measures - tier
weight, relevance, age and how many other sources say the same thing - into one 0..1
number with its parts. It ranks the facts room (#860) and is printed beside each vault
line. It decides nothing: which facts reach the script is unchanged.
"""

from __future__ import annotations

import unittest
from typing import ClassVar


class ConfidenceTests(unittest.TestCase):
    def test_tier_sets_the_base(self):
        from core.facts.confidence import fact_confidence

        operator = fact_confidence(tier="operator")
        vault = fact_confidence(tier="vault")
        self.assertGreater(operator.value, vault.value)
        self.assertEqual(fact_confidence(tier="context").value, 0.0)

    def test_low_relevance_lowers_it(self):
        from core.facts.confidence import fact_confidence

        self.assertLess(
            fact_confidence(tier="link", relevance=0.2).value,
            fact_confidence(tier="link", relevance=0.9).value,
        )

    def test_age_lowers_it(self):
        from core.facts.confidence import fact_confidence

        fresh = fact_confidence(tier="vault", age_days=3).value
        self.assertLess(fact_confidence(tier="vault", age_days=200).value, fresh)
        self.assertLess(
            fact_confidence(tier="vault", age_days=800).value,
            fact_confidence(tier="vault", age_days=200).value,
        )
        self.assertEqual(fact_confidence(tier="vault", age_days=None).value, fresh)

    def test_corroboration_raises_it_and_the_value_stays_in_range(self):
        from core.facts.confidence import fact_confidence

        alone = fact_confidence(tier="web").value
        self.assertGreater(fact_confidence(tier="web", corroborations=2).value, alone)
        self.assertLessEqual(fact_confidence(tier="operator", corroborations=9).value, 1.0)

    def test_parts_and_label(self):
        from core.facts.confidence import fact_confidence

        conf = fact_confidence(tier="link", relevance=0.9, corroborations=1, age_days=2)
        self.assertEqual(set(conf.parts), {"tier", "relevance", "age", "corroboration"})
        self.assertIn(conf.label, ("high", "medium", "low"))


class CorroborationTests(unittest.TestCase):
    LINES: ClassVar[list[tuple[str, str]]] = [
        ("Topuria beat Holloway by KO in round 3 at UFC 308.", "link:espn"),
        ("UFC 308: Topuria knocks out Holloway in the third round.", "web"),
        ("Topuria beat Holloway by KO in round 3 at UFC 308.", "link:espn"),  # same source
        ("Makhachev defends the lightweight belt.", "vault"),
    ]

    def test_other_sources_saying_the_same_count(self):
        from core.facts.confidence import corroboration_counts

        counts = corroboration_counts(self.LINES)
        self.assertEqual(counts[0], 1)  # the web line; not its own source's duplicate
        self.assertEqual(counts[1], 1)
        self.assertEqual(counts[3], 0)


class PromptTests(unittest.TestCase):
    def test_the_vault_review_prints_it(self):
        from core.facts.confidence import confidence_suffix
        from core.facts.store import FactRecord

        record = FactRecord(claim="Topuria is the champion.", tier="vault", relevance_score=0.8)
        self.assertRegex(confidence_suffix(record), r"conf 0\.\d\d")


if __name__ == "__main__":
    unittest.main()
