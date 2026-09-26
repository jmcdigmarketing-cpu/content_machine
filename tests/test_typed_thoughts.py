"""Typed thoughts at the Topic prompt (run 77, 2026-09-13).

The operator typed a four-question GTA 6 thesis at option 1. It was used verbatim as the
discovery search string (Trends/Wikipedia searched a comma-fragment and served "Goy"),
the angle LLM saw only that string, and its reply kept a preamble plus two raw lens
labels as angles. Each test here failed on unmodified e7ef6ad.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

RUN77_THOUGHTS = (
    "GTA 6 Analysis/Predictions!! Will it be the best game every? What does meeting the "
    "hype mean, is a goy candidate a failure? Long form predictions and content analysis"
)

# Run 77's variant reply, reconstructed from the five lines the menu printed.
RUN77_RAW_ANGLES = (
    "Here are five different angle lines for a short-form video about GTA 6:\n"
    "\n"
    "1. **whats_broken_needs_fixing**\n"
    "GTA 6 Analysis: Is Grand Theft Auto's Formula Still Relevant?\n"
    "**upcoming_content_predictions**\n"
    "TAKE: A critical examination of the series' core gameplay mechanics and whether "
    "they've become stale."
)


class TestThoughtsBecomeASearchSeed(unittest.TestCase):
    def test_run_77_thesis_searches_as_gta_6(self):
        from core.idea_intake import search_seed_from_thoughts

        self.assertEqual(search_seed_from_thoughts(RUN77_THOUGHTS), "GTA 6")

    def test_named_subjects_make_the_seed(self):
        from core.idea_intake import search_seed_from_thoughts

        cases = {
            "my thoughts: is marvel rivals season 4 dying? feels like the meta is stale "
            "and nobody queues ranked": "Marvel Rivals season 4",
            "Jon Jones vs Aspinall - who ducked who, why the UFC let it drag this long": (
                "Jon Jones Aspinall UFC"
            ),
            "COD Bo2 Playstation return. Is it better or worse than back in the day?": (
                "COD Bo2 Playstation return"
            ),
        }
        for thoughts, seed in cases.items():
            with self.subTest(thoughts=thoughts):
                self.assertEqual(search_seed_from_thoughts(thoughts), seed)

    def test_thoughts_with_no_named_subject_use_a_short_first_clause(self):
        from core.idea_intake import search_seed_from_thoughts

        seed = search_seed_from_thoughts(
            "I think the Fed cutting rates again is a trap for people buying houses. "
            "Mortgage rates track the 10 year, not the Fed."
        )
        self.assertIn("Fed", seed)
        self.assertFalse(seed.lower().startswith("i think"), seed)
        self.assertLessEqual(len(seed.split()), 8, seed)

    def test_a_plain_topic_is_untouched(self):
        from core.idea_intake import search_seed_from_thoughts

        for topic in (
            "Marvel Rivals season 3 tier list",
            "how does the offside rule actually work",
        ):
            with self.subTest(topic=topic):
                self.assertEqual(search_seed_from_thoughts(topic), topic)

    def test_a_labelled_multi_line_paste_searches_the_subject(self):
        from core.idea_intake import parse_pasted_idea

        parsed = parse_pasted_idea("GTA 6 thoughts:\nWill it be GOTY?\nIs anything less a failure?")
        self.assertEqual(parsed.seed_topic, "GTA 6")
        self.assertIn("anything less a failure", parsed.angle)

    def test_parsed_idea_searches_the_seed_and_briefs_the_thoughts(self):
        from core.idea_intake import creative_brief_for_run, parse_pasted_idea

        parsed = parse_pasted_idea(RUN77_THOUGHTS)
        self.assertEqual(parsed.seed_topic, "GTA 6")
        self.assertEqual(creative_brief_for_run(parsed), RUN77_THOUGHTS)


class TestAngleRepliesAreCleaned(unittest.TestCase):
    def _angles(self, *replies: str):
        from apis import topic_variants

        with patch.object(topic_variants, "complete", side_effect=list(replies)) as llm:
            out = topic_variants.generate_ai_angles(
                "GTA 6",
                ["whats_broken_needs_fixing", "upcoming_content_predictions"],
                channel_id="tapin",
            )
        return out, llm

    def test_run_77_preamble_and_lens_labels_are_not_angles(self):
        out, _llm = self._angles(
            RUN77_RAW_ANGLES,
            "Whether GTA 6 can live up to twelve years of hype\n"
            "What a GOTY-level GTA 6 has to deliver on day one",
        )
        blob = "\n".join(out)
        self.assertNotIn("Here are", blob)
        self.assertNotIn("**", blob)
        self.assertNotIn("whats_broken_needs_fixing", blob)
        self.assertNotIn("upcoming_content_predictions", blob)
        self.assertNotIn("TAKE:", blob)
        self.assertIn("GTA 6 Analysis: Is Grand Theft Auto's Formula Still Relevant?", out)
        self.assertIn(
            "A critical examination of the series' core gameplay mechanics and whether "
            "they've become stale.",
            out,
        )

    def test_a_reply_with_too_few_real_angles_is_asked_again(self):
        out, llm = self._angles(
            RUN77_RAW_ANGLES,
            "Whether GTA 6 can live up to twelve years of hype\n"
            "What a GOTY-level GTA 6 has to deliver on day one",
        )
        self.assertEqual(llm.call_count, 2)
        self.assertIn("Whether GTA 6 can live up to twelve years of hype", out)
        self.assertGreaterEqual(len(out), 3)


class TestThoughtsReachTheAngles(unittest.TestCase):
    def test_the_angle_prompt_carries_the_operators_thoughts(self):
        from apis import topic_variants

        seen: dict[str, str] = {}

        def _complete(prompt, **kwargs):
            seen["prompt"] = prompt
            return "one real angle line\ntwo real angle line\nthree real angle line"

        with patch.object(topic_variants, "complete", side_effect=_complete):
            topic_variants.generate_ai_angles(
                "GTA 6", ["first_impressions"], channel_id="tapin", brief=RUN77_THOUGHTS
            )
        self.assertIn("meeting the hype", seen["prompt"])

    def test_thoughts_choose_the_frame_when_the_seed_names_none(self):
        from apis import topic_variants
        from apis.topic_variants import INTENT_ANGLES
        from core.angle_intent import ANGLE_LIST

        seen: dict[str, object] = {}

        def _capture(t, angle_types, **kwargs):
            seen["types"] = list(angle_types)
            seen["brief"] = kwargs.get("brief")
            return ["angle"]

        brief = "ranking every GTA protagonist from worst to best"
        with patch.object(topic_variants, "generate_ai_titles", side_effect=_capture):
            topic_variants.generate_variants("GTA 6", channel_id="tapin", brief=brief)
        self.assertEqual(seen["types"], INTENT_ANGLES[ANGLE_LIST])
        self.assertEqual(seen["brief"], brief)

    def test_discovery_passes_thoughts_and_does_not_reuse_other_thoughts(self):
        from core import pipeline

        with (
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.pipeline.build_registry", return_value={"youtube": {"score": 1}}),
            patch("core.pipeline.generate_variants", return_value=["v one", "v two"]) as gen,
            # This test asserts the discovery cache's semantics (same thoughts reuse, other
            # thoughts do not); the suite runs with it off (tests/__init__.py, #828).
            patch.dict(
                os.environ, {"COMPETITOR_SYNC_ON_DISCOVERY": "off", "DISCOVERY_CACHE": "true"}
            ),
        ):
            pipeline.run_discovery("GTA 6 thoughts audit", channel_id="tapin", brief="first")
            pipeline.run_discovery("GTA 6 thoughts audit", channel_id="tapin", brief="first")
            pipeline.run_discovery("GTA 6 thoughts audit", channel_id="tapin", brief="second")
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(gen.call_args_list[0].kwargs.get("brief"), "first")
        self.assertEqual(gen.call_args_list[1].kwargs.get("brief"), "second")


if __name__ == "__main__":
    unittest.main()
