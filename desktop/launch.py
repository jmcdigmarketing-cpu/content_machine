"""Stage 1 launcher. PySide6 is an optional extra — missing it is an honest refuse."""

from __future__ import annotations

from core.ask_bridge import missing_pyside_message


def launch() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(missing_pyside_message())
        return 2
    from desktop.window import RunWindow

    app = QApplication.instance() or QApplication([])
    window = RunWindow()
    window.show()
    return int(app.exec())
