"""#909: the run records whether its topic was a best bet, and the ledger scores it.

`main.py` showed the best-bet card and took the pick, and nothing kept it: `menu_path` is
the menu, not the pick, so the prediction ledger (#113) could score every recommender but
the one on the first screen. The pick is now `features["best_bet"]` - what was offered
(topic, domain, the engaged rate it expected, its source) and which rank was taken, or
None when the operator typed their own. `ledger.freeze` keeps it and `ops predictions`
scores it: the pick's own error, and picked vs own-topic outcomes.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.test_prediction_ledger import _Ledger


def _bet(topic, rate, source="analytics"):
    return SimpleNamespace(
        topic=topic, domain="ufc", avg_engaged_rate=rate, source=source,
        supporting_runs=6, rationale="",
    )  # fmt: skip


OPTIONS = [_bet("Topuria vs Holloway", 0.30), _bet("Pereira rematch", 0.25, "score")]


class RecordTests(unittest.TestCase):
    def test_a_pick(self):
        from core.best_bet import pick_record

        rec = pick_record(OPTIONS, 1)
        self.assertEqual(rec["picked"], 1)
        self.assertEqual(rec["offered"][0], {
            "topic": "Topuria vs Holloway", "domain": "ufc", "expected": 0.30, "source": "analytics",
        })  # fmt: skip

    def test_typing_your_own(self):
        from core.best_bet import pick_record

        self.assertIsNone(pick_record(OPTIONS, None)["picked"])
        self.assertEqual(pick_record([], None), {"offered": [], "picked": None})

    def test_an_out_of_range_pick_is_none(self):
        from core.best_bet import pick_record

        self.assertIsNone(pick_record(OPTIONS, 7)["picked"])


class WiringTests(unittest.TestCase):
    def test_run_pipeline_takes_it(self):
        import inspect

        from core.pipeline import run_pipeline

        self.assertIn("best_bet", inspect.signature(run_pipeline).parameters)

    def test_main_records_and_passes_it(self):
        text = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("pick_record(options,", text)
        self.assertIn("best_bet=best_bet_pick", text)


class LedgerTests(_Ledger):
    def _set_pick(self, run_id, picked, expected=0.30, source="analytics"):
        run = self.repo.runs[run_id]
        features = json.loads(run.features_json or "{}")
        offered = [{"topic": "t", "domain": "ufc", "expected": expected, "source": source}]
        features["best_bet"] = {"offered": offered, "picked": picked}
        run.features_json = json.dumps(features)

    def test_freeze_keeps_the_pick(self):
        from core.predictions.ledger import freeze

        self._set_pick(9, 1)
        entry = freeze(9, "tapin")
        self.assertEqual(
            entry["best_bet"], {"picked": True, "rank": 1, "expected": 0.30, "source": "analytics"}
        )

    def test_typed_own_topic(self):
        from core.predictions.ledger import freeze

        self._set_pick(9, None)
        self.assertEqual(freeze(9, "tapin")["best_bet"]["picked"], False)

    def test_the_report_row(self):
        from core.predictions.ledger import freeze, ledger_rows, report_lines

        for run_id in (1, 2, 3, 4, 9):
            self._set_pick(run_id, 1 if run_id != 2 else None)
            freeze(run_id, "tapin")
        rows = {r["run_id"]: r for r in ledger_rows("tapin")}
        self.assertAlmostEqual(rows[9]["best_bet_error"], 0.90 - 0.30)
        self.assertNotIn("best_bet_error", rows[2])
        text = "\n".join(report_lines("tapin"))
        self.assertIn("best-bet pick", text)
        self.assertIn("picked 4", text)
        self.assertIn("own topic 1", text)


if __name__ == "__main__":
    unittest.main()
