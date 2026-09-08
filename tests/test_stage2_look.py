"""Stage 2 look: QSS from #170 tokens, per-channel chrome, empty/error, DPI.

Fail-then-fix: these import helpers that did not exist on unmodified Stage 1.
Widget construction is skipped when PySide6 is absent (CI has no [app] extra).
"""

from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from core.ask import ask_choice, ask_confirm, reset_backend, set_backend
from core.ask_bridge import AUTH_PROMPT, AskBridge, BridgeBackend
from core.design_tokens import channel_tokens, load_tokens, role_ansi_pair
from core.operator_facts import operator_key_fact_char_budget


class TestQssFromShippedTokens(unittest.TestCase):
    def test_tapin_and_moneywise_qss_disagree_and_use_token_hex(self):
        from core.chrome import build_qss

        tokens = load_tokens()
        tapin = build_qss("tapin")
        money = build_qss("moneywise")
        self.assertNotEqual(tapin, money)
        tapin_border = str(channel_tokens("tapin")["header_border"])
        money_border = str(channel_tokens("moneywise")["header_border"])
        self.assertIn(tapin_border, tapin)
        self.assertIn(money_border, money)
        self.assertNotIn(tapin_border, money)
        primary = str(tokens["roles"]["primary"]["hex"])
        self.assertTrue(primary in tapin or primary in money)
        body_px = int(tokens["type"]["body"])
        self.assertIn(f"{body_px}px", tapin)
        page = int(tokens["spacing"]["page"])
        self.assertIn(f"{page}px", tapin)
        tapin_bg = str(channel_tokens("tapin")["end_card_bg"])
        self.assertIn(tapin_bg, tapin)
        self.assertNotIn("QPushButton { }", tapin)

    def test_reduced_chroma_and_high_contrast_and_reduced_motion_are_token_classes(self):
        from core.chrome import build_qss, themed_css

        plain = build_qss("tapin")
        chroma = build_qss("tapin", reduced_chroma=True)
        contrast = build_qss("tapin", high_contrast=True)
        motion = build_qss("tapin", reduced_motion=True)
        self.assertNotIn("filter:", chroma)
        self.assertIn("reduced-chroma", chroma)
        self.assertNotIn("reduced-chroma", plain)
        self.assertIn("filter: saturate(0.45)", themed_css("tapin"))
        self.assertIn("high-contrast", contrast.lower().replace("_", "-"))
        self.assertGreater(contrast.count("#"), 3)
        self.assertIn("animation-duration", motion)
        self.assertIn("0", motion)

    def test_colorblind_qss_uses_colorblind_role_hex_not_default_success(self):
        from core.chrome import build_qss

        tokens = load_tokens()
        default_ok = str(tokens["roles"]["success"]["hex"])
        cb_ok = str(tokens["colorblind_roles"]["success"]["hex"])
        self.assertNotEqual(default_ok.lower(), cb_ok.lower())
        qss = build_qss("tapin", colorblind=True)
        self.assertIn(cb_ok, qss)
        pair = role_ansi_pair("success", colorblind=True)
        self.assertIsNotNone(pair)

    def test_empty_and_error_copy_are_designed_not_qt_defaults(self):
        from core.chrome import empty_state_copy, error_state_copy

        idle = empty_state_copy()
        err = error_state_copy("ffmpeg missing")
        self.assertIn("topic", idle.lower())
        self.assertNotIn("QLabel", idle)
        self.assertIn("ffmpeg missing", err)
        self.assertNotIn("Traceback", err)


class TestDpiWithoutDisplay(unittest.TestCase):
    def test_missing_screen_is_scale_one_not_a_crash(self):
        from core.chrome import device_pixel_ratio

        self.assertEqual(device_pixel_ratio(None), 1.0)
        self.assertEqual(device_pixel_ratio(object()), 1.0)


