"""The operator's stated intent must reach angle selection.

Run 73: the operator typed positive, reaction-shaped topics three times in a row
and got critique angles every time — "reveals missing mechanics", "community
wishlist items", "critique of design choices", "still worth the hype?" — ending in
the title "GTA 6 Community Predicts Toxic Meta Before Launch — Why They're Wrong".

The cause was not the LLM being edgy. `generate_variants` picked `angle_types`
from `profile.domain` and `repeat_count` only, so the topic string never reached
the decision, and `generate_ai_angles` additionally instructed the model to
"focus on ANALYSIS, PREDICTION, COMMUNITY debate, or CRITIQUE" once a franchise
was established. GTA 6 was established, so a reaction video was structurally
impossible to ask for.

These tests assert the SELECTED ANGLE TYPES and the prompt text, never the LLM's
output, which is not deterministic.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from apis import topic_variants
from core.angle_intent import ANGLE_REACTION, detect_angle_intent

# The operator's actual strings from run 73.
RUN73_TOPICS = (
    "GTA 6 Extended look analysis. HUGE NEWS LOOKS GREAT",
    "GTA 6 Extended look reactions, looks great!",
    "GTA 6 looks amazing!!!",
)

# Angle labels that a reaction video must never be steered into.
CRITIQUE_LABELS = {
    "whats_broken_needs_fixing",
    "community_wishlist",
    "is_it_still_worth_playing",
    "meta_or_balance_take",
    "community_controversy",
    "controversy",
}


class TestIntentDetection(unittest.TestCase):
    def test_the_operators_three_real_topics_all_read_as_reaction(self):
        for topic in RUN73_TOPICS:
            with self.subTest(topic=topic):
                self.assertEqual(detect_angle_intent(topic), ANGLE_REACTION)

    def test_critique_and_neutral_topics_are_not_reaction(self):
        for topic in (
            "GTA 6 review: is it worth it",
            "GTA 6 Extended Look analysis reveals missing mechanics",
            "UFC 320 predictions",
            "Take-Two stock after the GTA 6 delay",
            "",
        ):
            with self.subTest(topic=topic):
                self.assertNotEqual(detect_angle_intent(topic), ANGLE_REACTION)


class TestAngleTypesFollowIntent(unittest.TestCase):
    """`generate_variants` is what actually chooses the frame."""

    def _angle_types_for(self, topic: str, *, repeat_count: int) -> list[str]:
        seen: dict[str, list[str]] = {}

        def _capture(t, angle_types, **kwargs):
            seen["types"] = list(angle_types)
            return ["angle"]

        with patch.object(topic_variants, "generate_ai_titles", side_effect=_capture):
            topic_variants.generate_variants(topic, channel_id="tapin", repeat_count=repeat_count)
        return seen.get("types", [])

    def test_established_reaction_topic_does_not_get_the_critique_set(self):
        """GTA 6 is established (covered 3+ times), which is exactly the branch
        that produced run 73's angles."""
        for topic in RUN73_TOPICS:
            with self.subTest(topic=topic):
                types = self._angle_types_for(topic, repeat_count=5)
                self.assertTrue(types)
                self.assertEqual(
                    CRITIQUE_LABELS.intersection(types),
                    set(),
                    f"reaction topic still steered into critique: {types}",
                )

    def test_an_established_coverage_topic_keeps_the_staleness_guard(self):
        """The established pivot is right for genuinely repeated coverage — it
        must not be collateral damage."""
        types = self._angle_types_for("GTA 6 meta breakdown", repeat_count=5)
        self.assertTrue(CRITIQUE_LABELS.intersection(types), types)


class TestPromptDropsTheCritiqueInstruction(unittest.TestCase):
    def _prompt_for(self, topic: str, *, is_established: bool) -> str:
        captured: dict[str, str] = {}

        def _complete(prompt, **kwargs):
            captured["prompt"] = prompt
            return "a\nb\nc\nd\ne"

        with patch.object(topic_variants, "complete", side_effect=_complete):
            topic_variants.generate_ai_angles(
                topic,
                ["first_impressions"],
                channel_id="tapin",
                is_established=is_established,
            )
        return captured.get("prompt", "")

    def test_reaction_topic_is_not_told_to_critique(self):
        prompt = self._prompt_for(RUN73_TOPICS[1], is_established=True)
        self.assertNotIn("CRITIQUE", prompt)
        self.assertNotIn("that angle is stale", prompt)

    def test_non_reaction_established_topic_still_gets_the_freshness_guard(self):
        prompt = self._prompt_for("GTA 6 meta breakdown", is_established=True)
        self.assertIn("CRITIQUE", prompt)


