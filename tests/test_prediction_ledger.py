"""#113: the ledger freezes every call made at publish, and `ops predictions` scores it.

Beside the engagement prediction (#559), three recommenders make a claim about a video
before it publishes, and none was ever kept: the length recommender (which preset, and the
engaged rate its bucket expects), the post-time recommender (which slot, and that slot's
expected rate) and the report card (the grade shown). Post time is usually applied by
the scheduler itself, so "was it followed" says nothing; what can be checked is each
recommender's own expected rate against the outcome. Report-only and volume-gated:
under five measured videos a row says "collecting", never a rate.
"""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_prediction_freeze import _Case


def _length(choice="2", source="analytics", rate=0.30, n=6):
    return SimpleNamespace(
        length_choice=choice, label="", source=source, avg_engaged_rate=rate,
        supporting_runs=n, rationale="",
    )  # fmt: skip


def _slot(source="analytics", rate=0.25, n=4):
    return SimpleNamespace(
        when_utc=datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc), local_str="", source=source,
        avg_engaged_rate=rate, supporting_samples=n, rationale="",
    )  # fmt: skip


class _Ledger(_Case):
    def setUp(self):
        super().setUp()
        for run in self.repo.runs.values():
            run.timings_json = json.dumps({"length_preset": "2"})
            q = json.loads(run.quality_json)
            q.update({"grade_score": 50 + run.id * 4, "grade_letter": "B"})
            run.quality_json = json.dumps(q)
        self.stack.enter_context(
            patch("core.length_recommender.get_recommended_length", return_value=_length())
        )
        self.stack.enter_context(
            patch("analytics.post_timing.get_recommended_time", return_value=_slot())
        )


class FreezeTests(_Ledger):
    def test_every_call_is_frozen(self):
        from core.predictions.ledger import freeze

        entry = freeze(9, "tapin")
        self.assertEqual(
            entry["length"],
            {"recommended": "2", "chosen": "2", "expected": 0.30, "source": "analytics", "n": 6},
        )
        self.assertEqual(entry["post_time"]["expected"], 0.25)
        self.assertEqual(entry["post_time"]["recommended_at"], "2026-09-30T17:00:00+00:00")
        self.assertEqual(entry["grade"], {"score": 86, "letter": "B"})


class ReportTests(_Ledger):
    def _freeze_all(self, run_ids):
        from core.predictions.ledger import freeze

        for run_id in run_ids:
            freeze(run_id, "tapin")

    def test_under_five_measured_is_collecting(self):
        from core.predictions.ledger import report_lines

        self._freeze_all([1, 2, 3])
        text = "\n".join(report_lines("tapin"))
        self.assertIn("3 frozen, 3 measured", text)
        self.assertIn("collecting", text)
        self.assertNotIn("%", text.split("collecting")[0].splitlines()[-1])

    def test_five_measured_give_errors(self):
        from core.predictions.ledger import ledger_rows, report_lines

        self._freeze_all([1, 2, 3, 4, 9])
        rows = ledger_rows("tapin")
        self.assertEqual(len(rows), 5)
        row9 = next(r for r in rows if r["run_id"] == 9)
        self.assertAlmostEqual(row9["length_error"], 0.90 - 0.30)
        text = "\n".join(report_lines("tapin"))
        self.assertIn("5 frozen, 5 measured", text)
        self.assertIn("length recommender", text)
        self.assertIn("mean |error|", text)
        self.assertIn("grade vs engaged rate: r=", text)

    def test_a_backfilled_prediction_is_counted_apart(self):
        from core.predictions.ledger import freeze, report_lines

        freeze(1, "tapin", backfilled=True)
        self._freeze_all([2, 3, 4, 9])
        self.assertIn("1 backfilled", "\n".join(report_lines("tapin")))

    def test_an_unmeasured_video_is_frozen_not_scored(self):
        from core.predictions.ledger import ledger_rows

        del self.rates[9]
        self._freeze_all([1, 9])
        self.assertEqual([r["run_id"] for r in ledger_rows("tapin")], [1])


class OpsTests(_Ledger):
    def test_the_verb(self):
        from core.predictions.ledger import freeze
        from scripts.ops import COMMANDS

        freeze(1, "tapin")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["predictions"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("Prediction ledger", buf.getvalue())

    def test_the_weekly_report_carries_one_line(self):
        from core.predictions.ledger import summary_line

        self.assertIsNone(summary_line("tapin"))  # nothing frozen yet: silent
        self._freeze_all_one()
        self.assertIn("prediction ledger", summary_line("tapin") or "")

    def _freeze_all_one(self):
        from core.predictions.ledger import freeze

        freeze(1, "tapin")


if __name__ == "__main__":
    unittest.main()
