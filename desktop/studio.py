"""Stage 4 studio: last thumbnail + inspect_thumbnail overlay. No drag this wave."""

from __future__ import annotations

import os
from typing import Any

from PySide6.QtGui import QColor, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.chrome import build_qss, look_flags
from core.font_specimen import specimen_faces, write_font_pick
from core.html_report import html_dir
from core.studio_canvas import studio_overlay_for


class StudioWindow(QMainWindow):
    def __init__(self, context: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Content OS — studio")
        self.resize(960, 720)
        ctx = dict(context or {})
        self._ctx = ctx
        cid = str(ctx.get("channel_id") or "tapin")
        flags = look_flags()
        self.setStyleSheet(
            build_qss(
                cid,
                reduced_chroma=flags["reduced_chroma"],
                high_contrast=flags["high_contrast"],
                reduced_motion=flags["reduced_motion"],
                colorblind=flags["colorblind"],
            )
        )

        root = QWidget()
        layout = QVBoxLayout(root)
        brand = QLabel("Thumbnail studio")
        brand.setObjectName("title_brand")
        layout.addWidget(brand)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        layout.addWidget(self.view, 1)

        thumb = str(ctx.get("thumb_path") or "")
        self.empty_label = QLabel("")
        self.empty_label.setObjectName("empty_state")
        self.empty_label.setWordWrap(True)
        if thumb:
            try:
                overlay = studio_overlay_for(thumb)
                pix = QPixmap(thumb)
                if not pix.isNull():
                    self.scene.addPixmap(pix)
                    self._draw_overlay(overlay.get("rects") or {}, pix.width(), pix.height())
                    note = "quiet" if overlay.get("bottom_quiet") else "review"
                    layout.addWidget(QLabel(f"Safe-area {note}: {overlay.get('detail') or ''}"))
                else:
                    self.empty_label.setText("Last thumbnail could not be loaded.")
                    layout.addWidget(self.empty_label)
            except Exception as exc:
                self.empty_label.setText(f"No studio still: {exc}")
                layout.addWidget(self.empty_label)
        else:
            self.empty_label.setText("No last thumbnail on disk. Render first, then reopen studio.")
            layout.addWidget(self.empty_label)

        faces = specimen_faces(cid)
        strip = QHBoxLayout()
        strip.addWidget(QLabel("Caption faces:"))
        for face in faces:
            btn = QPushButton(face)
            btn.clicked.connect(lambda _checked=False, name=face: self._pick_font(name))
            strip.addWidget(btn)
        layout.addLayout(strip)
        self.pick_note = QLabel("")
        layout.addWidget(self.pick_note)
        self.setCentralWidget(root)

    def _draw_overlay(self, rects: dict[str, Any], width: int, height: int) -> None:
        del width, height
        chrome = rects.get("chrome") or ()
        if len(chrome) == 4:
            x0, y0, x1, y1 = (int(v) for v in chrome)
            item = QGraphicsRectItem(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
            item.setPen(QPen(QColor(255, 80, 80), 2))
            item.setBrush(QColor(255, 80, 80, 40))
            self.scene.addItem(item)
        safe = rects.get("title_safe") or ()
        if len(safe) == 4:
            x0, y0, x1, y1 = (int(v) for v in safe)
            item = QGraphicsRectItem(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
            item.setPen(QPen(QColor(80, 220, 120), 2))
            self.scene.addItem(item)

    def _pick_font(self, face: str) -> None:
        dest = os.path.join(html_dir(), "font_pick.txt")
        written = write_font_pick(face, dest)
        self.pick_note.setText(f"Wrote {written} (not channels.json)")
