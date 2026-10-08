"""#997: which video is worth promoting.

Ads amplify a Short; they do not fix one. The operator (2026-10-08) wants spending "calculated
and worth it", so `analytics.promotions.candidates` names at most two videos that already held
organic viewers, from the stored numbers `ops growth` reads (`analytics.growth._rows`):

- a full first week measured (organic 7-day views exist);
- never promoted - no paid views, and in no ads entry's `--video` list;
- organic 7-day views at or above the channel's median;
- stayed share in the channel's top third.

The suggested test is `min($10, what the monthly cap has left)` over 5 days; when the cap is
spent it says none this month. Below 5 measured videos it is "collecting". Shown in `ops
promotions` and on the app's Analytics page.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

TODAY = date(2026, 10, 8)
PUBLISHED = datetime(2026, 9, 20, tzinfo=timezone.utc)


def _row(vid, stayed, views7, paid=0):
    return {"title": f"Video {vid}", "video_id": vid, "published": PUBLISHED, "views7": views7,
            "stayed": stayed, "feed": None, "views": (views7 or 0) + paid, "paid": paid,
            "run_id": None}  # fmt: skip


ROWS = [
    _row("v1", 0.70, 900),
    _row("v2", 0.65, 800, paid=500),  # promoted: paid views
    _row("v3", 0.40, 1000),  # many views, but most swiped away
    _row("v4", 0.55, 300),  # below the median
    _row("v5", 0.30, 200),
    _row("v6", 0.20, 100),
    _row("v7", 0.68, 600),  # named in an ads entry
    _row("v8", 0.90, None),  # first week not over
]

ADS = [{"id": 1, "date": "2026-10-04", "amount": 40.0, "kind": "ads", "what": "first",
        "videos": ["v7"]}]  # fmt: skip


class CandidateTests(unittest.TestCase):
    def _cands(self, rows=ROWS, cap="", month=0.0):
        from analytics import promotions

        with (
            patch("analytics.growth._rows", return_value=rows),
            patch("core.money.ledger.entries", return_value=ADS),
            patch("core.money.ledger.ads_this_month", return_value=month),
            patch.dict("os.environ", {"ADS_MONTHLY_CAP": cap}),
        ):
            return promotions.candidates("tapin", today=TODAY)

    def test_only_a_video_that_held_viewers_and_was_never_promoted(self):
        got = self._cands()
        self.assertEqual(got["state"], "ready")
        self.assertEqual([p["video_id"] for p in got["picks"]], ["v1"])

    def test_the_test_is_sized_to_what_the_cap_has_left(self):
        self.assertEqual(self._cands(cap="")["budget"], 10.0)
        self.assertEqual(self._cands(cap="50", month=45.0)["budget"], 5.0)
        spent = self._cands(cap="20", month=40.0)
        self.assertEqual(spent["budget"], 0.0)
        self.assertEqual(spent["days"], 5)

    def test_collecting_below_five_measured_videos(self):
        got = self._cands(rows=[*ROWS[:3], ROWS[-1]])
        self.assertEqual(got["state"], "collecting")
        self.assertEqual(got["picks"], [])


class ShownTests(unittest.TestCase):
    def test_lines_say_the_video_and_the_test(self):
        from analytics.promotions import candidate_lines

        ready = {"state": "ready", "budget": 10.0, "days": 5, "picks": [
            {"title": "Video v1", "video_id": "v1", "stayed": 0.70, "views7": 900}]}  # fmt: skip
        with patch("analytics.promotions.candidates", return_value=ready):
            text = "\n".join(candidate_lines("tapin"))
        self.assertIn("Video v1", text)
        self.assertIn("v1", text)
        self.assertIn("70%", text)
        self.assertIn("$10", text)
        self.assertIn("5 days", text)
        spent = dict(ready, budget=0.0)
        with patch("analytics.promotions.candidates", return_value=spent):
            self.assertIn("cap is spent", "\n".join(candidate_lines("tapin")))

    def test_ops_promotions_prints_them(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with (
            patch("analytics.promotions.report", return_value=[]),
            patch("analytics.promotions.candidate_lines", return_value=["Worth promoting: X"]),
            redirect_stdout(buf),
        ):
            COMMANDS["promotions"][1](SimpleNamespace(channel="tapin"))
        self.assertIn("Worth promoting: X", buf.getvalue())

    def test_the_analytics_page_shows_them(self):
        from desktop.analytics_page import analytics_data

        with (
            patch("analytics.growth.report", return_value={}),
            patch("analytics.growth.videos", return_value=[]),
            patch("analytics.promotions.candidates_line", return_value="Worth promoting: X"),
        ):
            data = analytics_data("tapin")
        self.assertIn("Worth promoting: X", data["lines"])


class RowsTests(unittest.TestCase):
    def test_growth_rows_carry_the_video_id(self):
        import json

        from analytics import growth

        row = SimpleNamespace(youtube_video_id="abc", detail="T", content_run_id=1,
                              metrics_json=json.dumps({"views": 10}), published_at=None,
                              source="")  # fmt: skip
        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: [row])
        with (
            patch("analytics.growth._repo", return_value=repo),
            patch("storage.repositories.publish_log.is_seeded", return_value=False),
        ):
            self.assertEqual(growth._rows("tapin")[0]["video_id"], "abc")


if __name__ == "__main__":
    unittest.main()
