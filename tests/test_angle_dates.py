"""#1008: angles get the date and past-event checks.

Runs 119 and 120 offered angles written before any facts, and nothing checked them:
"These developers think AI will make cross-compatible gaming mods obsolete by 2025" (a past
year as a prediction - the script then had to say "Wait. It's 2026") and "Shavkat Rakhmonov's
undefeated streak faces real threat at UFC 305" (UFC 305 was August 2024). Both scored 96.7 and
100.0. Measured on 1b43610 with today = 2026-10-09: `find_elapsed_mismatches`,
`stale_preview` and `is_future_dated_claim` all pass both angles, and nothing in the repo maps
a numbered event to a date. A flagged angle is now dropped before the menu, as #976 cuts a
contrast frame, and the generation prompt carries today's date.
"""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import patch

TODAY = datetime.date(2026, 10, 9)
RUN_120 = "These developers think AI will make cross-compatible gaming mods obsolete by 2025"
RUN_119 = "Shavkat Rakhmonov's undefeated streak faces real threat at UFC 305"


class PastYearTests(unittest.TestCase):
    def test_a_past_year_as_a_prediction(self):
        from core.facts.event_dates import past_year_prediction

        self.assertIn("2025", past_year_prediction(RUN_120, TODAY))
        self.assertTrue(past_year_prediction("Madden 25 predictions for 2024", TODAY))
        self.assertTrue(past_year_prediction("Why the Chargers will win it all in 2025", TODAY))

    def test_a_retrospective_or_current_year_is_fine(self):
        from core.facts.event_dates import past_year_prediction

        self.assertEqual(past_year_prediction("What the 2024 draft taught the Chargers", TODAY), "")
        self.assertEqual(past_year_prediction("Can the Chargers turn it around by 2027", TODAY), "")
        self.assertEqual(past_year_prediction("Why 2026 is the year of AI mods", TODAY), "")


class NumberedEventTests(unittest.TestCase):
    def test_a_numbered_event_years_ago(self):
        from core.facts.event_dates import past_numbered_event

        note = past_numbered_event(RUN_119, TODAY)
        self.assertIn("UFC 305", note)
        self.assertIn("2024", note)

    def test_a_dated_fact_line_wins_over_the_estimate(self):
        from core.facts.event_dates import past_numbered_event

        facts = "UFC 331 took place on May 2, 2026 in Las Vegas."
        self.assertIn("2026-05-02", past_numbered_event("Who wins at UFC 331", TODAY, facts=facts))
        later = "UFC 331 is set for December 12, 2026."
        self.assertEqual(past_numbered_event("Who wins at UFC 331", TODAY, facts=later), "")

    def test_a_recent_or_coming_event_is_not_flagged(self):
        from core.facts.event_dates import past_numbered_event

        self.assertEqual(past_numbered_event("Who wins at UFC 330", TODAY), "")

    def test_the_topic_naming_the_event_is_the_operator_asking(self):
        from core.facts.event_dates import past_numbered_event

        self.assertEqual(
            past_numbered_event(RUN_119, TODAY, topic="UFC 305 rewatch: Rakhmonov"), ""
        )


class StaleAngleTests(unittest.TestCase):
    def test_reason_and_clean_angle(self):
        from core.facts.event_dates import stale_angle_reason

        self.assertTrue(stale_angle_reason(RUN_120, today=TODAY))
        self.assertTrue(stale_angle_reason(RUN_119, today=TODAY))
        self.assertEqual(
            stale_angle_reason("How the 0-4 Chargers can turn it around this year", today=TODAY),
            "",
        )


class AngleCleaningTests(unittest.TestCase):
    def test_stale_angles_are_dropped_before_the_menu(self):
        from apis import topic_variants

        raw = "\n".join(
            [
                RUN_119,
                "Rakhmonov's grappling is the cleanest path to a title shot",
                RUN_120,
                "Modders are already blending games with AI",
            ]
        )
        dropped: list[dict] = []
        with patch("core.facts.event_dates._today", return_value=TODAY):
            kept = topic_variants._clean_angle_lines(
                raw, [], topic="Shavkat Rakhmonov", dropped=dropped
            )
        self.assertEqual(
            kept,
            [
                "Rakhmonov's grappling is the cleanest path to a title shot",
                "Modders are already blending games with AI",
            ],
        )
        self.assertEqual([d["angle"] for d in dropped], [RUN_119, RUN_120])
        self.assertTrue(all(d["reason"] for d in dropped))

    def test_the_prompt_carries_today_and_drops_reach_the_report(self):
        from apis import topic_variants

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return "\n".join(
                [RUN_119, "Rakhmonov's wrestling base", "Rakhmonov vs the top five", "The title"]
            )

        report: dict = {}
        with (
            patch.object(topic_variants, "complete", side_effect=fake),
            patch("core.facts.event_dates._today", return_value=TODAY),
        ):
            angles = topic_variants.generate_variants(
                "Shavkat Rakhmonov next fight", channel_id="tapin", report=report
            )
        self.assertNotIn(RUN_119, angles)
        self.assertIn("2026-10-09", prompts[0])
        self.assertEqual(report["angles_dropped"][0]["angle"], RUN_119)


class SiblingTitleTests(unittest.TestCase):
    """The video title is written after the facts, but #978 checked it for elapsed-time
    phrases only: "Chargers predictions for 2025" passed in October 2026."""

    def test_the_title_gets_the_past_year_check(self):
        from core.facts.date_math import find_meta_mismatches

        notes = find_meta_mismatches(
            "Chargers predictions for 2025: can they turn it around",
            "They had won 11 games by 2025.",
            "",
            today=TODAY,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertTrue(notes[0].startswith("title: "))

    def test_an_iso_string_is_a_date(self):
        from core.facts.event_dates import stale_angle_reason

        self.assertTrue(stale_angle_reason(RUN_119, today="2026-10-09"))
        self.assertEqual(stale_angle_reason(RUN_119, today="2024-06-01"), "")


class MenuNoteTests(unittest.TestCase):
    def test_the_menu_says_what_was_dropped_and_why(self):
        from core.pipeline import angles_dropped_note

        note = angles_dropped_note(
            {
                "angles_dropped": [
                    {"angle": RUN_120, "reason": "'by 2025' is a year that has passed"},
                    {"angle": RUN_119, "reason": "UFC 305 was around 2024"},
                ]
            }
        )
        self.assertIn("2 angles dropped", note)
        self.assertIn("by 2025", note)
        self.assertEqual(angles_dropped_note({}), "")


if __name__ == "__main__":
    unittest.main()
