"""Stage 1/3/4 launcher. PySide6 is an optional extra — missing it is an honest refuse."""

from __future__ import annotations

import sys

from core.ask_bridge import missing_pyside_message


def desktop_mode(argv: list[str] | None = None) -> str:
    args = argv if argv is not None else sys.argv[1:]
    if "--studio" in args:
        return "studio"
    if "--queue" in args:
        return "queue"
    if "--review" in args:
        return "review"
    return "run"


def launch(
    *,
    review: bool | None = None,
    studio: bool | None = None,
    queue: bool | None = None,
) -> int:
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
    if studio:
        mode = "studio"
    elif queue:
        mode = "queue"
    elif review:
        mode = "review"
    else:
        mode = desktop_mode()
    app = QApplication.instance() or QApplication([])
    window: QMainWindow
    if mode == "studio":
        from core.review_booth import gather_booth_context
        from desktop.studio import StudioWindow

        window = StudioWindow(context=gather_booth_context())
    elif mode == "queue":
        from desktop.queue import QueueWindow

        window = QueueWindow()
    elif mode == "review":
        from core.review_booth import gather_booth_context
        from desktop.review import ReviewWindow

        window = ReviewWindow(context=gather_booth_context())
    else:
        from desktop.window import RunWindow

        window = RunWindow()
    window.show()
    return int(app.exec())
