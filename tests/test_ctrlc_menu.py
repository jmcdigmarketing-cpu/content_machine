"""#484: Ctrl+C at a prompt returns to the menu instead of freezing/killing the process."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestCtrlCReturnsToMenu(unittest.TestCase):
    def test_keyboard_interrupt_during_topic_prompt_does_not_systemexit(self):
        """Run 73 lost two discovery runs because the frozen process was the only copy."""
        import main as app

        with (
            patch.object(app, "check_channel_setup", return_value=SimpleNamespace(ok=True)),
            patch.object(app, "display_upload_queue"),
            patch("core.cadence.cadence_status", return_value=None),
            patch("core.cadence.display_cadence"),
            patch("core.metrics_gate.metrics_gate_reason", return_value=None),
            patch("core.best_bet.get_best_bets", return_value=[]),
            patch.object(app, "ask_text", side_effect=KeyboardInterrupt),
            patch.object(app, "run_discovery") as discovery,
        ):
            try:
                app._run_new_video_flow("tapin")
            except SystemExit as exc:
                self.fail(f"Ctrl+C exited the process: {exc}")
            except KeyboardInterrupt:
                self.fail("Ctrl+C escaped the video flow instead of returning to the menu")
        discovery.assert_not_called()
