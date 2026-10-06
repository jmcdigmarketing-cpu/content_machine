"""The desktop launcher. PySide6 is an optional extra - missing it is an honest refuse.

#981/#982: with no flag it opens the one app window (`desktop/shell.py`); the old flags
still open a single window (`--run`, `--review`, `--queue`, `--cost`, `--studio`, `--brand`),
and `--chip` the quota chip. Under `pythonw` (the Start Menu / Desktop shortcut) there is no
console, so a missing PySide6 is said in a message box.
"""

from __future__ import annotations

import sys

from core.ask_bridge import missing_pyside_message

_FLAGS = ("brand", "studio", "queue", "cost", "review", "run", "chip")


def desktop_mode(argv: list[str] | None = None) -> str:
    args = argv if argv is not None else sys.argv[1:]
    for name in _FLAGS:
        if f"--{name}" in args:
            return name
    return "shell"


def _qt_available() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
    except ImportError:
        return False
    return True


def _no_console() -> bool:
    """True under pythonw, where print() goes nowhere."""
    return sys.stdout is None or "pythonw" in (sys.executable or "").lower()


def _message_box(text: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showinfo("Content OS", text)
        root.destroy()
    except Exception as exc:  # no Tk either: nothing left to show it with
        sys.stderr.write(f"{text}\n({exc})\n") if sys.stderr else None


def _channel() -> str:
    try:
        from config.channels import list_channel_ids
        from core.ui import preferred_channel

        chosen = preferred_channel(list_channel_ids())
        return chosen if chosen and chosen != "default" else "tapin"
    except Exception:
        return "tapin"


def launch(
    *,
    review: bool | None = None,
    studio: bool | None = None,
    queue: bool | None = None,
    brand: bool | None = None,
    cost: bool | None = None,
    mode: str | None = None,
    channel_id: str | None = None,
) -> int:
    for flag, value in (("brand", brand), ("studio", studio), ("queue", queue), ("cost", cost),
                        ("review", review)):  # fmt: skip
        if value:
            mode = flag
    mode = mode or desktop_mode()
    if mode == "chip":
        from core.win_notify import run_tray

        return int(run_tray(stay=True))
    if not _qt_available():
        message = missing_pyside_message()
        if _no_console():
            _message_box(
                'Content OS needs the app extra. In PowerShell run:\n\npip install -e ".[app]"'
            )
        else:
            print(message)
        return 2
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QMainWindow

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Content OS")
    channel = channel_id or _channel()
    window: QMainWindow
    if mode == "shell":
        from desktop.shell import MainShell

        window = MainShell(channel_id=channel)
    else:
        from desktop.shell import build_page

        page = build_page(mode, channel)
        assert isinstance(page, QMainWindow)
        window = page
    window.show()
    return int(app.exec())
