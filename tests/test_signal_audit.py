"""#588 and #575: which signals are frozen, and which ever feed the script.

#588: a signal served from a stale cache returns the same payload for every topic and
reads as healthy - "active", data present. `frozen_signals` hashes each run's payload
(from #386's snapshots, `data/traces/<run>.signals.json`) and flags a signal whose
payload repeats unchanged on 3+ runs across 2+ different topics. Popularity signals
(`core/signal_facts.DEMAND_SIGNALS`) are topic-blind by design and listed apart.

#575: "active" is not "useful". `contribution_rows` counts, per signal, the runs it
ran on, was active on, fed fact lines into the prompt on (its own
`format_signal_facts` block), and was cited on (a named entity from those lines is in
the finished script). A signal that fed nothing over 10+ runs is a retirement
candidate; retiring stays the operator's call (decisions §19). `ops signal-audit`.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

RAWG_SAME = [{"name": "Elden Ring Nightreign", "released": "2025-05-30", "rating": 4.2}]


def _sig(data, *, active=True):
    return {"connected": True, "active": active, "status": "ok", "data": data}


def _run(run_id, topic, signals, script=""):
    from core.runs.signal_audit import RunSignals

    return RunSignals(run_id=run_id, topic=topic, signals=signals, script=script)


class FrozenTests(unittest.TestCase):
    def test_the_same_payload_across_topics_is_frozen(self):
        from core.runs.signal_audit import frozen_signals

        runs = [
            _run(1, "GTA 6 trailer", {"rawg": _sig(RAWG_SAME)}),
            _run(2, "Uncharted 5", {"rawg": _sig(RAWG_SAME)}),
            _run(3, "Topuria vs Pereira", {"rawg": _sig(RAWG_SAME)}),
        ]
        rows = frozen_signals(runs)
        self.assertEqual([(r["signal"], r["runs"]) for r in rows], [("rawg", [1, 2, 3])])
        self.assertFalse(rows[0]["expected"])

    def test_one_topic_repeated_is_a_cache_not_a_freeze(self):
        from core.runs.signal_audit import frozen_signals

        runs = [_run(i, "GTA 6 trailer", {"rawg": _sig(RAWG_SAME)}) for i in (1, 2, 3)]
        self.assertEqual(frozen_signals(runs), [])

    def test_a_popularity_signal_is_expected_to_repeat(self):
        from core.runs.signal_audit import frozen_signals

        top = {"top_games": ["Fortnite", "GTA V"]}
        runs = [_run(i, t, {"twitch": _sig(top)}) for i, t in ((1, "a"), (2, "b"), (3, "c"))]
        rows = frozen_signals(runs)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["expected"])


class ContributionTests(unittest.TestCase):
    def test_fed_and_cited_are_counted_per_run(self):
        from core.runs.signal_audit import contribution_rows

        runs = [
            _run(1, "Nightreign", {"rawg": _sig(RAWG_SAME), "news": _sig(None, active=False)},
                 script="Elden Ring Nightreign just dropped a patch."),
            _run(2, "Nightreign", {"rawg": _sig(RAWG_SAME), "news": _sig(None, active=False)},
                 script="Nothing named here."),
        ]  # fmt: skip
        rows = {r["signal"]: r for r in contribution_rows(runs)}
        self.assertEqual(
            (
                rows["rawg"]["runs"],
                rows["rawg"]["active"],
                rows["rawg"]["fed"],
                rows["rawg"]["cited"],
            ),
            (2, 2, 2, 1),
        )
        self.assertEqual((rows["news"]["active"], rows["news"]["fed"]), (0, 0))

    def test_a_signal_that_never_feeds_is_a_candidate(self):
        from core.runs.signal_audit import contribution_rows, retirement_candidates

        runs = [_run(i, f"t{i}", {"news": _sig(None, active=False)}) for i in range(10)]
        self.assertEqual(retirement_candidates(contribution_rows(runs)), ["news"])
        self.assertEqual(retirement_candidates(contribution_rows(runs[:9])), [])


class LoaderAndVerbTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        for run_id, topic in ((7, "GTA 6 trailer"), (8, "Uncharted 5"), (9, "UFC 320")):
            with open(os.path.join(d, f"{run_id}.signals.json"), "w", encoding="utf-8") as f:
                json.dump({"signals": {"rawg": _sig(RAWG_SAME)}}, f)
            with open(os.path.join(d, f"{run_id}.json"), "w", encoding="utf-8") as f:
                json.dump({"run_id": run_id, "selected_topic": topic, "channel_id": "tapin"}, f)
        self._patches = [
            patch("core.run_trace.TRACES_DIR", d),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(
                    get=lambda i: SimpleNamespace(script="Elden Ring Nightreign is back.")
                ),
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def test_runs_load_from_the_snapshots(self):
        from core.runs.signal_audit import load_runs

        runs = load_runs()
        self.assertEqual([r.run_id for r in runs], [9, 8, 7])
        self.assertEqual(runs[0].topic, "UFC 320")
        self.assertIn("Nightreign", runs[0].script)

    def test_ops_signal_audit(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["signal-audit"][1](Namespace(channel="tapin"))
        text = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("rawg", text)
        self.assertIn("frozen", text)
        self.assertIn("3 runs", text)

    def test_the_reliability_line_names_the_frozen_signal(self):
        from core.runs.signal_audit import reliability_line

        self.assertIn("rawg", reliability_line())


if __name__ == "__main__":
    unittest.main()
