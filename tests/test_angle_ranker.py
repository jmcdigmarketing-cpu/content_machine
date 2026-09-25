"""The variant scorer does not rank, and #323 was not the fix.

`_score_variant` calls `build_registry(variant, reuse_signals=base_signals)`, and
`_VARIANT_REUSE_DEFAULT` pins *every* signal in the roster — so each variant is
scored against the base topic's signals, unchanged. `composite_score_raw` then
reads the topic string only via `infer_domain` (same domain for five framings of
one subject) and `get_historical_boost` (an exact-string lookup, so 0.0 for a
freshly generated angle). Five angles, identical inputs, one number.

Live-run 71 showed five angles at exactly 100.00 and #323 attributed that to the
0-100 clamp. Run 72 then tied at exactly **92.14** — below the ceiling, after
#323 shipped. Removing a clamp cannot separate numbers that were already equal.

This module tests the editorial ranker that does separate them, from the angle
text alone — no extra signal fetch, because re-fetching per variant is the cost
`reuse_signals` exists to avoid and would not work anyway.
"""

from __future__ import annotations

import unittest
from unittest import mock

from core.angle_ranker import rank_angles

# Run 72's five variants, verbatim from
# output/tapin/reports/intelligence_gta_6_*.json. Every one scored 92.14.
_RUN_72 = [
    "Gta 6's Vice City map size reveals Rockstar's ambitious scope creep problem",
    "Gta 6 leaks expose how community speculation is driving development delays",
    "Why Gta 6's realism push might kill the series' signature satire edge",
    "Gta 6's mobile companion app could redefine companion gaming expectations",
    "Gta 6's economy design teases a post-grind monetization revolution",
]


class TestTheRealTieIsBroken(unittest.TestCase):
    def test_run_72s_five_angles_no_longer_return_one_number(self):
        scores = rank_angles(_RUN_72, seed_topic="GTA 6 extended look")
        self.assertEqual(len(scores), len(_RUN_72))
        self.assertGreater(
            len(set(scores.values())),
            1,
            f"still a tie: {scores}",
        )

    def test_every_angle_scores_in_range(self):
        for value in rank_angles(_RUN_72, seed_topic="GTA 6").values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class TestItRanksOnThingsTheOperatorAskedFor(unittest.TestCase):
    def test_a_near_duplicate_ranks_below_the_angle_it_duplicates(self):
        """Five angles that share a thumbnail are the complaint the angle prompt
        already tries to prevent in words ('if two angles could share the same
        thumbnail, rewrite one'). Nothing measured it."""
        angles = [
            "Rockstar's delay reshapes the 2026 release calendar",
            "Rockstar's delay reshapes the 2026 release schedule",
            "The Slim Jim carjacking minigame signals a systems-first design",
        ]
        scores = rank_angles(angles, seed_topic="GTA 6 delay")
        self.assertGreater(
            scores[angles[2]],
            scores[angles[0]],
            f"the distinct angle did not win: {scores}",
        )

    def test_an_angle_that_drops_the_operators_subject_ranks_lower(self):
        """Run 48: an NBA seed produced a Marvel Rivals script. Nothing in the
        score noticed the subject had gone."""
        kept = "Wembanyama's minutes limit reshapes the Spurs' 2027 ceiling"
        drifted = "One team is quietly winning the offseason"
        scores = rank_angles([kept, drifted], seed_topic="Wembanyama 2027 projections")
        self.assertGreater(scores[kept], scores[drifted], f"subject drift unpunished: {scores}")

    def test_it_costs_no_signal_fetch(self):
        """The whole point: this must not reintroduce the per-variant refetch that
        `reuse_signals` exists to avoid (150-185s and 5x web spend per run)."""
        import apis.register_signals as rs

        with mock.patch.object(rs, "build_registry") as fetch:
            rank_angles(_RUN_72, seed_topic="GTA 6")
        fetch.assert_not_called()


class TestDegenerateInput(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(rank_angles([], seed_topic="x"), {})

    def test_a_single_angle_scores_without_peers_to_compare_against(self):
        scores = rank_angles(["Rockstar delays GTA 6 to spring"], seed_topic="GTA 6")
        self.assertEqual(len(scores), 1)

    def test_no_seed_topic_still_ranks(self):
        scores = rank_angles(_RUN_72)
        self.assertGreater(len(set(scores.values())), 1, f"still a tie: {scores}")

    def test_blank_and_duplicate_angles_do_not_crash(self):
        scores = rank_angles(["", "  ", "Same angle", "Same angle"], seed_topic="x")
        self.assertIn("Same angle", scores)


if __name__ == "__main__":
    unittest.main()
