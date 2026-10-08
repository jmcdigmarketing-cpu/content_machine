"""#992: paid subscribers, from the campaign's own results page.

The stored per-video `subscribers_gained` is one number for every viewer, so the promotion
ledger (#959) could only compare rates between videos. The operator, 2026-10-08: YouTube
Studio's campaign page shows the subscribers the ad brought. That is the only clean paid count,
so it is entered once - `py -m scripts.ops spend result --entry N --subs N [--amount X]`, where
`--amount` is what the campaign actually charged (it can stop under its budget) - and
`analytics/promotions` reads it:

- cost per paid subscriber = charged / paid subscribers;
- paid subscribers per 1,000 paid views, against the channel's other videos' rate;
- the "not split into paid and organic" line only while a campaign has no result.

The spend total counts what was charged once a result says so.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

START = date(2026, 10, 4)


def _temp_ledger(test: unittest.TestCase):
    from core.money import ledger

    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    patcher = patch.object(ledger, "LEDGER_FILE", os.path.join(tmp.name, "l.json"))
    patcher.start()
    test.addCleanup(patcher.stop)
    return ledger


class LedgerTests(unittest.TestCase):
    def test_a_result_is_kept_on_the_ads_entry(self):
        ledger = _temp_ledger(self)
        entry = ledger.add_entry(40, "first campaign", "ads", on=START, videos=["v1"])
        got = ledger.set_result(entry["id"], subscribers=12, spent=38.5, on=date(2026, 10, 9))
        self.assertEqual(got["result"], {"subscribers": 12, "spent": 38.5, "date": "2026-10-09"})
        # A second call changes only what it is given.
        again = ledger.set_result(entry["id"], subscribers=14)
        self.assertEqual(again["result"]["subscribers"], 14)
        self.assertEqual(again["result"]["spent"], 38.5)

    def test_refusals(self):
        ledger = _temp_ledger(self)
        sub = ledger.add_entry(22, "ElevenLabs", "subscription", on=START, monthly=True)
        ads = ledger.add_entry(40, "first campaign", "ads", on=START)
        with self.assertRaises(ValueError):
            ledger.set_result(sub["id"], subscribers=3)  # not an ad campaign
        with self.assertRaises(ValueError):
            ledger.set_result(ads["id"], subscribers=-1)
        with self.assertRaises(ValueError):
            ledger.set_result(ads["id"])  # nothing to record
        self.assertIsNone(ledger.set_result(99, subscribers=3))

    def test_the_total_counts_what_was_charged(self):
        ledger = _temp_ledger(self)
        entry = ledger.add_entry(40, "first campaign", "ads", on=START)
        ledger.set_result(entry["id"], spent=38.5)
        self.assertEqual(ledger.total_spent(today=START)["total"], 38.5)


class OpsTests(unittest.TestCase):
    def test_spend_result(self):
        ledger = _temp_ledger(self)
        from scripts.ops import COMMANDS

        entry = ledger.add_entry(40, "first campaign", "ads", on=START)
        args = SimpleNamespace(target="result", entry=entry["id"], subs=12, amount=38.5,
                               date="", what="", kind="", monthly=False, video=None, days=None)  # fmt: skip
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(COMMANDS["spend"][1](args), 0)
        self.assertEqual(ledger.entries()[0]["result"]["subscribers"], 12)
        self.assertIn("12 subscribers", buf.getvalue())
        self.assertIn("$3.21", buf.getvalue())  # 38.50 / 12

    def test_spend_result_needs_the_entry_and_a_number(self):
        _temp_ledger(self)
        from scripts.ops import COMMANDS

        args = SimpleNamespace(target="result", entry=None, subs=12, amount=None, date="",
                               what="", kind="", monthly=False, video=None, days=None)  # fmt: skip
        with redirect_stdout(io.StringIO()):
            self.assertEqual(COMMANDS["spend"][1](args), 2)


def _video(vid: str, *, paid_per_day: int = 0, subs: int = 0, views_per_day: int = 30):
    first = START - timedelta(days=14)
    daily = [[(first + timedelta(days=d)).isoformat(), views_per_day + (
        paid_per_day if d >= 14 and d < 18 else 0)] for d in range(30)]  # fmt: skip
    paid = [[(START + timedelta(days=d)).isoformat(), paid_per_day] for d in range(4)]
    metrics = {"views": sum(v for _d, v in daily), "daily_views": daily,
               "daily_paid_views": paid if paid_per_day else [], "subscribers_gained": subs}  # fmt: skip
    return SimpleNamespace(youtube_video_id=vid, detail=f"Video {vid}", content_run_id=1,
                           metrics_json=json.dumps(metrics))  # fmt: skip


ENTRY = {"id": 1, "date": START.isoformat(), "amount": 40.0, "kind": "ads", "what": "first",
         "videos": ["v1"], "ended": "2026-10-07",
         "result": {"subscribers": 12, "spent": 38.5, "date": "2026-10-09"}}  # fmt: skip


class ReportTests(unittest.TestCase):
    def _camp(self, entry, rows):
        from analytics import promotions

        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
        with (
            patch("analytics.promotions._repo", return_value=repo),
            patch("core.money.ledger.entries", return_value=[entry]),
        ):
            return promotions.report("tapin", today=date(2026, 10, 24))[0]

    def test_paid_subscribers_from_the_result(self):
        rows = [_video("v1", paid_per_day=500, subs=20), _video("v2", subs=3)]
        camp = self._camp(ENTRY, rows)
        self.assertEqual(camp["amount"], 38.5)  # what was charged, not the budget
        self.assertEqual(camp["paid_views"], 2000)
        self.assertEqual(camp["paid_subscribers"], 12)
        self.assertAlmostEqual(camp["cost_per_paid_subscriber"], 3.21, places=2)
        self.assertAlmostEqual(camp["paid_subs_per_1k"], 6.0)

    def test_the_verdict_reads_the_paid_rate(self):
        from analytics.promotions import verdict

        good = {"state": "done", "paid_views": 2000, "paid_subscribers": 12,
                "paid_subs_per_1k": 6.0, "subs_per_1k_promoted": 0.1,
                "subs_per_1k_others": 2.0, "spillover": 0.0}  # fmt: skip
        self.assertEqual(verdict(good)["call"], "keep")
        self.assertIn("paid", verdict(good)["why"])
        poor = dict(good, paid_subscribers=1, paid_subs_per_1k=0.5, subs_per_1k_promoted=9.0)
        self.assertEqual(verdict(poor)["call"], "stop")

    def test_render_says_where_the_number_came_from(self):
        from analytics import promotions

        rows = [_video("v1", paid_per_day=500, subs=20), _video("v2", subs=3)]
        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
        with (
            patch("analytics.promotions._repo", return_value=repo),
            patch("core.money.ledger.entries", return_value=[ENTRY]),
        ):
            text = promotions.render("tapin")
        self.assertIn("from the campaign page", text)
        self.assertNotIn("not split", text)  # every campaign has its result
        no_result = {k: v for k, v in ENTRY.items() if k != "result"}
        with (
            patch("analytics.promotions._repo", return_value=repo),
            patch("core.money.ledger.entries", return_value=[no_result]),
        ):
            text = promotions.render("tapin")
        self.assertIn("not split", text)
        self.assertIn("spend result", text)


if __name__ == "__main__":
    unittest.main()
