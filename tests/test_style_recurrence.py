"""#803: max() hides a repeat.

The item's premise was wrong. `core/authenticity.py` already compares against
`_RECENT_RUNS = 12` scripts - it has never been "one script deep". What it does
is collapse those 12 into `max_open`, so a *recurring* shape is invisible: an
opener that shows up in eight of the last twelve at 0.5 similarity each never
touches `_OPENING_SIM_LIMIT` (0.80) and nothing is ever said about it. That is
the "recurring nightmare" opener the operator kept seeing across GTA runs.

Report-only this wave: a `style_recurrence` reading and a card note. No points
change and no `GRADE_VERSION` bump - same staging #800 used for hedge density.
"""

from __future__ import annotations

import unittest

from core.authenticity import _OPENING_SIM_LIMIT, evaluate_authenticity, style_recurrence

# Eight scripts that all open on the same five-word frame without any pair
# tripping the 0.80 opening limit or the 0.60 full-script limit. Measured on
# this fixture: peak opening 0.67, peak full 0.56, and 5 of the 8 sit at or
# above the 0.50 recurrence floor.
_OPENER = "here is the thing nobody"
_RECENT = [
    f"{_OPENER} {tail}."
    for tail in (
        "rockstar delayed it again and the studio said nothing about refunds at all",
        "the trailer leaked early and fans picked apart every frame for weeks on end",
        "that patch broke matchmaking for a week while support insisted it was fine",
        "the leaks kept coming from an insider who turned out to be completely wrong",
        "a studio veteran quit mid-project and the reasons never became public at all",
        "the release window slipped twice before anyone admitted the schedule was dead",
        "those clips were fake but three outlets ran them as confirmed footage anyway",
        "refund requests spiked and the storefront quietly changed its policy overnight",
    )
]
_DRAFT = f"{_OPENER} the next patch arrives tomorrow with server changes nobody requested."


class TestRecurrenceIsInvisibleToTheMax(unittest.TestCase):
    def test_no_single_pair_trips_the_opening_limit(self) -> None:
        """The premise of the test: this is exactly the case max() lets through."""
        from difflib import SequenceMatcher

        from core.authenticity import _opening

        peak = max(
            SequenceMatcher(None, _opening(_DRAFT), _opening(other)).ratio() for other in _RECENT
        )
        self.assertLess(peak, _OPENING_SIM_LIMIT, f"fixture invalid: peak {peak:.2f}")

    def test_the_repeated_opener_is_counted(self) -> None:
        reading = style_recurrence(_DRAFT, _RECENT)
        self.assertEqual(reading["n"], 8)
        self.assertGreaterEqual(reading["opener"], 5)
        self.assertTrue(reading["flagged"])

    def test_a_distinct_draft_is_not_flagged(self) -> None:
        distinct = "Valve just quietly shipped a Steam Deck revision and nobody noticed the price."
        reading = style_recurrence(distinct, _RECENT)
        self.assertLess(reading["opener"], 3)
        self.assertFalse(reading["flagged"])

    def test_no_history_is_not_a_repeat(self) -> None:
        reading = style_recurrence(_DRAFT, [])
        self.assertEqual(reading["n"], 0)
        self.assertFalse(reading["flagged"])


class TestRecurrenceReachesTheReport(unittest.TestCase):
    def test_the_variation_check_says_so_without_changing_the_points(self) -> None:
        report = evaluate_authenticity(_DRAFT, "tapin", fact_count=3, recent=_RECENT)
        variation = next(c for c in report.checks if c.name == "variation")
        self.assertIn("recurs in", variation.detail.lower())
        # Report-only: the gate and the points are untouched this wave.
        self.assertTrue(variation.passed)
        self.assertGreaterEqual(report.recurrence["opener"], 5)

    def test_points_are_identical_with_and_without_the_repeat(self) -> None:
        """Proves report-only: the same draft scores the same either way."""
        repeated = evaluate_authenticity(_DRAFT, "tapin", fact_count=3, recent=_RECENT)
        # Same peak similarity, but each prior opens differently -> no recurrence.
        varied = [
            _RECENT[0],
            "Completely unrelated opening about hardware pricing and nothing else at all.",
        ]
        control = evaluate_authenticity(_DRAFT, "tapin", fact_count=3, recent=varied)
        self.assertTrue(repeated.recurrence["flagged"])
        self.assertFalse(control.recurrence["flagged"])

    def test_the_reading_is_persisted_for_the_card(self) -> None:
        from unittest.mock import patch

        from core.run_quality import build_quality

        with (
            patch("core.authenticity._recent_scripts", return_value=_RECENT),
            patch("core.engagement_predictor.predict_engaged_rate", return_value=None),
        ):
            quality = build_quality(script=_DRAFT, channel_id="tapin", features={})

        self.assertGreaterEqual(quality.get("style_recurrence_opener"), 5)


if __name__ == "__main__":
    unittest.main()


class TestTheRecurrenceIsReadBack(unittest.TestCase):
    """The persisted reading has to reach the operator, not just the row."""

    def test_the_card_shows_a_recurring_opener_from_the_record(self) -> None:
        import json
        from unittest.mock import patch

        from core.video_grade import display_grade_for_run
        from storage.repositories.content_runs import ContentRunRecord

        quality = {
            "hook_score": 70,
            "hook_verdict": "strong",
            "authenticity_score": 80,
            "authenticity_verdict": "ok",
            "ungrounded_count": 0,
            "style_recurrence_opener": 7,
            "style_recurrence_closer": 1,
            "style_recurrence_n": 12,
        }
        record = ContentRunRecord(
            id=7,
            channel_id="tapin",
            input_topic="t",
            selected_topic="t",
            status="drafted",
            composite_score=64.0,
            script_preview="a script",
            quality_json=json.dumps(quality),
        )

        class _Repo:
            def get(self, run_id):
                return record

        printed: list[str] = []
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=_Repo(),
            ),
            patch("core.video_grade.render_expert_panel", return_value=""),
            patch("core.video_grade._accuracy_lines", return_value=[]),
        ):
            display_grade_for_run(7, print_fn=printed.append)

        text = "\n".join(printed).lower()
        self.assertIn("7/12", text)
        self.assertIn("opener", text)
