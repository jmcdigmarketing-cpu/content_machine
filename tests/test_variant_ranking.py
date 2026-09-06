"""Candidate 323: a clamped score cannot rank, so rank on the real one or admit the tie.

Live-run 71 offered five angles and asked `Choose 1-5 (Enter = best)`:

    * 1. [100.0] ...  2. [100.0] ...  3. [100.0] ...  4. [100.0] ...  5. [100.0] ...

`composite_score` ends `round(min(final_score, 100), 2)`. The weighted average was
already high (blog_rss 100, autocomplete 100, twitch 98, tiktok 90, trends 86.4), and
`final_score * (0.7 + 0.3 * domain_factor) + boost` pushed every variant past the
ceiling. Once clamped they are indistinguishable, so the menu presented a tie as a
ranking and "Enter = best" picked whichever happened to sort first.

The stored 0-100 score is unchanged — `composite_score` still clamps. Only the
*ordering* and what the operator is told about it changed.
"""

import unittest
from unittest.mock import patch

from core.pipeline import best_variant_index
from core.ui import display_variants


def _ev(pairs):
    """(variant, displayed score) -> the 3-tuple shape display_variants consumes."""
    return [(v, s, {}) for v, s in pairs]


class _Lines(list):
    """Collector that tolerates `print_fn()` with no args (subsection prints blanks)."""

    def __call__(self, *args):
        self.append(args[0] if args else "")

    @property
    def text(self) -> str:
        return "\n".join(str(x) for x in self)


class TestClampStillAppliesToTheStoredScore(unittest.TestCase):
    """The 0-100 contract every consumer depends on must not move."""

    def test_composite_score_is_still_capped_at_100(self):
        from apis import topic_scorer

        with patch.object(topic_scorer, "composite_score_raw", return_value=137.4):
            self.assertEqual(topic_scorer.composite_score({}, "t", "tapin"), 100)

    def test_below_the_ceiling_is_unchanged(self):
        from apis import topic_scorer

        with patch.object(topic_scorer, "composite_score_raw", return_value=86.437):
            self.assertEqual(topic_scorer.composite_score({}, "t", "tapin"), 86.44)


class TestTieBreak(unittest.TestCase):
    """`best_variant_index` is the one ranking rule; the menu and the pipeline share it."""

    def test_run71_shape_picks_the_most_headroom(self):
        evaluated = _ev([(f"angle {i}", 100.0) for i in range(1, 6)])
        raw = {
            "angle 1": 101.0,
            "angle 2": 104.0,
            "angle 3": 137.4,
            "angle 4": 102.0,
            "angle 5": 100.5,
        }
        self.assertEqual(best_variant_index(evaluated, raw), 2)

    def test_a_visible_score_difference_always_wins_over_raw(self):
        evaluated = _ev([("a", 90.0), ("b", 100.0)])
        self.assertEqual(best_variant_index(evaluated, {"a": 500.0, "b": 100.0}), 1)

    def test_without_raw_scores_behaviour_is_the_old_one(self):
        self.assertEqual(best_variant_index(_ev([("a", 100.0), ("b", 100.0)])), 0)

    def test_partial_raw_falls_back_per_variant(self):
        evaluated = _ev([("a", 100.0), ("b", 100.0)])
        self.assertEqual(best_variant_index(evaluated, {"b": 140.0}), 1)

    def test_empty_is_refused_rather_than_returning_a_bogus_index(self):
        with self.assertRaises(ValueError):
            best_variant_index([])


class TestTheRealTieRunsOutOfTiebreakers(unittest.TestCase):
    """#323's raw-score tiebreak only works when the pre-clamp numbers differ.
    They do not: every signal is pinned during variant scoring, so all five
    variants are scored against identical inputs. Run 72 tied at 92.14 — under
    the clamp — *after* #323 shipped. The editorial score is the third key."""

    def test_equal_display_and_equal_raw_still_picks_first_without_angle_scores(self):
        evaluated = _ev([(f"angle {i}", 92.14) for i in range(1, 6)])
        raw = dict.fromkeys((v for v, *_ in evaluated), 92.14)
        self.assertEqual(best_variant_index(evaluated, raw), 0)

    def test_the_editorial_score_breaks_a_total_tie(self):
        evaluated = _ev([("angle a", 92.14), ("angle b", 92.14), ("angle c", 92.14)])
        raw = dict.fromkeys((v for v, *_ in evaluated), 92.14)
        angle_scores = {"angle a": 0.41, "angle b": 0.88, "angle c": 0.55}
        self.assertEqual(best_variant_index(evaluated, raw, angle_scores), 1)

    def test_a_visible_score_difference_still_outranks_the_editorial_score(self):
        """Order of authority is unchanged: displayed, then raw, then editorial."""
        evaluated = _ev([("a", 90.0), ("b", 100.0)])
        self.assertEqual(best_variant_index(evaluated, {}, {"a": 0.99, "b": 0.01}), 1)

    def test_raw_still_outranks_the_editorial_score(self):
        evaluated = _ev([("a", 100.0), ("b", 100.0)])
        self.assertEqual(
            best_variant_index(evaluated, {"a": 140.0, "b": 100.0}, {"a": 0.01, "b": 0.99}),
            0,
        )


