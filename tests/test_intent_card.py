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
