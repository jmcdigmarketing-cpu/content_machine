"""Run 74: spend the prompt budget on the best facts, not the first ones.

The old rule was insertion order plus `break` on overflow. Run 74 packed 54 facts
and roughly 15 of them were article furniture — "Below, you'll find everything
shown off during the GTA 6 Extended Look:", "Check out the five biggest takeaways
below.", "Note: All of these details are compiled from various previews…" — while
the actual detail (six wanted stars, the Slim Jim minigame, the 80-hour
playthrough) sat in the tail that never fit. Raising the ceiling would have packed
more furniture. Ranking is what fixes it.

Three rules keep the change safe:
  - facts the operator typed themselves are pinned and never ranked out
    (decisions §4 makes them the highest ground truth in the system);
  - scaffolding is penalised, not blacklisted, so a boilerplate-shaped line that
    still carries a number survives;
  - every exclusion carries a reason, because a silent drop of ground truth is the
    worst failure this module can have.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from core.fact_selection import (
    FactSelectionDrop,
    scaffolding_penalty,
    select_facts_for_prompt,
)
from core.fact_store import TIER_LINK, TIER_OPERATOR, FactRecord

TODAY = date(2026, 8, 29)
TOPIC = "GTA 6 extended look"
CORPUS = (
    "Grand Theft Auto 6 extended look Netflix Rockstar Vice City Jason Lucia "
    "wanted stars carjacking release date November 19"
)

# Verbatim from run 74's packed-fact list.
SCAFFOLDING = [
    "Below, you will find everything shown off during the GTA 6 Extended Look:",
    "Check out the five biggest takeaways from the Grand Theft Auto 6 extended look below.",
    "Note: All of these details and features are compiled from various GTA 6 previews.",
    "We have gone through the Netflix Extended Look and the newly released previews.",
    "All the news, reveals, details, and more from the biggest GTA 6 showcase yet.",
]
DETAIL = [
    "Six Wanted Stars return in GTA 6, up from the five-star cap GTA 5 used.",
    "Rob Nelson said his most recent GTA 6 playthrough took around 80 hours to finish.",
    "Grand Theft Auto 6 releases on November 19 on PlayStation 5 and Xbox Series X/S.",
    "Breaking into a car now runs a Slim Jim minigame on a right-stick timed meter.",
    "The Netflix extended look ran 26 minutes, six hours before the YouTube release.",
]


def _link(claim: str, *, days_old: int = 1) -> FactRecord:
    return FactRecord(
        claim=claim,
        tier=TIER_LINK,
        source_url="https://example.com/gta6",
        verified_at=TODAY - timedelta(days=days_old),
    )


def _typed(claim: str) -> FactRecord:
    return FactRecord(claim=claim, tier=TIER_OPERATOR, verified_at=TODAY)


def _select(records, *, budget=100_000, line_cap=500):
    return select_facts_for_prompt(
        records,
        topic=TOPIC,
        corpus=CORPUS,
        budget=budget,
        line_cap=line_cap,
        today=TODAY,
    )


class TestOperatorTypedFactsArePinned(unittest.TestCase):
    """Decisions §4: what the operator typed is the highest ground truth there is."""

    def test_a_typed_fact_survives_a_budget_that_cannot_hold_everything(self):
        typed = _typed("Umar Nurmagomedov lost at UFC Shanghai by knockout.")
        records = [_link(c) for c in DETAIL] + [typed]
        kept, _ = _select(records, budget=len(typed.claim) + 40)
        self.assertIn(typed.claim, kept)

    def test_typed_facts_are_never_reported_as_dropped(self):
        typed = [_typed(f"Operator line number {i} about Grand Theft Auto 6.") for i in range(3)]
        kept, drops = _select(typed + [_link(c) for c in SCAFFOLDING], budget=400)
        dropped = {d.claim for d in drops}
        for record in typed:
            self.assertNotIn(record.claim, dropped)
            self.assertIn(record.claim, kept)


class TestRecencyIsWeightedHeavily(unittest.TestCase):
    def test_a_fresh_fact_outranks_a_stale_one_of_equal_relevance(self):
        claim = "Grand Theft Auto 6 releases on November 19 for PlayStation 5."
        fresh = _link(claim, days_old=0)
        stale = _link(claim.replace("November 19", "November 20"), days_old=120)
        kept, _ = _select([stale, fresh], budget=len(claim) + 40)
        self.assertIn(fresh.claim, kept)
        self.assertNotIn(stale.claim, kept)

    def test_an_undated_fact_is_not_punished_to_the_floor(self):
        """Most pasted facts carry no date — neutral, not last."""
        undated = FactRecord(claim=DETAIL[0], tier=TIER_LINK)
        stale = _link(SCAFFOLDING[0], days_old=200)
        kept, _ = _select([stale, undated], budget=len(DETAIL[0]) + 40)
        self.assertIn(undated.claim, kept)


class TestScaffoldingRanksBelowSubstance(unittest.TestCase):
    def test_the_run_74_furniture_loses_to_the_run_74_detail(self):
        records = [_link(c) for c in SCAFFOLDING] + [_link(c) for c in DETAIL]
        # Room for about five lines.
        budget = sum(len(c) + 2 for c in DETAIL) + 10
        kept, _ = _select(records, budget=budget)
        self.assertTrue(set(DETAIL).issubset(set(kept)), sorted(set(DETAIL) - set(kept)))

    def test_scaffolding_is_penalised_not_blacklisted(self):
        # Same furniture shape, but it carries a real number.
        with_number = "Below you will find all 150 new GTA 6 details Rockstar confirmed."
        self.assertGreater(scaffolding_penalty(SCAFFOLDING[0]), 0.0)
        self.assertLess(
            scaffolding_penalty(with_number),
            scaffolding_penalty(SCAFFOLDING[0]),
        )

    def test_a_plain_fact_carries_no_penalty(self):
        self.assertEqual(scaffolding_penalty(DETAIL[0]), 0.0)


class TestTheBudgetIsRespected(unittest.TestCase):
    def test_output_never_exceeds_the_char_budget(self):
        records = [_link(c) for c in SCAFFOLDING + DETAIL]
        budget = 300
        kept, _ = _select(records, budget=budget)
        self.assertLessEqual(sum(len(line) + 2 for line in kept), budget)

    def test_output_never_exceeds_the_line_cap(self):
        records = [_link(c) for c in SCAFFOLDING + DETAIL]
        kept, _ = _select(records, line_cap=3)
        self.assertLessEqual(len(kept), 3)

    def test_everything_fits_when_the_budget_is_generous(self):
        records = [_link(c) for c in DETAIL]
        kept, drops = _select(records)
        self.assertEqual(len(kept), len(DETAIL))
        self.assertEqual(drops, [])


class TestEveryDropIsExplained(unittest.TestCase):
    def test_drops_name_the_fact_and_the_reason(self):
        records = [_link(c) for c in SCAFFOLDING + DETAIL]
        _, drops = _select(records, budget=200)
        self.assertTrue(drops)
        for drop in drops:
            self.assertIsInstance(drop, FactSelectionDrop)
            self.assertTrue(drop.claim.strip())
            self.assertTrue(drop.reason.strip())


class TestOutputOrderIsIntakeOrder(unittest.TestCase):
    """Rank to choose, but present in the order the operator gave them."""

    def test_kept_lines_follow_the_input_order(self):
        records = [_link(c) for c in DETAIL]
        kept, _ = _select(records)
        self.assertEqual(kept, DETAIL)


class TestLongFactsStillSplitAtSentences(unittest.TestCase):
    def test_a_selected_record_is_emitted_as_whole_sentences(self):
        paragraph = " ".join(DETAIL * 2)
        kept, _ = _select([_link(paragraph)], budget=100_000)
        self.assertGreater(len(kept), 1)
        for line in kept:
            self.assertTrue(line.endswith("."), line[-40:])
        self.assertEqual(" ".join(kept), paragraph)


class TestEmptyInput(unittest.TestCase):
    def test_no_records_selects_nothing(self):
        self.assertEqual(_select([]), ([], []))


if __name__ == "__main__":
    unittest.main()
