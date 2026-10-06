"""One desktop window (#981): a sidebar over the app's pages.

Operator, 2026-10-06: "I wanted more typical desktop application". Stages 1-4 built the run
window, review room, queue, cost tower, studio and brand kit as separate windows, each behind
its own flag. `MainShell` is the one window: Home (desktop/home.py) first, every other page
built the first time it is opened and kept, a page that fails showing why instead of closing
the app. `py -m desktop` and `content_os.pyw` open it (#982).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.chrome import build_qss, icon_svg, look_flags

# Spacing and shape only - every colour stays in core.chrome's token stylesheet.
_SHELL_QSS = """
QLabel { padding: 0px; }
QLabel#title_brand { padding-bottom: 12px; }
QLabel#section_head { font-size: 12px; font-weight: 700; letter-spacing: 1px; }
QFrame#card { border: 1px solid palette(mid); border-radius: 8px; }
QFrame#card QWidget, QFrame#card QLabel { padding: 0px; }
QListWidget#sidebar { border: none; border-radius: 0px; padding: 12px 8px; font-size: 15px; }
QListWidget#sidebar::item { padding: 10px 12px; border-radius: 6px; }
QStackedWidget { padding: 0px; }
"""

PAGES: list[tuple[str, str]] = [
    ("Home", "home"),
    ("Analytics", "analytics"),  # #984
    ("New video", "run"),
    ("Review", "review"),
    ("Queue", "queue"),
    ("Costs", "cost"),
    ("Studio", "studio"),
    ("Brand", "brand"),
]


def build_page(key: str, channel_id: str = "tapin") -> QWidget:
    """The existing window for `key`, to be embedded as a page."""
    if key == "run":
        from desktop.window import RunWindow

        window = RunWindow()
        index = window.channel.findData(channel_id)
        if index >= 0:  # the app's channel (#970), not the combo's first entry ("Default")
            window.channel.setCurrentIndex(index)
        return window
    if key == "analytics":
        from desktop.analytics_page import AnalyticsPage

        return AnalyticsPage(channel_id=channel_id)
    if key == "review":
        from core.review_booth import gather_booth_context
        from desktop.review import ReviewWindow

        return ReviewWindow(context=gather_booth_context())
    if key == "queue":
        from desktop.queue import QueueWindow

        return QueueWindow()
    if key == "cost":
        from desktop.cost import CostWindow

        return CostWindow()
    if key == "studio":
        from core.review_booth import gather_booth_context
        from desktop.studio import StudioWindow

        return StudioWindow(context=gather_booth_context())
    if key == "brand":
        from desktop.brand import BrandWindow

        return BrandWindow(channel_id=channel_id)
    raise KeyError(key)


class MainShell(QMainWindow):
    def __init__(
        self,
        *,
        channel_id: str = "tapin",
        factory: Callable[[str], QWidget] | None = None,
    ) -> None:
        super().__init__()
        self.channel_id = channel_id
        self._factory = factory or (lambda key: build_page(key, channel_id))
        self._built: dict[int, QWidget] = {}
        self.setWindowTitle("Content OS")
        self.resize(1180, 780)

        root = QWidget()
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        for name, _key in PAGES:
            self.sidebar.addItem(name)
        self.stack = QStackedWidget()
        self._home = QWidget()
        self._home_layout = QVBoxLayout(self._home)
        self._home_layout.setContentsMargins(28, 24, 28, 24)
        self._home_layout.setSpacing(14)
        self._home_labels: list[QLabel] = []
        self.stack.addWidget(self._home)
        for _ in PAGES[1:]:
            self.stack.addWidget(QWidget())  # placeholder until first opened
        row.addWidget(self.sidebar)
        row.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self._fill_home()
        self.sidebar.currentRowChanged.connect(self._open)
        self.sidebar.setCurrentRow(0)
        self._apply_look()

    # -- Home --------------------------------------------------------------------------
    def _fill_home(self) -> None:
        from desktop.home import home_lines

        layout = self._home_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()
        title = QLabel("Content OS")
        title.setObjectName("title_brand")
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        self._home_labels = []
        wide = {"Last videos", "Research"}
        col = row = 0
        for label, text in home_lines(self.channel_id):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 12, 16, 14)
            box.setSpacing(6)
            head = QLabel(label.upper())
            head.setObjectName("section_head")
            body = QLabel(text)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(head)
            box.addWidget(body)
            self._home_labels.append(body)
            if label in wide:
                if col:
                    row, col = row + 1, 0
                grid.addWidget(card, row, 0, 1, 2)
                row += 1
            else:
                grid.addWidget(card, row, col)
                col = (col + 1) % 2
                row += 0 if col else 1
        layout.addLayout(grid)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._fill_home)
        layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def home_text(self) -> str:
        return "\n".join(label.text() for label in self._home_labels)

    # -- pages -------------------------------------------------------------------------
    def _open(self, row: int) -> None:
        if row > 0 and row not in self._built:
            key = PAGES[row][1]
            try:
                page = self._factory(key)
                if isinstance(page, QMainWindow):
                    page.setWindowFlags(Qt.WindowType.Widget)
            except Exception as exc:
                page = QWidget()
                box = QVBoxLayout(page)
                note = QLabel(f"{PAGES[row][0]} could not open: {exc}")
                note.setWordWrap(True)
                box.addWidget(note)
                box.addStretch(1)
            old = self.stack.widget(row)
            self.stack.insertWidget(row, page)
            if old is not None:
                self.stack.removeWidget(old)
                old.deleteLater()
            self._built[row] = page
        self.stack.setCurrentIndex(row)

    def _apply_look(self) -> None:
        flags = look_flags()
        self.setStyleSheet(
            build_qss(
                self.channel_id,
                reduced_chroma=flags["reduced_chroma"],
                high_contrast=flags["high_contrast"],
                reduced_motion=flags["reduced_motion"],
                colorblind=flags["colorblind"],
            )
            + _SHELL_QSS
        )
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(icon_svg(self.channel_id).encode("utf-8")))
        self.setWindowIcon(QIcon(pixmap))
