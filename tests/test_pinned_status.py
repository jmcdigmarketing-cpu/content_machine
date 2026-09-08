"""#481 pinned status: formatter is real; emit invokes it; CSI is TTY-only."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apis.youtube_quota import format_uploads_left
from core import emit as emit_mod
from core.pinned_status import (
    format_pinned_status,
    last_pin_text,
    pin_csi,
    pin_enabled,
    reset_pin,
    set_pin_context,
)


class TestPinnedStatusFormatter(unittest.TestCase):
    def test_line_uses_real_uploads_left_and_channel_and_cost(self):
        summary = {"remaining": 3200}
        uploads = format_uploads_left(summary).splitlines()[0]
        line = format_pinned_status("tapin", quota_summary=summary, cost=0.12)
        self.assertIn("tapin", line)
        self.assertIn(uploads, line)
        self.assertIn("0.12", line)

    def test_pin_disabled_when_no_color_or_not_tty(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}, clear=False):
            self.assertFalse(pin_enabled())
        with patch.dict(os.environ, {"NO_COLOR": ""}, clear=False):
            with patch("sys.stdout.isatty", return_value=False):
                self.assertFalse(pin_enabled())

    def test_csi_wraps_the_formatted_line(self):
        body = "tapin  ~2 upload(s)"
        wrapped = pin_csi(body, rows=24)
        self.assertIn(body, wrapped)
        self.assertIn("\033[", wrapped)
        self.assertIn("24;1H", wrapped)

    def test_emit_invokes_the_formatter(self):
        summary = {"remaining": 3200}
        expected = format_pinned_status("moneywise", quota_summary=summary, cost=1.5)
        reset_pin()
        set_pin_context("moneywise", quota_summary=summary, cost=1.5)
        lines: list[str] = []
        emit_mod.set_emit(lambda *a, **k: lines.append(" ".join(str(x) for x in a)))
        try:
            emit_mod.emit("hello")
            self.assertEqual(last_pin_text(), expected)
            self.assertIn("hello", lines)
        finally:
            emit_mod.reset_emit()
            reset_pin()


class TestThePinDoesNotReadDiskPerLine(unittest.TestCase):
    """`emit()` calls `refresh_pin()`, which reaches `format_uploads_left` ->
    `get_usage_summary` -> `json.load(data/youtube_quota.json)`. There are 27
    `print_fn=emit` defaults in `core/ui.py`, several inside loops, so a chatty
    phase re-read the quota file once per printed line -- and did it even when
    `pin_enabled()` is False and nothing is painted at all.

    The pin still refreshes; it just stops recomputing faster than the number can
    possibly change.
    """

    def test_a_burst_of_emits_formats_once(self):
        calls = {"n": 0}
        real = format_pinned_status

        def counting(*a, **k):
            calls["n"] += 1
            return real(*a, **k)

        reset_pin()
        set_pin_context("tapin", quota_summary={"remaining": 10}, cost=0.0)
        emit_mod.set_emit(lambda *a, **k: None)
        try:
            with patch("core.pinned_status.format_pinned_status", side_effect=counting):
                for _ in range(25):
                    emit_mod.emit("line")
        finally:
            emit_mod.reset_emit()
            reset_pin()
        self.assertEqual(calls["n"], 1, f"formatted {calls['n']} times for 25 emitted lines")