class TestIntentsBeyondReaction(unittest.TestCase):
    """#533. The detector recognised exactly one alternative frame, so every calm
    idea fell to `default` and got the take machinery — `controversy` is in every
    non-reaction angle table. These are the operator's own recorded seeds."""

    def test_real_recorded_seeds_read_as_the_frame_they_asked_for(self):
        from core.angle_intent import (
            ANGLE_COMPARISON,
            ANGLE_EXPLAINER,
            ANGLE_LIST,
            ANGLE_RETROSPECTIVE,
            ANGLE_TUTORIAL,
        )

        cases = {
            # run 48's seed, which became a Marvel Rivals esports script
            "WAYYYYYY too early final standing projections for 2027": None,
            "how does the offside rule actually work": ANGLE_EXPLAINER,
            "the hidden cost of index fund concentration explained": ANGLE_EXPLAINER,
            "top 5 heavyweights of the decade": ANGLE_LIST,
            "ranking every GTA protagonist": ANGLE_LIST,
            "how to counter a dive comp in Marvel Rivals": ANGLE_TUTORIAL,
            # run 62's seed, verbatim
            "COD Bo2 Playstation return. Is it better or worse than back in the day?": (
                ANGLE_COMPARISON
            ),
            "revisiting Black Ops 2 ten years later": ANGLE_RETROSPECTIVE,
        }
        for topic, expected in cases.items():
            if expected is None:
                continue
            with self.subTest(topic=topic):
                self.assertEqual(detect_angle_intent(topic), expected)

    def test_an_explainer_is_not_steered_into_controversy(self):
        """The complaint in one assertion."""
        seen: dict[str, list[str]] = {}

        def _capture(t, angle_types, **kwargs):
            seen["types"] = list(angle_types)
            return ["angle"]

        with patch.object(topic_variants, "generate_ai_titles", side_effect=_capture):
            topic_variants.generate_variants(
                "how does the offside rule actually work", channel_id="tapin", repeat_count=0
            )
        self.assertTrue(seen["types"])
        self.assertEqual(CRITIQUE_LABELS.intersection(seen["types"]), set(), seen["types"])

    def test_the_established_critique_pivot_still_survives(self):
        """Guard against exactly the collateral damage this change invites: a
        loose explainer cue capturing 'breakdown' would silently kill the
        staleness guard, which is correct for genuinely repeated coverage."""
        seen: dict[str, list[str]] = {}

        def _capture(t, angle_types, **kwargs):
            seen["types"] = list(angle_types)
            return ["angle"]

        with patch.object(topic_variants, "generate_ai_titles", side_effect=_capture):
            topic_variants.generate_variants(
                "GTA 6 meta breakdown", channel_id="tapin", repeat_count=5
            )
        self.assertTrue(CRITIQUE_LABELS.intersection(seen["types"]), seen["types"])

    def test_every_intent_has_a_table_and_an_operator_note(self):
        """A detectable intent with no table would silently fall back to the take
        set — the failure mode this item exists to remove."""
        from apis.topic_variants import INTENT_ANGLES
        from core.angle_intent import ALL_INTENTS, angle_intent_note

        for intent in ALL_INTENTS:
            with self.subTest(intent=intent):
                self.assertTrue(angle_intent_note(intent))
                angle_intent_note(intent).encode("cp1252")  # candidate 250
                if intent != "default":
                    self.assertEqual(len(INTENT_ANGLES[intent]), 5, intent)

    def test_reaction_still_works(self):
        """The 2026-08-28 behaviour must survive being generalised."""
        for topic in RUN73_TOPICS:
            with self.subTest(topic=topic):
                self.assertEqual(detect_angle_intent(topic), ANGLE_REACTION)


if __name__ == "__main__":
    unittest.main()
