"""#158: the Cost Control Tower as a panel, read-only over `core.cost_tower.gather_tower()`."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.chrome import build_qss, look_flags
from core.cost_tower import TowerRow, amount_text

_COLUMNS = ("Lane", "Item", "Used / Limit", "State", "Resets")


class CostWindow(QMainWindow):
    def __init__(self, rows: list[TowerRow] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Content OS — cost tower")
        self.resize(860, 440)
        flags = look_flags()
        self.setStyleSheet(
            build_qss(
                "tapin",
                reduced_chroma=flags["reduced_chroma"],
                high_contrast=flags["high_contrast"],
                reduced_motion=flags["reduced_motion"],
                colorblind=flags["colorblind"],
            )
        )
        root = QWidget()
        layout = QVBoxLayout(root)
        brand = QLabel("Cost Control Tower")
        brand.setObjectName("title_brand")
        layout.addWidget(brand)
        layout.addWidget(QLabel("Read-only. UNKNOWN means no reading, never zero."))
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        self.setCentralWidget(root)
        self._show(rows if rows is not None else self._gather())

    @staticmethod
    def _gather() -> list[TowerRow]:
        # Looked up at call time so Refresh always reads the stores again.
        from core import cost_tower

        return cost_tower.gather_tower()

    def refresh(self, *_args) -> None:
        self._show(self._gather())

    def _show(self, rows: list[TowerRow]) -> None:
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            item = QTableWidgetItem(row.item)
            if row.note:
                item.setToolTip(row.note)
            cells = (
                QTableWidgetItem(row.lane),
                item,
                QTableWidgetItem(amount_text(row)),
                QTableWidgetItem(row.state.upper()),
                QTableWidgetItem(row.resets or ""),
            )
            for column, cell in enumerate(cells):
                self.table.setItem(index, column, cell)
        self.table.resizeColumnsToContents()
