"""#1054: Shorts cut from a long video measured against Shorts made as Shorts.

`core/chapter_shorts.py` writes `short_source: chapter_cut` on the Short's run and nothing
read it. On 2026-10-10 the store held 5 cut Shorts, none of them published, so the line has to
say that plainly instead of printing a comparison of nothing.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


def _row(run_id, views7, stayed):
    return {"title": f"V{run_id}", "published": None, "views7": views7, "stayed": stayed,
            "feed": None, "views": views7 or 0, "paid": 0, "run_id": run_id}  # fmt: skip


CUT = {"short_source": "chapter_cut", "parent_run_id": 119, "length_preset": "2"}
NATIVE = {"length_preset": "2"}
LONG = {"length_preset": "4", "all_angles": True}


class ShortsSplitTests(unittest.TestCase):
    def _split(self, rows, features, made=0):
        from analytics import growth

        with (
            patch("analytics.growth._rows", return_value=rows),
            patch("analytics.growth._features", side_effect=lambda rid: features.get(rid, {})),
            patch("analytics.growth._cut_shorts_made", return_value=made),
        ):
            return growth.shorts_split("tapin"), growth.shorts_line("tapin")

    def test_cut_and_native_are_measured_apart(self):
        rows = [_row(i, v, s) for i, v, s in ((1, 300, 0.40), (2, 340, 0.44), (3, 320, 0.42))]
        rows += [_row(i, v, s) for i, v, s in ((11, 600, 0.60), (12, 640, 0.62), (13, 700, 0.58))]
        rows += [_row(21, 9000, 0.9)]
        features = {1: CUT, 2: CUT, 3: CUT, 11: NATIVE, 12: NATIVE, 13: NATIVE, 21: LONG}
        split, line = self._split(rows, features, made=3)
        self.assertEqual((split["n_cut"], split["n_native"]), (3, 3))
        self.assertEqual((split["cut_views"], split["native_views"]), (320, 640))
        self.assertAlmostEqual(split["cut_stayed"], 0.42)
        self.assertIn("320", line)
        self.assertIn("640", line)
        self.assertIn("n=3", line)

    def test_a_long_video_is_on_neither_side(self):
        split, _line = self._split([_row(21, 9000, 0.9)], {21: LONG})
        self.assertEqual((split["n_cut"], split["n_native"]), (0, 0))

    def test_an_unmeasured_week_is_not_counted(self):
        split, _line = self._split([_row(1, None, None), _row(11, 500, 0.5)], {1: CUT, 11: NATIVE})
        self.assertEqual((split["n_cut"], split["n_native"]), (0, 1))

    def test_cut_shorts_that_were_never_published_are_named(self):
        rows = [_row(11 + i, 500, 0.5) for i in range(4)]
        _split, line = self._split(rows, {11 + i: NATIVE for i in range(4)}, made=5)
        self.assertIn("5 cut", line)
        self.assertIn("none published", line)

    def test_too_few_says_how_many_more(self):
        rows = [_row(1, 300, 0.4)] + [_row(11 + i, 500, 0.5) for i in range(4)]
        features = {1: CUT, **{11 + i: NATIVE for i in range(4)}}
        _split, line = self._split(rows, features, made=1)
        self.assertIn("1 measured", line)
        self.assertIn("needs 3", line)

    def test_the_lever_speaks_only_past_the_floor(self):
        from analytics.growth import levers

        base = {"per_week": 7.5, "paid_share": 0.0}
        thin = {"n_cut": 2, "n_native": 9, "cut_views": 100, "native_views": 600}
        real = {"n_cut": 4, "n_native": 9, "cut_views": 250, "native_views": 600}
        self.assertNotIn("shorts", [lv["key"] for lv in levers({**base, "shorts_split": thin})])
        found = [lv for lv in levers({**base, "shorts_split": real}) if lv["key"] == "shorts"]
        self.assertEqual(len(found), 1)
        self.assertIn("250", found[0]["line"])
        self.assertIn("600", found[0]["line"])

    def test_the_report_carries_the_split_and_the_page_prints_it(self):
        from analytics import growth

        with (
            patch("analytics.growth._rows", return_value=[]),
            patch("analytics.growth._cut_shorts_made", return_value=0),
        ):
            self.assertIn("shorts_split", growth.report("tapin"))


if __name__ == "__main__":
    unittest.main()
