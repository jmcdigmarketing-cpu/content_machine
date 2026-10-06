"""#980: one total of money spent, at startup, in `ops status` and the app's Home page.

Operator, 2026-10-06: "can i also get a total money spent across everything with the project in
entirety when i boot up". Each run stores an estimate of what it used (`features["cost"]`), the
cost tower shows quotas and `ops economics` shows cost per video - nothing added up money actually
paid: subscriptions, credit top-ups, the first $10 ad campaign. None of that is in an API, so it
is entered once (`ops spend add`), and a monthly entry keeps counting each started month until
it is ended. What the runs used is shown beside the total, never added to it - it was paid for
by those same credits and subscriptions.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

TODAY = date(2026, 10, 6)


class _LedgerCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "spend_ledger.json")
        p = patch("core.money.ledger.LEDGER_FILE", self.path)
        p.start()
        self.addCleanup(p.stop)


class TotalTests(_LedgerCase):
    def test_one_offs_and_monthly_entries_add_up(self):
        from core.money.ledger import add_entry, total_spent

        add_entry(10, "YouTube ads, first campaign", "ads", on=date(2026, 10, 4))
        add_entry(22, "ElevenLabs plan", "subscription", monthly=True, on=date(2026, 8, 15))
        add_entry(5, "DeepSeek credits", "credits", on=date(2026, 9, 1))
        got = total_spent(today=TODAY)
        # ElevenLabs: Aug, Sep, Oct started -> 3 x 22
        self.assertEqual(got["by_kind"], {"ads": 10.0, "subscription": 66.0, "credits": 5.0})
        self.assertEqual(got["total"], 81.0)

    def test_an_ended_subscription_stops_counting(self):
        from core.money.ledger import add_entry, end_entry, total_spent

        entry = add_entry(22, "ElevenLabs", "subscription", monthly=True, on=date(2026, 7, 1))
        self.assertTrue(end_entry(entry["id"], on=date(2026, 8, 20)))
        self.assertEqual(total_spent(today=TODAY)["total"], 44.0)  # Jul, Aug
        self.assertFalse(end_entry(99))

    def test_a_future_start_counts_nothing_yet(self):
        from core.money.ledger import add_entry, total_spent

        add_entry(9, "Buffer", "subscription", monthly=True, on=date(2026, 11, 1))
        self.assertEqual(total_spent(today=TODAY)["total"], 0.0)

    def test_bad_input_is_refused(self):
        from core.money.ledger import add_entry

        with self.assertRaises(ValueError):
            add_entry(-3, "x", "ads")
        with self.assertRaises(ValueError):
            add_entry(3, "x", "lunch")
        with self.assertRaises(ValueError):
            add_entry(3, "", "ads")


class LineTests(_LedgerCase):
    def _line(self, usage=(0.0, 0)):
        from core.money.ledger import spend_line

        with patch("core.money.ledger.run_usage", return_value=usage):
            return spend_line(today=TODAY)

    def test_nothing_entered_says_how(self):
        line = self._line((1.23, 40))
        self.assertIn("not entered yet", line)
        self.assertIn("py -m scripts.ops spend add", line)
        self.assertIn("$1.23", line)

    def test_the_total_and_its_parts(self):
        from core.money.ledger import add_entry

        add_entry(10, "ads", "ads", on=date(2026, 10, 4))
        add_entry(22, "ElevenLabs", "subscription", monthly=True, on=date(2026, 9, 1))
        line = self._line((3.4, 58))
        self.assertTrue(line.startswith("Spent so far: $54.00"), line)
        self.assertIn("subscriptions $44.00", line)
        self.assertIn("ads $10.00", line)
        self.assertIn("58 runs used ~$3.40 of it", line)


class UsageTests(unittest.TestCase):
    def test_runs_on_every_channel_are_summed(self):
        from core.money.ledger import run_usage

        runs = {
            "tapin": [SimpleNamespace(features_json=json.dumps({"cost": {"total": 0.31}})),
                      SimpleNamespace(features_json=json.dumps({"cost": {"total": 0.19}}))],
            "moneywise": [SimpleNamespace(features_json="{}"),
                          SimpleNamespace(features_json=json.dumps({"cost": {"total": 1.5}}))],
        }  # fmt: skip
        repo = SimpleNamespace(list_for_channel=lambda c, **k: runs.get(c, []))
        with (
            patch("config.channels.list_channel_ids", return_value=["tapin", "moneywise"]),
            patch("storage.repositories.content_runs.get_content_run_repository",
                  return_value=repo),
        ):  # fmt: skip
            usd, n = run_usage()
        self.assertAlmostEqual(usd, 2.0)
        self.assertEqual(n, 3)


class OpsTests(_LedgerCase):
    def _ops(self, **kw):
        from scripts.ops import COMMANDS

        args = Namespace(channel="tapin", target=None, amount=None, what="", kind="mp4",
                         monthly=False, date="", entry=None)  # fmt: skip
        for key, value in kw.items():
            setattr(args, key, value)
        buf = io.StringIO()
        with redirect_stdout(buf), patch("core.money.ledger.run_usage", return_value=(0.0, 0)):
            code = COMMANDS["spend"][1](args)
        return code, buf.getvalue()

    def test_add_list_and_end(self):
        code, out = self._ops(target="add", amount=10.0, what="YouTube ads", kind="ads",
                              date="2026-10-04")  # fmt: skip
        self.assertEqual(code, 0)
        self.assertIn("Added #1", out)
        code, out = self._ops(target="add", amount=22.0, what="ElevenLabs",
                              kind="subscription", monthly=True, date="2026-09-01")  # fmt: skip
        code, out = self._ops()
        self.assertIn("Spent so far:", out)
        self.assertIn("#1", out)
        self.assertIn("YouTube ads", out)
        self.assertIn("monthly", out)
        code, out = self._ops(target="end", entry=2, date="2026-10-01")
        self.assertEqual(code, 0)
        self.assertIn("Ended #2", out)

    def test_a_bad_add_says_what_is_missing(self):
        code, out = self._ops(target="add", amount=None, what="x", kind="ads")
        self.assertEqual(code, 2)
        self.assertIn("--amount", out)
        code, out = self._ops(target="add", amount=5.0, what="x", kind="mp4")
        self.assertEqual(code, 2)
        self.assertIn("--kind", out)


class ShownTests(unittest.TestCase):
    def test_status_shows_it(self):
        from core.status import build_status_lines

        with patch("core.money.ledger.spend_line", return_value="Spent so far: $54.00"):
            self.assertIn("Spent so far: $54.00", build_status_lines("tapin"))

    def test_startup_shows_it(self):
        with open("main.py", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("spend_line", text)


if __name__ == "__main__":
    unittest.main()
