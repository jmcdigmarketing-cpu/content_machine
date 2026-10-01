"""#585 and #574: how useful each signal has been, at discovery, and skipping the useless.

#585: the health block said which signals were "active" this run - not whether they
had ever fed the script. It now prints, from #575's recorded runs, how often each
signal fed the prompt (`Fed the script (last N runs): rawg 3/3 · never: news 0/3`), and
the `v` view adds `fed N/M` per signal. Runs are this channel's only: wave 51's
`load_runs` mixed tapin and moneywise snapshots and `ops signal-audit` ignored --channel.

#574 (operator: you approve each skip): `ops signal-audit --skip news --note ...` records
the audit's evidence and the date (decisions §19); discovery then leaves the signal out
- through `register_signals._skip_signals`, so every reader of `CONTENT_SKIP_SIGNALS`
honours it - and the health block names it. `--unskip` reverses it. Nothing skips itself.
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

RAWG = [{"name": "Elden Ring Nightreign", "released": "2025-05-30"}]


def _sig(data, *, active=True):
    return {"connected": True, "active": active, "status": "ok", "data": data}


class _Traces(unittest.TestCase):
    RUNS = (
        (1, "tapin", "GTA 6"),
        (2, "tapin", "Uncharted 5"),
        (3, "tapin", "UFC 320"),
        (4, "moneywise", "ISA allowance"),
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        for run_id, channel, topic in self.RUNS:
            signals = {"rawg": _sig(RAWG), "news": _sig(None, active=False)}
            if channel == "moneywise":
                signals = {"fred": _sig({"series": "CPI", "value": 3.1})}
            with open(os.path.join(d, f"{run_id}.signals.json"), "w", encoding="utf-8") as f:
                json.dump({"signals": signals}, f)
            with open(os.path.join(d, f"{run_id}.json"), "w", encoding="utf-8") as f:
                json.dump({"run_id": run_id, "selected_topic": topic, "channel_id": channel}, f)
        self._patches = [
            patch("core.run_trace.TRACES_DIR", d),
            patch("core.runs.signal_skips.SKIPS_FILE", os.path.join(d, "signal_skips.json")),
        ]
        for p in self._patches:
            p.start()
        from core.runs import signal_audit

        signal_audit.reset_cache()

    def tearDown(self):
        from core.runs import signal_audit

        for p in reversed(self._patches):
            p.stop()
        signal_audit.reset_cache()
        self._tmp.cleanup()

    def _health(self, signals, *, channel="tapin", expand=False):
        from core.ui import display_signal_health

        lines: list[str] = []
        with patch("core.ask.ask_text", return_value="v" if expand else ""):
            display_signal_health(
                signals,
                channel_id=channel,
                print_fn=lambda *a: lines.append(" ".join(map(str, a))),
                ask=expand,
            )
        return "\n".join(lines)


class ContributionAtDiscoveryTests(_Traces):
    def test_runs_are_this_channels_only(self):
        from core.runs.signal_audit import load_runs

        self.assertEqual([r.run_id for r in load_runs(channel_id="tapin")], [3, 2, 1])
        self.assertEqual([r.run_id for r in load_runs(channel_id="moneywise")], [4])

    def test_the_health_block_says_what_fed_the_script(self):
        text = self._health({"rawg": _sig(RAWG), "news": _sig(None, active=False)})
        self.assertIn("Fed the script (last 3 runs): rawg 3/3", text)
        self.assertIn("never: news 0/3", text)

    def test_the_expanded_view_adds_it_per_signal(self):
        text = self._health({"rawg": _sig(RAWG)}, expand=True)
        self.assertIn("fed 3/3", text)

    def test_too_few_runs_says_nothing(self):
        text = self._health({"fred": _sig({"x": 1})}, channel="moneywise")
        self.assertNotIn("Fed the script", text)

    def test_ops_signal_audit_honours_the_channel(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            COMMANDS["signal-audit"][1](Namespace(channel="moneywise", skip="", unskip="", note=""))
        self.assertIn("over 1 recorded run", buf.getvalue())
        self.assertNotIn("rawg", buf.getvalue())


class ApprovedSkipTests(_Traces):
    def _ops(self, **kw):
        from scripts.ops import COMMANDS

        args = Namespace(channel="tapin", skip="", unskip="", note="")
        for k, v in kw.items():
            setattr(args, k, v)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["signal-audit"][1](args)
        return code, buf.getvalue()

    def test_a_skip_is_recorded_with_its_evidence_and_honoured(self):
        from apis.register_signals import _skip_signals
        from core.runs.signal_skips import load_skips

        code, out = self._ops(skip="news", note="no articles for gaming topics")
        self.assertEqual(code, 0)
        self.assertIn("news will be skipped", out)
        entry = load_skips()["tapin"]["news"]
        self.assertEqual(entry["evidence"], "fed the script on 0 of 3 recorded runs")
        self.assertEqual(entry["note"], "no articles for gaming topics")
        self.assertIn("news", _skip_signals("tapin"))
        self.assertNotIn("news", _skip_signals("moneywise"))

    def test_skipping_a_useful_signal_warns_but_is_your_call(self):
        code, out = self._ops(skip="rawg")
        self.assertEqual(code, 0)
        self.assertIn("not a retirement candidate", out)

    def test_unskip_reverses_it(self):
        from apis.register_signals import _skip_signals

        self._ops(skip="news")
        self._ops(unskip="news")
        self.assertNotIn("news", _skip_signals("tapin"))

    def test_the_health_block_names_the_skip(self):
        self._ops(skip="news")
        self.assertIn(
            "Skipped by you (never fed the script): news", self._health({"rawg": _sig(RAWG)})
        )

    def test_discovery_leaves_it_out(self):
        from apis import register_signals

        self._ops(skip="news")
        sources = register_signals._active_signal_sources(topic="", channel_id="tapin")
        self.assertNotIn("news", [name for name, _fn in sources])


if __name__ == "__main__":
    unittest.main()
