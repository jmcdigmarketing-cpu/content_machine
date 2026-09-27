"""#902-#904: three glitches in the operator's first `ops reliability` after wave 44.

On the PC (Windows PowerShell), 2026-09-27:

    YouTube units: ???????????????? 816/10000 used (~9,184 left today; ...) - resets ...
    Reliability trend (last 14 day(s)) ... 2026-09-15 -> 2028-09-11
    ! competitor '(none)' no config at C:\\dev\\content_machine\\config\\competitors\\default.json

The em dash in "— resets" arrived as "-" while the meter blocks arrived as "?": the text
went through a legacy code page that best-fits what it can and replaces the rest. The
trend's last row was dated two years ahead (a test wrote it before #892 redirected the
history file), so every "now=" came from it. And with no channel pinned, competitor
health checked the placeholder `default` channel, which has no competitors file.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch


class MeterTests(unittest.TestCase):
    def _meter(self, *, os_name: str, env: dict[str, str]):
        from core import themes

        with (
            patch.object(themes.os, "name", os_name),
            patch.dict(os.environ, env, clear=False),
            patch.object(themes.sys, "stdout", SimpleNamespace(encoding="utf-8")),
        ):
            return themes.meter(816, 10000, width=16)

    def test_a_windows_console_gets_the_ascii_meter(self):
        bar = self._meter(os_name="nt", env={"WT_SESSION": "", "CONTENT_UI_UNICODE": ""})
        self.assertTrue(set(bar.split()[0]) <= {"#", "."}, bar)

    def test_windows_terminal_keeps_the_blocks(self):
        bar = self._meter(os_name="nt", env={"WT_SESSION": "abc", "CONTENT_UI_UNICODE": ""})
        self.assertFalse(set(bar.split()[0]) <= {"#", "."}, bar)

    def test_the_operator_can_ask_for_unicode(self):
        bar = self._meter(os_name="nt", env={"WT_SESSION": "", "CONTENT_UI_UNICODE": "1"})
        self.assertFalse(set(bar.split()[0]) <= {"#", "."}, bar)

    def test_elsewhere_nothing_changes(self):
        bar = self._meter(os_name="posix", env={"WT_SESSION": "", "CONTENT_UI_UNICODE": ""})
        self.assertFalse(set(bar.split()[0]) <= {"#", "."}, bar)


class FutureHistoryTests(unittest.TestCase):
    ROWS: ClassVar[list[dict]] = [
        {"date": "2026-09-15", "cache_hit_rate": 0.2},
        {"date": "2026-09-27", "cache_hit_rate": 0.18},
        {"date": "2028-09-11", "cache_hit_rate": 0.9},
    ]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "reliability_history.json"
        self.path.write_text(json.dumps(self.ROWS), encoding="utf-8")
        self._patch = patch("core.reliability_history._path", return_value=str(self.path))
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def test_the_helper(self):
        from core.reliability_history import drop_future_rows

        kept = drop_future_rows(self.ROWS, date(2026, 9, 27))
        self.assertEqual([r["date"] for r in kept], ["2026-09-15", "2026-09-27"])

    def test_the_trend_ends_today(self):
        from core import reliability_history

        with patch.object(reliability_history, "date") as fake:
            fake.today.return_value = date(2026, 9, 27)
            text = reliability_history.render()
        self.assertIn("2026-09-15 -> 2026-09-27", text)
        self.assertNotIn("2028", text)

    def test_the_next_record_heals_the_file(self):
        from core import reliability_history

        with patch.object(reliability_history, "date") as fake:
            fake.today.return_value = date(2026, 9, 27)
            reliability_history.record({})
        dates = [r["date"] for r in json.loads(self.path.read_text(encoding="utf-8"))]
        self.assertNotIn("2028-09-11", dates)
        self.assertIn("2026-09-27", dates)


class CompetitorDefaultTests(unittest.TestCase):
    def _section(self, channel: str):
        from core import reliability

        seen: list[str] = []

        def inspect(cid, **_kw):
            seen.append(cid)
            return cid

        with (
            patch.dict(os.environ, {"CONTENT_CHANNEL_ID": channel}),
            patch("core.competitor_health.inspect_competitors", side_effect=inspect),
            patch("core.competitor_health.warning_lines", side_effect=lambda r: [f"warn {r}"]),
        ):
            return reliability._competitor_health_section(), seen

    def test_no_pinned_channel_checks_the_real_channels(self):
        lines, seen = self._section("")
        self.assertNotIn("default", seen)
        self.assertIn("tapin", seen)
        self.assertIn("moneywise", seen)
        self.assertFalse(any("default" in line for line in lines), lines)

    def test_a_pinned_channel_is_checked_alone(self):
        _lines, seen = self._section("tapin")
        self.assertEqual(seen, ["tapin"])


if __name__ == "__main__":
    unittest.main()
