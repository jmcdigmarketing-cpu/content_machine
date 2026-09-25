"""#807: ordinary recorded angle sets must not all score the same.

Wave 14 (#744) fixed the thesis-case tie (run 76 hype vs honourable mention).
Nothing replayed ordinary multi-angle sets. Traces store input_topic and
selected_topic, not the five variants, so the strings below are copied from
docs/run_76.md, idea_quality_diagnosis.md (run 72), and the 38 recorded
input/selected pairs. The suite never opens data/traces.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.angle_ranker import rank_angles, score_spread
from core.pipeline import best_variant_index

# Verbatim from docs/run_76.md.
RUN76_SEED = (
    "GTA 6 Analysis/Predictions!! Will it be the best game every? What does meeting "
    "the hype mean, is a goy candidate a failure? Long form predictions and content "
    "analysis so far"
)
RUN76_CRITERION = "GTA 6 Will It Be the Best: The One Criterion That Decides It All"
RUN76_HONOUR = "GTA 6 Predictions: The Honorable Mention That Almost Made the List"
# The other three listicle leftovers the same archive named (closest-call /
# forgotten feature) plus the hype phrasing the seed actually asked.
RUN76_ANGLES = [
    RUN76_CRITERION,
    RUN76_HONOUR,
    "GTA 6 Predictions: The Closest Call That Almost Made the Cut",
    "GTA 6: The Forgotten Feature Coming In At Number Four",
    "GTA 6 Analysis: What Meeting the Hype Actually Means",
]

# idea_quality_diagnosis.md: two of run 72's five, which tied at 92.14.
RUN72_ANGLES = [
    "Vice City map size reveals Rockstar's ambitious scope creep problem",
    "economy design teases a post-grind monetization revolution",
    "GTA 6 looks amazing!!!",
    "GTA 6 community predicts toxic meta before launch",
    "GTA 6 Extended Look Proves Hype Is Real",
]
RUN72_SEED = "GTA 6 looks amazing!!!"

# Recorded input_topic + selected_topic (runs 47, 50) plus three sibling framings
# so each set is five angles, the shape discovery actually scores.
ORDINARY = [
    (
        "NBA Free Agency Recap 7/7. Where will Lebron Go?",
        [
            "NBA Free Agency Recap 7/7. Where will Lebron Go?",
            "LeBron free agency recap: The one team that makes the most sense",
            "Where LeBron actually fits next season",
            "The rumor mill around LeBron is drowning out the cap sheet",
            "LeBron to Miami is the take nobody can stop repeating",
        ],
    ),
    (
        "Marvel Rivals adds X-Men's Jubilee in season 9: first look at gameplay",
        [
            "Marvel Rivals adds X-Men's Jubilee in season 9: first look at gameplay",
            "Marvel Rivals' Jubilee kit recycles too much from Star-Lord",
            "First look: what Jubilee actually changes in season 9",
            "Jubilee rankings among season 9 DPS",
            "Why Jubilee is the character nobody expected",
        ],
    ),
]


def _spread(angles: list[str], seed: str) -> float:
    return score_spread(rank_angles(angles, seed_topic=seed, llm_judge=False))


class TestOrdinarySetsAreNotTied(unittest.TestCase):
    def test_run76_five_angles_have_spread(self) -> None:
        """Unmodified code has no score_spread; the ImportError is the fail-first."""
        scores = rank_angles(RUN76_ANGLES, seed_topic=RUN76_SEED, llm_judge=False)
        self.assertGreater(score_spread(scores), 0.0, scores)
        honour = scores[RUN76_HONOUR]
        self.assertGreater(scores[RUN76_CRITERION], honour)
        evaluated = [(a, 100.0, {}) for a in RUN76_ANGLES]
        raw = dict.fromkeys(RUN76_ANGLES, 100.0)
        idx = best_variant_index(evaluated, raw, scores)
        self.assertNotEqual(RUN76_ANGLES[idx], RUN76_HONOUR)

    def test_run72_ordinary_gta_set_has_spread(self) -> None:
        self.assertGreater(_spread(RUN72_ANGLES, RUN72_SEED), 0.0)

    def test_recorded_ordinary_seeds_have_spread(self) -> None:
        for seed, angles in ORDINARY:
            with self.subTest(seed=seed[:40]):
                self.assertGreater(_spread(angles, seed), 0.0)

    def test_two_paraphrases_of_the_same_take_are_not_forced_apart(self) -> None:
        """Rule 7: a wider ranker must not invent a ranking between restatements."""
        a = "LeBron free agency recap: The one team that makes the most sense"
        b = "LeBron free agency recap: the one team that makes the most sense"
        scores = rank_angles([a, b], seed_topic=ORDINARY[0][0], llm_judge=False)
        self.assertLessEqual(score_spread(scores), 0.05, scores)


class TestEditorialIsWhatBreaksTheTie(unittest.TestCase):
    def test_without_leftover_penalty_the_honourable_mention_catches_up(self) -> None:
        """Rule 17: watched red if this assertion is inverted. The leftover
        penalty is the named #744 lever; stubbing it must move the honourable
        mention, not leave the scores identical to the live ranker."""
        live = rank_angles(RUN76_ANGLES, seed_topic=RUN76_SEED, llm_judge=False)
        with patch("core.angle_ranker._listicle_leftover_penalty", return_value=0.0):
            broken = rank_angles(RUN76_ANGLES, seed_topic=RUN76_SEED, llm_judge=False)
        self.assertGreater(broken[RUN76_HONOUR], live[RUN76_HONOUR], (live, broken))


if __name__ == "__main__":
    unittest.main()
