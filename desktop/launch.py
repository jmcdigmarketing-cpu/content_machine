"""Stage 1/3 launcher. PySide6 is an optional extra — missing it is an honest refuse."""

from __future__ import annotations

import sys

from core.ask_bridge import missing_pyside_message


def launch(*, review: bool | None = None) -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication, QMainWindow
    except ImportError:
        print(missing_pyside_message())
        return 2
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    want_review = bool(review) or "--review" in sys.argv
    app = QApplication.instance() or QApplication([])
    window: QMainWindow
    if want_review:
        from core.review_booth import gather_booth_context
        from desktop.review import ReviewWindow

        window = ReviewWindow(context=gather_booth_context())
    else:
        from desktop.window import RunWindow

        window = RunWindow()
    window.show()
    return int(app.exec())
