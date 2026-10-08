"""#998: after the ads stop - did the views hold?

The operator's case for ads (2026-10-06): "isn't content kind of like a get the ball rolling
type of ordeal ... easier to be popular if you have more viewers, artificial or not". The
promotion ledger (#959) compared the campaign window with the days before it; nothing looked at
the days after, which is where a snowball would show. `analytics.promotions` now adds, per
campaign, the channel's organic views a day (every video, the promoted ones included) in up to
the campaign's `days` after its last day, against the same span before it:

- `after_per_day`, `after_days` (days with data) and `held` = after / before - 1;
- `verdict` keeps a campaign when `held` >= `SPILLOVER_KEEP` with 7+ days after it, and says
  how many days after it has so far otherwise;
- `render` prints before -> during -> after.
"""

from __future__ import annotations

import json
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

START = date(2026, 10, 4)
END = date(2026, 10, 7)  # stopped early (`spend end`)


def _video(vid, *, before, during, after, paid=0, after_days=10, subs=0):
    daily, paid_daily = [], []
    for d in range(-14, 4 + after_days):
        day = START + timedelta(days=d)
        organic = before if d < 0 else during if d < 4 else after
        bought = paid if 0 <= d < 4 else 0
        daily.append([day.isoformat(), organic + bought])
        if bought:
            paid_daily.append([day.isoformat(), bought])
    metrics = {"views": sum(v for _d, v in daily), "daily_views": daily,
               "daily_paid_views": paid_daily, "subscribers_gained": subs}  # fmt: skip
    return SimpleNamespace(youtube_video_id=vid, detail=vid, content_run_id=1,
                           metrics_json=json.dumps(metrics))  # fmt: skip


ENTRY = {"id": 1, "date": START.isoformat(), "amount": 40.0, "kind": "ads", "what": "first",
         "videos": ["v1"], "ended": END.isoformat()}  # fmt: skip


def _camp(rows, today=date(2026, 10, 24)):
    from analytics import promotions

    repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
    with (
        patch("analytics.promotions._repo", return_value=repo),
        patch("core.money.ledger.entries", return_value=[ENTRY]),
    ):
        return promotions.report("tapin", today=today)[0]


class AfterTests(unittest.TestCase):
    def test_before_during_after(self):
        rows = [
            _video("v1", before=20, during=30, after=30, paid=500),
            _video("v2", before=20, during=25, after=30),
        ]
        camp = _camp(rows)
        self.assertAlmostEqual(camp["before_per_day"], 40.0)
        self.assertAlmostEqual(camp["during_per_day"], 55.0)
        self.assertAlmostEqual(camp["after_per_day"], 60.0)
        self.assertEqual(camp["after_days"], 10)
        self.assertAlmostEqual(camp["held"], 0.5)

    def test_paid_views_are_not_counted_as_held(self):
        rows = [_video("v1", before=20, during=20, after=20, paid=500)]
        camp = _camp(rows)
        self.assertAlmostEqual(camp["during_per_day"], 20.0)
        self.assertAlmostEqual(camp["held"], 0.0)


BASE = {"state": "done", "paid_views": 2000, "subs_per_1k_promoted": 0.5,
        "subs_per_1k_others": 2.0, "spillover": 0.05}  # fmt: skip


class VerdictTests(unittest.TestCase):
    def test_views_that_held_keep_the_campaign(self):
        from analytics.promotions import verdict

        got = verdict(dict(BASE, held=0.5, after_days=10))
        self.assertEqual(got["call"], "keep")
        self.assertIn("after the ads stopped", got["why"])

    def test_too_few_days_after_says_so(self):
        from analytics.promotions import verdict

        got = verdict(dict(BASE, held=0.5, after_days=3))
        self.assertEqual(got["call"], "stop")
        self.assertIn("3 days after", got["why"])

    def test_render_prints_the_three(self):
        from analytics import promotions

        rows = [_video("v1", before=20, during=30, after=30, paid=500)]
        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
        with (
            patch("analytics.promotions._repo", return_value=repo),
            patch("core.money.ledger.entries", return_value=[ENTRY]),
        ):
            text = promotions.render("tapin", today=date(2026, 10, 24))
        self.assertIn("before", text)
        self.assertIn("-> 30.0 after", text)


if __name__ == "__main__":
    unittest.main()
