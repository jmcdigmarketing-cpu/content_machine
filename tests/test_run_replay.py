"""#386: a run can be replayed offline from what it recorded.

Traces kept status / connected / active / score per signal (`run_trace._slim_signals`),
so a scoring or fact-formatting bug seen in a run could only be reproduced by fetching
the signals again - different answers, more credits. Operator's choice (wave 47): every
run now saves its full signals beside its trace (`data/traces/<run>.signals.json`,
capped, secrets scrubbed, `RUN_SIGNAL_SNAPSHOT=false` to stop), and `ops replay <run>`
re-scores them with today's code: the composite against the recorded one, the signal
facts block, event coverage. No network.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import patch

SECRET = "sk-live-very-secret-value-123456"
TOPIC = "Topuria vs Holloway UFC 308"


def _signals():
    return {
        "news": {
            "connected": True, "active": True, "score": 70.0, "confidence": 0.75, "status": "ok",
            "status_detail": None,
            "data": {"headlines": [{"title": f"Topuria vs Holloway headline {i}",
                                    "source": "ESPN", "description": "x" * 50}
                                   for i in range(60)]},
        },
        "web_search": {
            "connected": True, "active": True, "score": 64.0, "confidence": 0.8, "status": "ok",
            "status_detail": f"https://api.example.com/q?api_key={SECRET}",
            "data": {"provider": "tavily", "answer": "a" * 5000, "results": []},
        },
        "rawg": {"connected": True, "active": False, "score": 0, "confidence": 0,
                 "status": "inactive", "status_detail": None, "data": None},
    }  # fmt: skip


class _TraceDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self._patches = [
            patch("core.run_trace.TRACES_DIR", self.dir),
            patch.dict(os.environ, {"FAKE_SERVICE_API_KEY": SECRET, "RUN_SIGNAL_SNAPSHOT": ""}),
            patch("core.run_trace._llm_calls", return_value=([], 0.0)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _write(self, composite=None):
        from core.run_trace import write_run_trace

        return write_run_trace(
            run_id=42, channel_id="tapin", input_topic=TOPIC, selected_topic=TOPIC,
            status="drafted", signals=_signals(), composite_score=composite,
        )  # fmt: skip

    def _snapshot(self):
        with open(os.path.join(self.dir, "42.signals.json"), encoding="utf-8") as f:
            return json.load(f)


class SnapshotTests(_TraceDir):
    def test_the_full_signals_are_kept_beside_the_trace(self):
        self._write()
        snap = self._snapshot()
        self.assertEqual(set(snap["signals"]), {"news", "web_search", "rawg"})
        self.assertEqual(snap["signals"]["news"]["data"]["headlines"][0]["source"], "ESPN")

    def test_it_is_capped(self):
        self._write()
        snap = self._snapshot()
        self.assertEqual(len(snap["signals"]["news"]["data"]["headlines"]), 25)
        self.assertLessEqual(len(snap["signals"]["web_search"]["data"]["answer"]), 2000)

    def test_secrets_are_scrubbed(self):
        self._write()
        with open(os.path.join(self.dir, "42.signals.json"), encoding="utf-8") as f:
            self.assertNotIn(SECRET, f.read())

    def test_it_can_be_turned_off(self):
        with patch.dict(os.environ, {"RUN_SIGNAL_SNAPSHOT": "false"}):
            self._write()
        self.assertFalse(os.path.exists(os.path.join(self.dir, "42.signals.json")))

    def test_the_trace_list_ignores_it(self):
        from core.run_trace import list_traces

        self._write()
        self.assertEqual([t["run_id"] for t in list_traces()], [42])


class ReplayTests(_TraceDir):
    def _recorded(self):
        from apis.topic_scorer import composite_score

        return composite_score(_signals(), TOPIC, "tapin")

    def test_the_same_code_reproduces_the_score(self):
        from core.runs.replay import replay

        self._write(composite=self._recorded())
        report = replay(42)
        self.assertIsNotNone(report)
        self.assertEqual(report.composite_now, report.composite_recorded)
        self.assertGreater(report.fact_lines, 0)

    def test_a_scoring_change_is_named(self):
        from core.runs.replay import replay, report_lines

        self._write(composite=self._recorded())
        with patch("apis.topic_scorer.get_weights", return_value={"web_search": 1.0}):
            report = replay(42)
        self.assertNotEqual(report.composite_now, report.composite_recorded)
        self.assertIn("changed", "\n".join(report_lines(report)))

    def test_no_snapshot_says_so(self):
        from core.runs.replay import replay

        self.assertIsNone(replay(999))

    def test_no_network(self):
        from core.runs.replay import replay

        self._write(composite=self._recorded())
        with (
            patch("requests.get", side_effect=AssertionError("network")),
            patch("requests.post", side_effect=AssertionError("network")),
        ):
            replay(42)


class OpsTests(_TraceDir):
    def test_the_verb(self):
        from scripts.ops import COMMANDS

        self._write(composite=50.0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["replay"][1](Namespace(target="42", source=None, run_id=None))
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("Replay of run 42", text)
        self.assertIn("composite", text)

    def test_one_signal(self):
        from scripts.ops import COMMANDS

        self._write()
        buf = io.StringIO()
        with redirect_stdout(buf):
            COMMANDS["replay"][1](Namespace(target="42", source="news", run_id=None))
        self.assertIn("ESPN", buf.getvalue())

    def test_a_missing_run(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["replay"][1](Namespace(target="7", source=None, run_id=None))
        self.assertEqual(code, 1)
        self.assertIn("no signal snapshot", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
