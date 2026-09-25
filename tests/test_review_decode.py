"""Real QtMultimedia decode guard for the committed 2.15s H.264 fixture."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QElapsedTimer, QUrl
    from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - app extra is optional outside CI
    QApplication = None  # type: ignore[misc, assignment]


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "video" / "intro" / "channel_intro.mp4"


from tests.qt_support import requires_qt


@requires_qt
@unittest.skipUnless(FIXTURE.is_file(), "committed intro fixture missing")
class TestReviewRoomRealDecode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_qt_decodes_the_committed_h264_fixture_without_audio_output(self):
        player = QMediaPlayer()
        sink = QVideoSink()
        player.setVideoOutput(sink)
        player.setSource(QUrl.fromLocalFile(str(FIXTURE.resolve())))

        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < 10_000 and player.duration() <= 0:
            self.app.processEvents()

        self.assertGreater(
            player.duration(),
            2_000,
            f"Qt failed to decode {FIXTURE}: {player.errorString()}",
        )
        player.stop()


if __name__ == "__main__":
    unittest.main()
