"""#1067 the new-video page shows angle 1 and the intent read before discovery.

Enter on the topic starts the run with that idea.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tests.qt_support import requires_qt


@requires_qt
class TestIntentCard(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            QApplication([])
        from core import themes

        previous = themes._channel_theme
        self.addCleanup(setattr, themes, "_channel_theme", previous)

    def test_the_card_shows_angle_one_and_the_read(self):
        from apis.topic_variants import idea_angle
        from desktop.window import RunWindow

        idea = "Chargers reasons for hope"
        window = RunWindow()
        self.addCleanup(window.close)
        window.topic.setText(idea)
        with patch(
            "core.llm_router.complete",
            return_value="Chargers reasons for hope outlook",
        ):
            shown = idea_angle(idea, "tapin")
            window.topic.editingFinished.emit()
        text = window.intent_card.text()
        self.assertIn(shown, text)
        self.assertIn("Intent: hope", text)
        self.assertIn("Source: cue", text)
        self.assertIn("Cue: hope", text)

    def test_enter_on_the_topic_keeps_that_idea(self):
        from desktop.window import RunWindow

        idea = "Chargers reasons for hope"
        window = RunWindow()
        self.addCleanup(window.close)
        window.topic.setText(idea)
        with (
            patch("core.llm_router.complete", return_value=idea),
            patch("desktop.window.start_run_worker") as start,
        ):
            start.return_value.is_alive.return_value = False
            window.topic.returnPressed.emit()
        start.assert_called_once()
        self.assertEqual(start.call_args.kwargs["topic"], idea)

    def test_the_angle_step_dropdown_sends_m_then_the_mode_key(self):
        from core.ask_bridge import AskRequest
        from desktop.window import RunWindow

        window = RunWindow()
        self.addCleanup(window.close)
        window._show_request(
            AskRequest(
                prompt="\n  Choose 1-6 (Enter = your idea, M = change mode): ",
                kind="choice",
                gate="angles",
                payload={
                    "intent": "hope",
                    "source": "model",
                    "cue": "reasons for hope",
                    "also": "",
                    "also_cue": "",
                    "detected": "",
                },
            )
        )
        text = window.intent_card.text()
        self.assertIn("Intent: hope", text)
        self.assertIn("Source: model", text)
        self.assertIn("Cue: reasons for hope", text)
        keys = [window.mode_box.itemData(i) for i in range(window.mode_box.count())]
        # #1588 (2026-10-28): "v" - a preview of a coming game, with its call; #1594 "s" - the
        # story, a headline told as what happened and why fans care.
        self.assertEqual(keys, ["n", "h", "t", "p", "e", "u", "l", "c", "b", "r", "v", "s"])
        window.mode_box.setCurrentIndex(keys.index("p"))
        self.assertEqual(window._bridge._answers.get_nowait(), "m")
        window._show_request(AskRequest(prompt="  Mode (Enter = keep this one): ", kind="text"))
        self.assertEqual(window._bridge._answers.get_nowait(), "p")


class TestAngleAskPayload(unittest.TestCase):
    def test_the_real_angle_prompt_is_the_angle_choice(self):
        from core.ask_bridge import classify_prompt

        kind, gate = classify_prompt("\n  Choose 1-6 (Enter = your idea, M = change mode): ")
        self.assertEqual((kind, gate), ("choice", "angles"))

    def test_the_angle_ask_puts_the_discovery_read_on_the_payload(self):
        import threading
        from types import SimpleNamespace

        import main
        from core.ask import reset_backend, set_backend
        from core.ask_bridge import AskBridge, BridgeBackend

        bridge = AskBridge()
        set_backend(BridgeBackend(bridge))
        self.addCleanup(reset_backend)
        discovery = SimpleNamespace(
            meta={
                "intent_read": {
                    "intent": "plan",
                    "source": "model",
                    "cue": "turn it around",
                }
            }
        )
        seen: dict = {}

        def answer() -> None:
            req = bridge.wait_request(timeout=2)
            seen["payload"] = None if req is None else req.payload
            bridge.submit("1")

        threading.Thread(target=answer).start()
        got = main._ask_angle(discovery, "\n  Choose 1-6 (Enter = your idea, M = change mode): ")
        self.assertEqual(got, "1")
        self.assertEqual(seen["payload"]["intent"], "plan")
        self.assertEqual(seen["payload"]["source"], "model")
        self.assertEqual(seen["payload"]["cue"], "turn it around")
