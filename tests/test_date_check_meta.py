"""#978: the date check reads the title and the description too.

#551's `find_elapsed_mismatches` read the script only. A title saying "3 Years Since the Lakers
Traded for Luka" or a description saying "ten years since 2019" was checked by nothing, and
those are the two lines a viewer reads first. `core.facts.date_math.find_meta_mismatches`
runs the same check over both, each flag tagged with where it was found, and
`run_quality.build_quality(title=, description=)` keeps them beside the script's in
`date_mismatches` (the run card prints them). The pipeline passes the run's title and
description.
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

TODAY = date(2026, 10, 5)
TRADE = "The Lakers traded for Luka Doncic on February 2, 2025."


class MetaTests(unittest.TestCase):
    def test_a_wrong_count_in_the_title_is_flagged_and_tagged(self):
        from core.facts.date_math import find_meta_mismatches

        got = find_meta_mismatches("3 Years Since the Lakers Traded for Luka", "", TRADE,
                                   today=TODAY)  # fmt: skip
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("title: "), got)
        self.assertIn("2025-02-02", got[0])

    def test_the_description_is_checked_too(self):
        from core.facts.date_math import find_meta_mismatches

        got = find_meta_mismatches("Heat rebuild", "Ten years since 2019, the Heat rebuild.",
                                   "", today=TODAY)  # fmt: skip
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("description: "), got)

    def test_right_counts_pass(self):
        from core.facts.date_math import find_meta_mismatches

        self.assertEqual(
            find_meta_mismatches("1 Year Since the Lakers Traded for Luka",
                                 "Seven years since 2019.", TRADE, today=TODAY),
            [],
        )  # fmt: skip


class QualityTests(unittest.TestCase):
    def test_build_quality_keeps_title_flags_beside_the_scripts(self):
        from core.run_quality import build_quality

        with patch("core.facts.date_math._today", return_value=TODAY):
            quality = build_quality(
                script="The Lakers made the trade and it changed everything.",
                channel_id="tapin",
                features={"grounding_text": TRADE},
                title="3 Years Since the Lakers Traded for Luka",
                description="",
            )
        notes = quality.get("date_mismatches") or []
        self.assertTrue(any(n.startswith("title: ") for n in notes), notes)

    def test_the_pipeline_passes_the_title_and_description(self):
        import inspect

        from core import pipeline

        source = inspect.getsource(pipeline)
        call = source[source.index("quality = build_quality(") :][:400]
        self.assertIn("title=", call)
        self.assertIn("description=", call)


if __name__ == "__main__":
    unittest.main()
