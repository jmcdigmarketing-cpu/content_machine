"""#913: the overnight batch's and auto_generate's best-bet picks are recorded too.

#909 kept the pick when the operator took one from the card in `main.py`. The automatic
paths take their topics from the same recommender - `core/batch_generation` from
`get_best_bets`, `scripts/auto_generate` from `get_best_bet` - and dropped the objects
before `run_pipeline`, so every automatic pick was missing from `ops predictions`. Each
record now says who picked (`by`: operator / batch / auto), and the ledger splits them.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_batch_generation import BatchCase, _discovery, _pipeline_result
from tests.test_prediction_ledger import _Ledger


def _bet(topic, rate=0.3):
    return SimpleNamespace(
        topic=topic, domain="ufc", avg_engaged_rate=rate, source="analytics",
        supporting_runs=6, rationale="because",
    )  # fmt: skip


BETS = [_bet("Topuria vs Holloway", 0.31), _bet("Pereira rematch", 0.27)]


class RecordTests(unittest.TestCase):
    def test_who_picked_is_kept(self):
        from core.best_bet import pick_record

        self.assertEqual(pick_record(BETS, 1)["by"], "operator")
        self.assertEqual(pick_record(BETS, 2, by="batch")["by"], "batch")


class BatchTests(BatchCase):
    def test_best_bet_topics_carry_their_rank(self):
        from core import batch_generation as bg

        picks: dict = {}
        with patch("core.best_bet.get_best_bets", return_value=BETS):
            topics = bg.collect_topics("tapin", count=2, picks=picks)
        self.assertEqual(topics, ["Topuria vs Holloway", "Pereira rematch"])
        self.assertEqual(picks["Pereira rematch"]["picked"], 2)
        self.assertEqual(picks["Pereira rematch"]["by"], "batch")
        self.assertEqual(len(picks["Pereira rematch"]["offered"]), 2)

    def test_explicit_topics_are_not_picks(self):
        from core import batch_generation as bg

        picks: dict = {}
        bg.collect_topics("tapin", topics=["my own idea"], picks=picks)
        self.assertEqual(picks, {})

    def test_the_draft_passes_it_to_the_pipeline(self):
        from core import batch_generation as bg
        from core.best_bet import pick_record

        record = pick_record(BETS, 1, by="batch")
        with (
            patch("core.pipeline.run_discovery", return_value=_discovery()),
            patch("core.pipeline.run_pipeline", return_value=_pipeline_result()) as rp,
        ):
            bg.run_batch("tapin", ["Topuria vs Holloway"], picks={"Topuria vs Holloway": record})
        self.assertEqual(rp.call_args.kwargs["best_bet"], record)

    def test_overnight_threads_the_picks(self):
        from unittest.mock import MagicMock

        from core import overnight

        with (
            patch("core.best_bet.get_best_bets", return_value=BETS),
            patch("core.overnight_quota.adjust_count", return_value=(2, "")),
            patch("core.batch_generation.run_batch", return_value=[]) as batch,
            patch("core.channel_health.build_health", return_value=MagicMock()),
            patch("core.channel_health.health_line", return_value=""),
            patch("core.events.emit_event", return_value=True),
            patch("core.signal_canary.check_signals", return_value=[]),
            patch("core.signal_canary.save_results"),
        ):
            overnight.run_overnight("tapin", count=2)
        picks = batch.call_args.kwargs["picks"]
        self.assertEqual(picks["Topuria vs Holloway"]["picked"], 1)


class AutoGenerateTests(unittest.TestCase):
    def test_the_bet_is_recorded_as_automatic(self):
        from scripts import auto_generate

        with (
            patch("core.best_bet.get_best_bet", return_value=BETS[0]),
            patch("builtins.print"),
        ):
            topic, record = auto_generate._pick_topic(
                "tapin", "", True
            )  # fmt: skip
        self.assertEqual(topic, "Topuria vs Holloway")
        self.assertEqual((record["picked"], record["by"]), (1, "auto"))

    def test_an_override_is_not_a_pick(self):
        from scripts import auto_generate

        topic, record = auto_generate._pick_topic("tapin", "typed topic", True)
        self.assertEqual((topic, record), ("typed topic", None))

    def test_it_reaches_run_pipeline(self):
        from core.best_bet import pick_record
        from tests.test_wave19 import _drive_auto_generate

        record = pick_record(BETS[:1], 1, by="auto")
        call = _drive_auto_generate(["--channel", "tapin"], pick=("Topuria vs Holloway", record))
        self.assertEqual(call.kwargs["best_bet"], record)


class LedgerTests(_Ledger):
    def _set_pick(self, run_id, picked, by):
        run = self.repo.runs[run_id]
        features = json.loads(run.features_json or "{}")
        offered = [{"topic": "t", "domain": "ufc", "expected": 0.3, "source": "analytics"}]
        features["best_bet"] = {"offered": offered, "picked": picked, "by": by}
        run.features_json = json.dumps(features)

    def test_the_report_splits_who_picked(self):
        from core.predictions.ledger import freeze, report_lines

        for run_id, by in ((1, "batch"), (2, "operator"), (3, "auto"), (4, "batch"), (9, "")):
            self._set_pick(run_id, 1 if by else None, by or "operator")
            freeze(run_id, "tapin")
        self.assertEqual(freeze(1, "tapin")["best_bet"]["by"], "batch")
        text = "\n".join(report_lines("tapin"))
        self.assertIn("1 by you, 3 automatic", text)

    def test_an_old_record_reads_as_the_operator(self):
        from core.predictions.ledger import freeze

        run = self.repo.runs[9]
        features = json.loads(run.features_json or "{}")
        features["best_bet"] = {"offered": [], "picked": None}
        run.features_json = json.dumps(features)
        self.assertEqual(freeze(9, "tapin")["best_bet"]["by"], "operator")


if __name__ == "__main__":
    unittest.main()
