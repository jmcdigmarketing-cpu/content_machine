"""Stage 1 run window: ask() round-trips on a worker; facts paste feeds the fact loop.

CI has no Qt display. These tests call the toolkit-agnostic bridge and the real
prompt strings from main.py / core/ui.py. Widget construction is skipped when
PySide6 is absent.
"""

from __future__ import annotations

import threading
import unittest

from core.ask import ask_confirm, ask_text, reset_backend, set_backend
from core.ask_bridge import (
    AUTH_PROMPT,
    FACT_PROMPT_NEEDLE,
    GROUND_PROMPT,
    METRICS_PROMPT,
    OVER_PROMPT,
    PROCEED_PROMPT,
    THIN_PROMPT,
    AskBridge,
    BridgeBackend,
    classify_prompt,
    missing_pyside_message,
)


class TestClassifyPrompt(unittest.TestCase):
    def test_five_gates_are_confirm_with_named_gate(self):
        self.assertEqual(classify_prompt(AUTH_PROMPT), ("confirm", "authenticity"))
        self.assertEqual(classify_prompt(GROUND_PROMPT), ("confirm", "grounding"))
        self.assertEqual(classify_prompt(THIN_PROMPT), ("confirm", "thin_facts"))
        self.assertEqual(classify_prompt(OVER_PROMPT), ("confirm", "over_length"))
        self.assertEqual(classify_prompt(METRICS_PROMPT), ("confirm", "metrics"))

    def test_proceed_and_facts_and_angles(self):
        self.assertEqual(classify_prompt(PROCEED_PROMPT), ("proceed", None))
        fact = "  Fact 1 (or `paste`, empty when done): "
        self.assertEqual(classify_prompt(fact), ("fact", None))
        self.assertIn(FACT_PROMPT_NEEDLE, fact)
        self.assertEqual(
            classify_prompt("\n  Choose 1-5 (Enter = best): "),
            ("choice", "angles"),
        )
        self.assertEqual(classify_prompt("  Select 1-4 [2]: "), ("choice", "length"))

    def test_gate_constants_are_the_live_main_and_ui_strings(self):
        """The window classifies the prompts main.py actually prints, not a fixture copy."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        main_src = (root / "main.py").read_text(encoding="utf-8")
        ui_src = (root / "core" / "ui.py").read_text(encoding="utf-8")
        self.assertIn(AUTH_PROMPT, main_src)
        self.assertIn(GROUND_PROMPT, main_src)
        self.assertIn(THIN_PROMPT, main_src)
        self.assertIn(OVER_PROMPT, main_src)
        self.assertIn(METRICS_PROMPT, main_src)
        self.assertIn(PROCEED_PROMPT, ui_src)


class TestAskBridgeRoundTrip(unittest.TestCase):
    def tearDown(self):
        reset_backend()

    def test_worker_ask_confirm_blocks_until_ui_submits(self):
        """The Qt backend posts to a queue and blocks the worker — not input()."""
        bridge = AskBridge()
        set_backend(BridgeBackend(bridge))
        result: list[bool] = []

        def worker():
            result.append(ask_confirm(AUTH_PROMPT, default=False))

        thread = threading.Thread(target=worker)
        thread.start()
        req = bridge.wait_request(timeout=2.0)
        self.assertIsNotNone(req)
        assert req is not None
        self.assertEqual(req.kind, "confirm")
        self.assertEqual(req.gate, "authenticity")
        self.assertEqual(req.prompt, AUTH_PROMPT)
        bridge.submit("y")
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [True])

    def test_facts_paste_answers_the_fact_loop_then_stops(self):
        """Run 73: the article belongs in the paste box, not in PowerShell."""
        bridge = AskBridge()
        bridge.set_fact_lines(
            [
                "Dana White told ESPN the fight is Saturday.",
                "Ilia Topuria is the featherweight champion as of June 2026.",
            ]
        )
        set_backend(BridgeBackend(bridge))
        one = ask_text("  Fact 1 (or `paste`, empty when done): ")
        two = ask_text("  Fact 2 (or `paste`, empty when done): ")
        done = ask_text("  Fact 3 (or `paste`, empty when done): ")
        self.assertEqual(one, "Dana White told ESPN the fight is Saturday.")
        self.assertEqual(two, "Ilia Topuria is the featherweight champion as of June 2026.")
        self.assertEqual(done, "")

    def test_closing_the_bridge_raises_keyboardinterrupt(self):
        bridge = AskBridge()
        set_backend(BridgeBackend(bridge))
        raised: list[BaseException] = []

        def worker():
            try:
                ask_text("  Topic: ")
            except BaseException as exc:
                raised.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertIsNotNone(bridge.wait_request(timeout=2.0))
        bridge.cancel()
        thread.join(timeout=2.0)
        self.assertTrue(raised)
        self.assertIsInstance(raised[0], KeyboardInterrupt)


class TestMissingPysideRefuse(unittest.TestCase):
    def test_message_names_the_extra_and_does_not_look_like_a_crash(self):
        line = missing_pyside_message()
        self.assertIn("PySide6", line)
        self.assertIn("[app]", line)


class TestAngleModeFromTopic(unittest.TestCase):
    def test_run73_reaction_topic_is_not_standard(self):
        from core.angle_intent import ANGLE_REACTION, detect_angle_intent
        from desktop.session import angle_mode_line

        topic = "GTA 6 looks amazing!!!"
        self.assertEqual(detect_angle_intent(topic), ANGLE_REACTION)
        line = angle_mode_line(topic)
        self.assertIn("reaction", line.lower())
        self.assertNotEqual(angle_mode_line("how does the offside rule actually work"), line)


class TestStdoutReachesThePane(unittest.TestCase):
    def test_print_and_emit_both_land_in_the_log(self):
        import threading

        from core.emit import emit, reset_emit, set_emit
        from desktop.session import _gui_emit, capture_stdout

        lines: list[str] = []
        lock = threading.Lock()
        set_emit(_gui_emit(lines, lock))
        try:
            with capture_stdout(lines, lock):
                print("script body line")
                emit("Database: JSON-only")
        finally:
            reset_emit()
        self.assertIn("script body line", lines)
        self.assertTrue(any("Database: JSON-only" in ln for ln in lines))


class TestSpinnerReportsToBridge(unittest.TestCase):
    def tearDown(self):
        from core.ask_bridge import set_current_bridge

        set_current_bridge(None)

    def test_report_reaches_the_bridge(self):
        from core.ask_bridge import AskBridge, set_current_bridge
        from core.ui import DiscoverySpinner

        bridge = AskBridge()
        set_current_bridge(bridge)
        spinner = DiscoverySpinner("Discovery")
        spinner.report("signals", 1, 3, "tapology")
        tick = bridge.progress()
        self.assertIsNotNone(tick)
        assert tick is not None
        self.assertEqual(tick.phase, "signals")
        self.assertEqual(tick.detail, "tapology")


class TestOpsRunWindowRegistered(unittest.TestCase):
    def test_verb_is_in_the_live_registry(self):
        from scripts.ops import COMMANDS

        self.assertIn("run-window", COMMANDS)


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None  # type: ignore[misc, assignment]


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestRunWindowWidgets(unittest.TestCase):
    def test_shipped_channels_and_a_large_facts_box(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from desktop.window import RunWindow

        if QApplication.instance() is None:
            QApplication([])
        window = RunWindow()
        ids = [window.channel.itemData(i) for i in range(window.channel.count())]
        self.assertIn("tapin", ids)
        self.assertIn("moneywise", ids)
        self.assertGreaterEqual(window.facts.minimumHeight(), 160)
        window.close()


class TestClosingTheWindowDoesNotDestroyARun(unittest.TestCase):
    """Stage 1 exists because "two `KeyboardInterrupt`s in run 73 destroyed whole
    runs" (`docs/desktop_app.md`). As shipped, the close button reproduced that:
    the worker is `daemon=True` and never joined, and `AskBridge.cancel()` only
    unblocks a worker *currently sitting in an ask*. A worker inside TTS, ffmpeg
    or an upload noticed nothing, `app.exec()` returned, and the interpreter
    exited without waiting — orphaned ffmpeg, half-written mp4, spent quota.
    """

    def test_a_worker_between_steps_is_waited_for(self):
        from core.ask_bridge import AskBridge
        from desktop.session import shutdown_worker

        bridge = AskBridge()
        stopped = threading.Event()

        def body():
            try:
                # Blocks until cancel() pushes the sentinel, which surfaces as
                # KeyboardInterrupt — the same signal the CLI worker unwinds on.
                bridge.ask_text("Topic?")
            except KeyboardInterrupt:
                pass
            stopped.set()

        worker = threading.Thread(target=body, daemon=True)
        worker.start()
        clean = shutdown_worker(worker, bridge, timeout=5.0)
        self.assertTrue(clean, "close did not wait for a cancellable worker")
        self.assertTrue(stopped.is_set())
        self.assertFalse(worker.is_alive())

    def test_a_worker_mid_render_is_reported_not_silently_orphaned(self):
        """A worker inside ffmpeg cannot be cancelled. Closing is still allowed —
        trapping the operator is worse — but it must say what it is abandoning
        rather than dropping the run on the floor in silence."""
        from core.ask_bridge import AskBridge
        from desktop.session import shutdown_worker

        bridge = AskBridge()
        release = threading.Event()
        worker = threading.Thread(target=release.wait, daemon=True)
        worker.start()
        try:
            with self.assertLogs("content_machine.desktop.session", level="WARNING") as logs:
                clean = shutdown_worker(worker, bridge, timeout=0.2)
            self.assertFalse(clean)
            self.assertTrue(any("still running" in m.lower() for m in logs.output), logs.output)
        finally:
            release.set()
            worker.join(timeout=2)
