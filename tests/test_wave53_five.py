"""Wave 53's roadmap items: #929, #591, #573, #586.

#929 the best bet read the newest 30 runs only (`core/best_bet._TOP_N`) while post time,
     the predictor and the ledger read every measured outcome - so a domain's sample
     count depended on which recommender asked. Every measured run now counts; the
     30-run window only bounds runs that have no outcome yet.
#591 nothing recorded how long each signal took - the spinner's "typ ~Ns" is the whole
     discovery phase. The base pool's per-signal seconds go into the run trace
     (`signal_seconds`), and `ops signal-audit` prints p50 / p90 per signal.
#573 the research brief fetched its RSS context keyed by the *angle*, so switching
     angles - or the intelligence report's brief per variant - refetched every feed. It
     now fetches by the run's seed, so one fetch serves every angle.
#586 `ops signal-diff <run A> <run B>`: what each signal returned differently between two
     recorded runs (status, payload, fact lines) - from #386's snapshots, no network.
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


class BestBetWindowTests(unittest.TestCase):
    def test_an_old_measured_run_still_counts(self):
        from core import best_bet

        runs = [
            SimpleNamespace(
                id=i, input_topic=f"GTA 6 news {i}", selected_topic="", composite_score=50
            )
            for i in range(40, 0, -1)
        ]  # newest first; run 1 is the 40th
        log = SimpleNamespace(
            content_run_id=1, metrics_json=json.dumps({"engaged_rate": 0.4}), published_at=None
        )
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_timed_outcomes=lambda c: [log]),
            ),
        ):
            entries = best_bet._build_entries("tapin")
        ids = [e["run_id"] for e in entries]
        self.assertIn(1, ids)
        self.assertEqual(len(ids), best_bet._TOP_N + 1)  # 30 newest + the measured old one


class _Traces(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        self._p = patch("core.run_trace.TRACES_DIR", self.d)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def _run(self, run_id, signals, *, seconds=None, topic="GTA 6"):
        with open(os.path.join(self.d, f"{run_id}.signals.json"), "w", encoding="utf-8") as f:
            json.dump({"signals": signals}, f)
        trace = {"run_id": run_id, "selected_topic": topic, "channel_id": "tapin"}
        if seconds is not None:
            trace["signal_seconds"] = seconds
        with open(os.path.join(self.d, f"{run_id}.json"), "w", encoding="utf-8") as f:
            json.dump(trace, f)


def _sig(data, *, active=True, status="ok"):
    return {"connected": True, "active": active, "status": status, "data": data}


class TimingTests(_Traces):
    def test_the_base_pool_records_seconds_per_signal(self):
        from apis import register_signals

        def fake(topic):
            return _sig({"x": 1})

        with (
            patch.object(
                register_signals, "_active_signal_sources", return_value=(("fast", fake),)
            ),
            patch.object(register_signals, "get_cached", return_value=None),
            patch.object(register_signals, "set_cache"),
            patch("core.discovery_headroom.emit_headroom"),
        ):
            register_signals.build_registry("seed topic")
        seconds = register_signals.base_pool_seconds()
        self.assertIn("fast", seconds)
        self.assertGreaterEqual(seconds["fast"], 0.0)

    def test_the_trace_keeps_them(self):
        from core.run_trace import read_trace, write_run_trace

        with patch("apis.register_signals.base_pool_seconds", return_value={"rawg": 1.25}):
            write_run_trace(
                run_id=5, channel_id="tapin", input_topic="t", selected_topic="t", status="ok"
            )
        self.assertEqual(read_trace(5)["signal_seconds"], {"rawg": 1.25})

    def test_the_audit_prints_p50_and_p90(self):
        from core.runs.signal_audit import report_lines

        for run_id, secs in ((1, 1.0), (2, 2.0), (3, 9.0)):
            self._run(run_id, {"rawg": _sig({"a": run_id})}, seconds={"rawg": secs})
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=SimpleNamespace(get=lambda i: None),
        ):
            text = "\n".join(report_lines(channel_id="tapin"))
        self.assertIn("seconds p50/p90", text)
        self.assertRegex(text, r"rawg\s+.*2\.0s / 9\.0s")


class BriefFetchTests(unittest.TestCase):
    def test_every_angle_of_a_run_fetches_the_seeds_rss(self):
        from core import research_brief

        with (
            patch.object(
                research_brief, "fetch_rss_context", return_value={"headlines": []}
            ) as rss,
            patch.object(research_brief, "_USE_LLM", False),
            patch.object(research_brief, "get_cached", return_value=None),
            patch.object(research_brief, "set_cache"),
            patch.object(research_brief, "enrich_facts", return_value=""),
            patch("analytics.competitor_context.get_competitor_prompt_block", return_value=""),
            patch("apis.stats_context_api.gather_stats_context", return_value={"lines": []}),
        ):
            for angle in ("Critics doubt the new Uncharted", "Uncharted 5 needs Cassie"):
                research_brief.build_research_brief(
                    angle, {}, channel_id="tapin", seed_topic="New Uncharted game"
                )
        self.assertEqual({c.args[0] for c in rss.call_args_list}, {"New Uncharted game"})


class SignalDiffTests(_Traces):
    def test_two_runs_are_compared_per_signal(self):
        from core.runs.signal_audit import diff_runs

        self._run(
            1,
            {
                "rawg": _sig([{"name": "Elden Ring"}]),
                "news": _sig(None, active=False, status="inactive"),
            },
        )
        self._run(
            2,
            {"rawg": _sig([{"name": "Nightreign"}]), "news": _sig({"headlines": [{"title": "x"}]})},
        )
        text = "\n".join(diff_runs(1, 2))
        self.assertIn("rawg: payload changed", text)
        self.assertIn("news: inactive -> ok", text)

    def test_the_ops_verb(self):
        from scripts.ops import COMMANDS

        self._run(1, {"rawg": _sig([{"name": "A"}])})
        self._run(2, {"rawg": _sig([{"name": "A"}])})
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["signal-diff"][1](Namespace(channel="tapin", target="1", run_id=2))
        self.assertEqual(code, 0)
        self.assertIn("rawg: same payload", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
