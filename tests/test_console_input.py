"""Run 74: buffered console input must never auto-answer a prompt.

The operator pasted a 40-paragraph article at the `Fact N` prompt. The first blank
line ended fact intake; the rest stayed in the Windows console buffer and answered
the prompts that followed. `Proceed?` got Engadget's byline label `by`, read it as
"not y", and discarded the run.

`core/console_input` is the primitive that fixes both halves: *see* that input is
still arriving (so a blank line is a paragraph break, not a terminator) and *read*
what is buffered (so it can be offered back as facts instead of hijacking a gate).

Everything here must be a safe no-op off a real console — CI has no tty.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core import console_input


class TestNoTtyIsAlwaysSafe(unittest.TestCase):
    """CI, pipes, and redirected stdin: never raise, never claim input is pending."""

    def test_input_pending_is_false_without_a_tty(self):
        with patch.object(console_input, "_stdin_is_tty", return_value=False):
            self.assertFalse(console_input.input_pending())

    def test_read_pending_lines_is_empty_without_a_tty(self):
        with patch.object(console_input, "_stdin_is_tty", return_value=False):
            self.assertEqual(console_input.read_pending_lines(), [])

    def test_drain_reports_zero_without_a_tty(self):
        with patch.object(console_input, "_stdin_is_tty", return_value=False):
            self.assertEqual(console_input.drain_stdin(), 0)

    def test_the_real_calls_never_raise_under_the_test_runner(self):
        # Called for real (no patching) — the suite's stdin is not a console.
        self.assertIsInstance(console_input.input_pending(), bool)
        self.assertIsInstance(console_input.read_pending_lines(), list)
        self.assertIsInstance(console_input.drain_stdin(), int)


class TestFailuresAreSwallowed(unittest.TestCase):
    """A platform quirk must degrade to 'nothing pending', never crash a run."""

    def test_input_pending_swallows_backend_errors(self):
        with (
            patch.object(console_input, "_stdin_is_tty", return_value=True),
            patch.object(console_input, "_pending_backend", side_effect=OSError("boom")),
        ):
            self.assertFalse(console_input.input_pending())

    def test_read_pending_lines_swallows_backend_errors(self):
        with (
            patch.object(console_input, "_stdin_is_tty", return_value=True),
            patch.object(console_input, "_read_backend", side_effect=OSError("boom")),
        ):
            self.assertEqual(console_input.read_pending_lines(), [])


class TestBufferedTextBecomesLines(unittest.TestCase):
    """The Engadget paste: CR-separated console text splits into usable lines."""

    def test_carriage_returns_split_into_lines(self):
        raw = "by\rDave Meikleham\rAug. 28, 2026 6:08 pm EST\r"
        with (
            patch.object(console_input, "_stdin_is_tty", return_value=True),
            patch.object(console_input, "_read_backend", return_value=raw),
        ):
            self.assertEqual(
                console_input.read_pending_lines(),
                ["by", "Dave Meikleham", "Aug. 28, 2026 6:08 pm EST"],
            )

    def test_blank_paragraph_breaks_are_preserved_as_empty_lines(self):
        # A paragraph break inside the paste must survive: parse_pasted_block uses
        # it to separate facts. Only trailing blanks are dropped.
        raw = "First paragraph.\r\n\r\nSecond paragraph.\r\n\r\n"
        with (
            patch.object(console_input, "_stdin_is_tty", return_value=True),
            patch.object(console_input, "_read_backend", return_value=raw),
        ):
            self.assertEqual(
                console_input.read_pending_lines(),
                ["First paragraph.", "", "Second paragraph."],
            )

    def test_drain_counts_what_it_discarded(self):
        with (
            patch.object(console_input, "_stdin_is_tty", return_value=True),
            patch.object(console_input, "_read_backend", return_value="by\rDave\r"),
        ):
            self.assertEqual(console_input.drain_stdin(), 2)


if __name__ == "__main__":
    unittest.main()
