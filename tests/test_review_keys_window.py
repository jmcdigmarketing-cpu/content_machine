"""#706. ReviewWindow.keyPressEvent with a fake player, no decode.

All four construction sites pass an empty mp4 path, so the QMediaPlayer branch
never runs in the suite. Injecting `_player` covers J/K/L/comma/period/h/S/?
without QtMultimedia decode.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - app extra is optional outside CI
    QApplication = None  # type: ignore[misc, assignment]


class _RecordingPlayer:
    def __init__(self, position: int = 12_000, duration: int = 60_000):
        self._position = position
        self._duration = duration
        self.positions: list[int] = []
        self.actions: list[str] = []

    def position(self) -> int:
        return self._position

    def duration(self) -> int:
        return self._duration

    def setPosition(self, value: int) -> None:
        self._position = value
        self.positions.append(value)

    def pause(self) -> None:
        self.actions.append("pause")

    def play(self) -> None:
        self.actions.append("play")


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestReviewWindowKeyDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        from desktop.review import ReviewWindow

        return ReviewWindow(
            context={
                "mp4_path": "",
                "run_id": 706,
                "run_status": "drafted",
                "can_approve": False,
                "refuse_reason": "No file",
                "grade": "n/a",
                "channel_id": "tapin",
            }
        )

    @staticmethod
    def _press(window, text: str, key) -> None:
        event = QKeyEvent(
            QEvent.Type.KeyPress,
            key,
            Qt.KeyboardModifier.NoModifier,
            text,
        )
        window.keyPressEvent(event)

    def test_transport_keys_reach_the_player(self):
        cases = [
            ("j", Qt.Key.Key_J, 7_000),
            ("l", Qt.Key.Key_L, 17_000),
            (",", Qt.Key.Key_Comma, 11_967),
            (".", Qt.Key.Key_Period, 12_033),
            ("h", Qt.Key.Key_H, 3_000),
        ]
        for text, key, expected in cases:
            with self.subTest(key=text):
                window = self._window()
                player = _RecordingPlayer()
                window._player = player
                self._press(window, text, key)
                self.assertEqual(player.positions, [expected])
                self.assertEqual(player.actions, ["play"])
                window.close()

    def test_k_toggles_pause_and_unhandled_space_does_not_seek(self):
        window = self._window()
        player = _RecordingPlayer()
        window._player = player
        self._press(window, "k", Qt.Key.Key_K)
        self.assertTrue(window._paused)
        self.assertEqual(player.actions, ["pause"])
        before = list(player.positions)
        self._press(window, " ", Qt.Key.Key_Space)
        self.assertEqual(player.positions, before)
        window.close()

    def test_help_and_still_keys_reach_their_real_window_branches(self):
        window = self._window()
        player = _RecordingPlayer(position=1_234)
        window._player = player
        self._press(window, "?", Qt.Key.Key_Question)
        self.assertIn("J", window.empty_label.text())

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_bytes(b"fixture boundary")

            def _save(_src: str, dest: str, *, position_ms: int):
                self.assertEqual(position_ms, 1_234)
                Path(dest).write_bytes(b"frame")
                return dest

            window._mp4 = str(source)
            with (
                patch("desktop.review.review_stills_dir", return_value=tmp),
                patch("desktop.review.save_review_frame", side_effect=_save),
            ):
                self._press(window, "s", Qt.Key.Key_S)
            self.assertIn("Saved", window.empty_label.text())
            self.assertTrue((Path(tmp) / "review_frame.png").is_file())
        window.close()


if __name__ == "__main__":
    unittest.main()