class TestMenuUsesTheSameRule(unittest.TestCase):
    def test_display_returns_the_headroom_winner(self):
        evaluated = _ev([("a", 100.0), ("b", 100.0), ("c", 100.0)])
        best = display_variants(
            evaluated, raw_scores={"a": 101.0, "b": 140.0, "c": 105.0}, print_fn=_Lines()
        )
        self.assertEqual(best, 1)

    def test_own_idea_prints_as_candidate_zero(self):
        """#664. Enter still picks the ranked angle; 0 keeps what the operator typed."""
        lines = _Lines()
        display_variants(
            _ev([("generated take", 92.0)]),
            own_idea="how does the offside rule actually work",
            print_fn=lines,
        )
        self.assertIn("0.", lines.text)
        self.assertIn("how does the offside rule actually work", lines.text)

    def test_minus_one_keeps_the_typed_idea(self):
        from core.pipeline import DiscoveryResult, chosen_variant

        d = DiscoveryResult(
            input_topic="how does the offside rule actually work",
            base_signals={"ok": True},
            evaluated=[("generated take", 92.0, {"other": 1})],
        )
        topic, score, signals = chosen_variant(d, -1)
        self.assertEqual(topic, "how does the offside rule actually work")
        self.assertEqual(signals, {"ok": True})
        self.assertEqual(score, 0.0)


class TestOperatorIsToldAboutTheTie(unittest.TestCase):
    def test_ceiling_tie_with_distinct_raw_says_ordered_by_headroom(self):
        lines = _Lines()
        display_variants(
            _ev([("a", 100.0), ("b", 100.0), ("c", 100.0)]),
            raw_scores={"a": 101.0, "b": 140.0, "c": 105.0},
            print_fn=lines,
        )
        self.assertIn("ceiling", lines.text)
        self.assertIn("headroom", lines.text)

    def test_a_genuine_tie_is_admitted_not_dressed_up(self):
        lines = _Lines()
        display_variants(
            _ev([("a", 100.0), ("b", 100.0)]),
            raw_scores={"a": 100.0, "b": 100.0},
            print_fn=lines,
        )
        self.assertIn("this is a tie", lines.text)
        self.assertIn("editorial judgement", lines.text)

    def test_distinct_scores_print_no_tie_notice(self):
        lines = _Lines()
        display_variants(
            _ev([("a", 88.0), ("b", 74.5)]),
            raw_scores={"a": 88.0, "b": 74.5},
            print_fn=lines,
        )
        self.assertNotIn("tie", lines.text)
        self.assertNotIn("ceiling", lines.text)

    def test_single_variant_is_not_a_tie(self):
        lines = _Lines()
        display_variants(_ev([("only", 100.0)]), raw_scores={"only": 120.0}, print_fn=lines)
        self.assertNotIn("tie", lines.text)

    def test_partial_raw_cannot_claim_headroom_ordering(self):
        lines = _Lines()
        display_variants(
            _ev([("a", 100.0), ("b", 100.0)]),
            raw_scores={"a": 140.0},  # one missing — the claim would be unearned
            print_fn=lines,
        )
        self.assertIn("this is a tie", lines.text)
        self.assertNotIn("headroom", lines.text)


class TestPipelineCarriesRawScores(unittest.TestCase):
    def test_discovery_result_defaults_to_empty(self):
        from core.pipeline import DiscoveryResult

        d = DiscoveryResult(input_topic="t", base_signals={}, evaluated=[])
        self.assertEqual(d.raw_scores, {})

    def test_score_variant_returns_the_raw_alongside_the_clamped(self):
        import core.pipeline as pl

        with patch.object(pl, "build_registry", return_value={}):
            with patch.object(pl, "composite_score", return_value=100.0):
                with patch("apis.topic_scorer.composite_score_raw", return_value=137.4):
                    variant, score, _signals, raw = pl._score_variant("angle", "tapin", {})
        self.assertEqual((variant, score), ("angle", 100.0))
        self.assertAlmostEqual(raw, 137.4)

    def test_seed_penalty_applies_to_both_scores(self):
        import core.pipeline as pl

        with patch.object(pl, "build_registry", return_value={}):
            with patch.object(pl, "composite_score", return_value=100.0):
                with patch("apis.topic_scorer.composite_score_raw", return_value=130.0):
                    with patch.object(pl, "anchor_preservation_penalty", return_value=10.0):
                        with patch.object(pl, "mcu_drift_penalty", return_value=0.0):
                            _v, score, _s, raw = pl._score_variant(
                                "angle", "tapin", {}, seed_topic="seed"
                            )
        self.assertEqual(score, 90.0)
        self.assertAlmostEqual(raw, 120.0)


if __name__ == "__main__":
    unittest.main()
