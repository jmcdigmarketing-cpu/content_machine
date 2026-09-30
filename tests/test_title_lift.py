"""#566: title patterns ranked by their lift over the channel, not their raw average.

`title_experiments.pattern_leaderboard` ranked tags by raw average engaged rate and
`winning_tags` called any tag whose raw average beat the channel's a "proven pattern" -
so three lucky colon titles outranked twelve steady questions and earned the hint shown at
variant selection. Each tag's rate is now shrunk toward the channel (#352's `shrunk_mean`,
four pseudo-videos at the channel mean) and ranked by lift over the channel; a pattern is
"proven" only with a shrunk lift of at least a point. `ops title-patterns` prints the lift.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

TAGS = {"colon": ["colon"], "question": ["question"], "plain": []}


def _outcomes():
    # 3 colon titles at 0.70, 12 questions at 0.66, 5 plain at 0.30: channel 0.576.
    return (
        [("colon", 0.70)] * 3 + [("question", 0.66)] * 12 + [("plain", 0.30)] * 5
    )  # fmt: skip


class LiftTests(unittest.TestCase):
    def setUp(self):
        from core import title_experiments as te

        te.reset_cache()
        self._patches = [
            patch.object(te, "_titled_outcomes", side_effect=lambda c: _outcomes()),
            patch.object(te, "feature_tags", side_effect=lambda t: TAGS[t]),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        from core import title_experiments as te

        for p in reversed(self._patches):
            p.stop()
        te.reset_cache()

    def test_the_steady_pattern_ranks_above_the_lucky_one(self):
        from core.title_experiments import pattern_leaderboard

        board = pattern_leaderboard("tapin", min_measured=3)
        self.assertEqual([tag for tag, _avg, _n in board], ["question", "colon"])

    def test_each_pattern_carries_its_lift(self):
        from core.title_experiments import pattern_lifts

        lifts = {row["tag"]: row for row in pattern_lifts("tapin", min_measured=3)}
        self.assertAlmostEqual(lifts["colon"]["avg"], 0.70)
        self.assertAlmostEqual(lifts["colon"]["lift"], (2.1 + 4 * 0.576) / 7 - 0.576)

    def test_a_barely_better_small_pattern_is_not_proven(self):
        from core import title_experiments as te

        outcomes = [("colon", 0.52)] * 3 + [("plain", 0.50)] * 17  # colon +2pp raw
        with patch.object(te, "_titled_outcomes", side_effect=lambda c: outcomes):
            te.reset_cache()
            self.assertEqual(te.winning_tags("tapin"), frozenset())

    def test_the_report_prints_the_lift(self):
        from core.title_experiments import display_leaderboard

        buf = io.StringIO()
        with redirect_stdout(buf):
            display_leaderboard("tapin", print_fn=print)
        self.assertIn("pp vs channel", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
