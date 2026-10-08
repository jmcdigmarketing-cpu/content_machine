"""#996: an ads ceiling - a monthly cap and the most a subscriber may cost.

The operator, 2026-10-08: "i am very cautious about spending too much as i ran up like $40 total
really really quickly ... it needs to be calculated and worth it", then chose $20 a month with
nothing new until the Oct 24 decision. Nothing in the repo held a ceiling:

- `ADS_MONTHLY_CAP` (dollars, blank = none): `core.money.ledger.ads_budget_line` says what ads
  cost this calendar month against it, in `ops spend`, `ops promotions`, `ops status` and the
  app's Home; startup prints it only when the month is at or over the cap (the header stays one
  line, #986). `spend add --kind ads` still records the payment - the money is spent - and says
  when it takes the month over.
- `ADS_MAX_PER_SUB` (dollars, blank = none): `promotions.verdict` says stop when a subscriber
  cost more than that, whatever the rates say - also while the campaign is still running.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

TODAY = date(2026, 10, 8)


def _ledger(test: unittest.TestCase, rows: list[tuple[float, str, str]]):
    from core.money import ledger

    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    patcher = patch.object(ledger, "LEDGER_FILE", os.path.join(tmp.name, "l.json"))
    patcher.start()
    test.addCleanup(patcher.stop)
    for amount, kind, day in rows:
        ledger.add_entry(amount, f"{kind} {day}", kind, on=date.fromisoformat(day))
    return ledger


class MonthTests(unittest.TestCase):
    def test_only_this_months_ads_count(self):
        ledger = _ledger(self, [(40, "ads", "2026-10-04"), (15, "ads", "2026-09-20"),
                                (22, "subscription", "2026-10-01")])  # fmt: skip
        self.assertEqual(ledger.ads_this_month(TODAY), 40.0)

    def test_the_line_over_under_and_without_a_cap(self):
        ledger = _ledger(self, [(40, "ads", "2026-10-04")])
        with patch.dict("os.environ", {"ADS_MONTHLY_CAP": "20"}):
            line = ledger.ads_budget_line(today=TODAY)
            self.assertIn("$40.00 of your $20.00 cap", line)
            self.assertIn("over", line)
            self.assertIn("Nov 1", line)
            self.assertTrue(ledger.ads_over_cap(today=TODAY))
        with patch.dict("os.environ", {"ADS_MONTHLY_CAP": "50"}):
            line = ledger.ads_budget_line(today=TODAY)
            self.assertIn("$10.00 left", line)
            self.assertFalse(ledger.ads_over_cap(today=TODAY))
        with patch.dict("os.environ", {"ADS_MONTHLY_CAP": ""}):
            self.assertIn("ADS_MONTHLY_CAP", ledger.ads_budget_line(today=TODAY))
            self.assertFalse(ledger.ads_over_cap(today=TODAY))

    def test_no_ads_and_no_cap_says_nothing(self):
        ledger = _ledger(self, [(22, "subscription", "2026-10-01")])
        with patch.dict("os.environ", {"ADS_MONTHLY_CAP": ""}):
            self.assertEqual(ledger.ads_budget_line(today=TODAY), "")

    def test_a_bad_cap_is_no_cap(self):
        from core.money.ledger import ads_cap

        for raw in ("", "abc", "-5"):
            with patch.dict("os.environ", {"ADS_MONTHLY_CAP": raw}):
                self.assertIsNone(ads_cap(), raw)
        with patch.dict("os.environ", {"ADS_MONTHLY_CAP": "0"}):
            self.assertEqual(ads_cap(), 0.0)


class SpendAddTests(unittest.TestCase):
    def test_adding_an_ad_over_the_cap_warns_and_still_records(self):
        ledger = _ledger(self, [(15, "ads", "2026-10-02")])
        from scripts.ops import COMMANDS

        args = SimpleNamespace(target="add", amount=10.0, what="boost", kind="ads",
                               monthly=False, date="2026-10-08", entry=None, video=None,
                               days=None)  # fmt: skip
        buf = io.StringIO()
        with patch.dict("os.environ", {"ADS_MONTHLY_CAP": "20"}), redirect_stdout(buf):
            self.assertEqual(COMMANDS["spend"][1](args), 0)
        self.assertEqual(len(ledger.entries()), 2)
        self.assertIn("over your $20.00 cap", buf.getvalue())


class ShownTests(unittest.TestCase):
    def test_status_home_and_promotions_show_it(self):
        from core.status import build_status_lines
        from desktop.home import home_lines

        line = "Ads this month: CAP LINE"
        with patch("core.money.ledger.ads_budget_line", return_value=line):
            self.assertIn(line, build_status_lines("tapin"))
            self.assertIn(("Ads", line), home_lines("tapin"))
            with patch("analytics.promotions.report", return_value=[]):
                from analytics.promotions import render

                self.assertIn(line, render("tapin"))

    def test_startup_prints_it_only_over_the_cap(self):
        import main

        for over, shown in ((True, True), (False, False)):
            buf = io.StringIO()
            with (
                patch("core.money.ledger.ads_over_cap", return_value=over),
                patch("core.money.ledger.ads_budget_line", return_value="Ads this month: CAP"),
                patch("core.status.header_line", return_value="TapIn"),
                patch("youtube.oauth.sign_in_status", return_value=""),
                patch("youtube.oauth.sign_in_reminder", return_value=""),
                patch("apis.youtube_quota.uploads_remaining", return_value=5),
                redirect_stdout(buf),
            ):
                main._print_startup("tapin")
            self.assertEqual("Ads this month: CAP" in buf.getvalue(), shown, buf.getvalue())


class MaxPerSubscriberTests(unittest.TestCase):
    def test_a_subscriber_over_the_limit_stops_a_finished_campaign(self):
        from analytics.promotions import verdict

        camp = {"state": "done", "paid_views": 2000, "paid_subscribers": 12,
                "cost_per_paid_subscriber": 3.21, "paid_subs_per_1k": 6.0,
                "subs_per_1k_others": 2.0, "spillover": 0.5}  # fmt: skip
        with patch.dict("os.environ", {"ADS_MAX_PER_SUB": "1.50"}):
            got = verdict(camp)
        self.assertEqual(got["call"], "stop")
        self.assertIn("$3.21", got["why"])
        self.assertIn("$1.50", got["why"])
        with patch.dict("os.environ", {"ADS_MAX_PER_SUB": ""}):
            kept = verdict(camp)
        self.assertEqual(kept["call"], "keep")
        self.assertIn("$3.21", kept["why"])  # a keep still names the price

    def test_a_running_campaign_is_stopped_early(self):
        from analytics.promotions import verdict

        camp = {"state": "running", "decide_on": "2026-10-24", "paid_views": 900,
                "paid_subscribers": 4, "cost_per_paid_subscriber": 5.0}  # fmt: skip
        with patch.dict("os.environ", {"ADS_MAX_PER_SUB": "1.50", "ADS_MONTHLY_CAP": ""}):
            got = verdict(camp)
        self.assertEqual(got["call"], "stop")
        self.assertIn("Studio", got["why"])

    def test_a_running_campaign_over_the_cap_says_stop_it(self):
        from analytics.promotions import verdict

        camp = {"state": "running", "decide_on": "2026-10-24", "paid_views": 900,
                "start": "2026-10-04"}  # fmt: skip
        with (
            patch.dict("os.environ", {"ADS_MAX_PER_SUB": ""}),
            patch("core.money.ledger.ads_over_cap", return_value=True),
        ):
            got = verdict(camp)
        self.assertEqual(got["call"], "stop")
        self.assertIn("cap", got["why"])


if __name__ == "__main__":
    unittest.main()
