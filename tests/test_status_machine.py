"""#869: one place to ask "is the machine OK".

Seven verbs each answered part of it (doctor, free-doctor, secrets-doctor, health,
status, all-checks, reliability), so the operator had to know which to run. `ops status`
now ends with a Machine block: one line per family, each naming the verb for the detail.
The detail verbs stay; nothing is removed.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

DOCTOR = {"checks": [{"name": "ollama", "ok": True}, {"name": "feeds", "ok": False}]}
SECRETS = {"required_missing": 1, "placeholder": 2, "present": 9}


def _patches(**over):
    base = {
        "core.ops_doctor.gather": DOCTOR,
        "core.secrets_doctor.gather": SECRETS,
        "core.channel_health.build_health": SimpleNamespace(),
        "core.channel_health.health_line": "Health: GREEN (engagement ok, cadence ok)",
        "core.reliability.summary_line": "Apify ok; 0 signals paused; YouTube uploads left 6",
    }
    base.update(over)
    return [
        patch(target, side_effect=value)
        if isinstance(value, Exception)
        else patch(target, return_value=value)
        for target, value in base.items()
    ]


class MachineLinesTests(unittest.TestCase):
    def _lines(self, **over):
        from core.status_summary import machine_lines

        ps = _patches(**over)
        for p in ps:
            p.start()
        try:
            return machine_lines("tapin")
        finally:
            for p in ps:
                p.stop()

    def test_every_family_has_a_line_naming_its_verb(self):
        text = "\n".join(self._lines())
        self.assertIn("1 of 2 checks pass", text)
        self.assertIn("feeds", text)
        self.assertIn("ops doctor", text)
        self.assertIn("1 required key missing", text)
        self.assertIn("ops secrets-doctor", text)
        self.assertIn("Health: GREEN", text)
        self.assertIn("ops health", text)
        self.assertIn("YouTube uploads left 6", text)
        self.assertIn("ops reliability", text)

    def test_a_failing_family_says_unavailable_and_the_rest_still_print(self):
        text = "\n".join(self._lines(**{"core.ops_doctor.gather": RuntimeError("boom")}))
        self.assertIn("unavailable (see ops doctor)", text)
        self.assertIn("Health: GREEN", text)

    def test_reliability_summary_line_reads_the_snapshot(self):
        from core.reliability import summary_line

        line = summary_line(
            {
                "apify": {"status": "ok"},
                "signals": {"disabled": ["twitch"], "cooldowns": {"rawg": 1}, "persisted": {}},
                "youtube": {"uploads_left": 5},
            }
        )
        self.assertIn("Apify ok", line)
        self.assertIn("2 signals paused", line)
        self.assertIn("uploads left 5", line)


class StatusVerbTests(unittest.TestCase):
    def test_status_prints_the_machine_block(self):
        import argparse
        import io
        from contextlib import redirect_stdout

        from scripts.ops import cmd_status

        out = io.StringIO()
        with (
            patch("core.status.build_status_lines", return_value=["Queue: empty"]),
            patch("core.status_summary.machine_lines", return_value=["Doctor: all 3 checks pass"]),
            redirect_stdout(out),
        ):
            cmd_status(argparse.Namespace(channel="tapin", json=False, out=""))
        self.assertIn("Machine", out.getvalue())
        self.assertIn("Doctor: all 3 checks pass", out.getvalue())


if __name__ == "__main__":
    unittest.main()
