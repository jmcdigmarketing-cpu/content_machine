"""The facts room panel (#860, desktop Stage 3).

A checkbox table over `core.facts.room.gather`'s rows, sorted by #548's confidence: the
line, where it came from, its tier, and whether the off-topic filter flagged it (greyed,
unticked). Keep returns the ticked ids to the run through `AskBridge.submit`, and
`core/ui.prompt_key_facts_result` carries on with them at their own tiers.

`table_model` is pure so CI can check what the table shows without a display; Qt is
imported only when the dialog opens (PySide6 is the optional `[app]` extra).
"""

from __future__ import annotations

from typing import Any


def table_model(rows: list[Any]) -> list[dict[str, Any]]:
    """What each table row shows: id, tick, greyed, line, source, tier, confidence."""
    return [
        {
            "id": row.id,
            "checked": bool(row.keep),
            "greyed": bool(row.off_topic),
            "line": row.line,
            "source": row.source,
            "tier": row.tier,
            "confidence": f"{row.confidence.value:.2f} {row.confidence.label}",
            "flag": "off-topic" if row.off_topic else "uncertain" if row.uncertain else "",
        }
        for row in rows
    ]


def open_facts_room(parent: Any, rows: list[Any]) -> list[int]:
    """Show the dialog; the ticked ids (the default ticks when it is closed)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QBrush, QColor
    from PySide6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QLabel,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )

    model = table_model(rows)
    dialog = QDialog(parent)
    dialog.setWindowTitle("Facts room")
    layout = QVBoxLayout(dialog)
    layout.addWidget(
        QLabel(
            f"{len(model)} line(s) from your paste, its links and the vault, ranked by "
            "confidence. Untick what should not reach the script."
        )
    )
    table = QTableWidget(len(model), 5, dialog)
    table.setHorizontalHeaderLabels(["Keep", "Fact", "From", "Tier", "Confidence"])
    grey = QBrush(QColor(140, 140, 140))
    for r, item in enumerate(model):
        tick = QTableWidgetItem()
        tick.setFlags(tick.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        tick.setCheckState(Qt.CheckState.Checked if item["checked"] else Qt.CheckState.Unchecked)
        tick.setData(Qt.ItemDataRole.UserRole, item["id"])
        table.setItem(r, 0, tick)
        source = item["source"] + (f" ({item['flag']})" if item["flag"] else "")
        for c, text in enumerate((item["line"], source, item["tier"], item["confidence"]), 1):
            cell = QTableWidgetItem(str(text))
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if item["greyed"]:
                cell.setForeground(grey)
            table.setItem(r, c, cell)
    table.resizeColumnsToContents()
    layout.addWidget(table)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Keep ticked")
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.resize(1100, 560)
    dialog.exec()
    kept: list[int] = []
    for r in range(table.rowCount()):
        cell = table.item(r, 0)
        if cell is not None and cell.checkState() == Qt.CheckState.Checked:
            kept.append(int(cell.data(Qt.ItemDataRole.UserRole)))
    return kept