class TestFactsMeterAndDrop(unittest.TestCase):
    def test_meter_uses_the_live_char_budget(self):
        from desktop.session import facts_meter_line

        budget = operator_key_fact_char_budget()
        line = facts_meter_line("abc")
        self.assertIn("3", line)
        self.assertIn(str(budget), line)
        over = facts_meter_line("x" * (budget + 10))
        self.assertIn(str(budget + 10), over)

    def test_txt_drop_becomes_facts_and_a_url_stays_a_url(self):
        from desktop.session import facts_from_drop

        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "leak.txt"
            note.write_text("Dana White told ESPN the fight is Saturday.\n", encoding="utf-8")
            blob = facts_from_drop([str(note), "https://example.com/card"])
        self.assertIn("Dana White told ESPN the fight is Saturday.", blob)
        self.assertIn("https://example.com/card", blob)

    def test_window_state_round_trips_per_channel_including_screen_name(self):
        from desktop.session import load_window_state, save_window_state

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "window_state.json"
            with patch("desktop.session.window_state_path", return_value=path):
                save_window_state(
                    "tapin",
                    {"x": 12, "y": 34, "w": 900, "h": 700, "screen": "\\\\.\\DISPLAY2"},
                )
                save_window_state(
                    "moneywise",
                    {"x": 1, "y": 2, "w": 800, "h": 600, "screen": "\\\\.\\DISPLAY1"},
                )
                tapin = load_window_state("tapin")
                money = load_window_state("moneywise")
        self.assertEqual(tapin["screen"], "\\\\.\\DISPLAY2")
        self.assertEqual(tapin["w"], 900)
        self.assertEqual(money["screen"], "\\\\.\\DISPLAY1")
        self.assertNotEqual(tapin["x"], money["x"])


class TestAskBackendContract(unittest.TestCase):
    def tearDown(self):
        reset_backend()

    def test_scripted_and_bridge_agree_on_the_same_answers(self):
        from core.ask import ScriptedBackend

        set_backend(ScriptedBackend(["y", "3"]))
        scripted = [
            ask_confirm(AUTH_PROMPT, default=False),
            ask_choice("  Choose 1-5 (Enter = best): "),
        ]
        reset_backend()
        bridge = AskBridge()
        set_backend(BridgeBackend(bridge))
        got: list[object] = []

        def worker():
            got.append(ask_confirm(AUTH_PROMPT, default=False))
            got.append(ask_choice("  Choose 1-5 (Enter = best): "))

        thread = threading.Thread(target=worker)
        thread.start()
        first = bridge.wait_request(timeout=2.0)
        self.assertIsNotNone(first)
        bridge.submit("y")
        second = bridge.wait_request(timeout=2.0)
        self.assertIsNotNone(second)
        bridge.submit("3")
        thread.join(timeout=2.0)
        self.assertEqual(got, scripted)
        self.assertEqual(scripted, [True, "3"])


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None  # type: ignore[misc, assignment]


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestRunWindowLook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def test_stylesheet_is_not_default_qt_and_flips_with_channel(self):
        from desktop.window import RunWindow

        window = RunWindow()
        qss = window.styleSheet()
        self.assertTrue(qss.strip())
        self.assertIn(str(channel_tokens("tapin")["header_border"]), qss)
        window.channel.setCurrentIndex(
            next(
                i
                for i in range(window.channel.count())
                if window.channel.itemData(i) == "moneywise"
            )
        )
        window._apply_look()
        money_qss = window.styleSheet()
        self.assertIn(str(channel_tokens("moneywise")["header_border"]), money_qss)
        self.assertNotIn(str(channel_tokens("tapin")["header_border"]), money_qss)
        self.assertTrue(window.empty_state.text())
        window.close()

    def test_facts_meter_tracks_the_paste_box(self):
        from desktop.window import RunWindow

        window = RunWindow()
        window.facts.setPlainText("hello")
        window._refresh_facts_meter()
        self.assertIn("5", window.facts_meter.text())
        self.assertIn(str(operator_key_fact_char_budget()), window.facts_meter.text())
        window.close()
