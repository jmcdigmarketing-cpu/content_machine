"""#151. The compiled brand kit, with the source each field came from.

Read-only by design. This shows what `core.brand_kit.compile_kit` resolved; it
does not edit tokens, channels.json or the assets folder, and it changes nothing
about how a video renders.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.brand_kit import BrandKit, compile_kit, summarize_config
from core.chrome import build_qss, look_flags

_SWATCH_FIELDS = {"caption_fill", "caption_outline", "header_border", "end_card_bg", "end_card_fg"}


def kit_rows(kit: BrandKit) -> list[tuple[str, str, str]]:
    """(field, value, source) triples -- the table model, testable without Qt."""
    values = (
        ("caption_fill", kit.caption_fill),
        ("caption_outline", kit.caption_outline),
        ("header_border", kit.header_border),
        ("end_card_bg", kit.end_card_bg),
        ("end_card_fg", kit.end_card_fg),
        ("grain", str(kit.grain)),
        ("vignette", str(kit.vignette)),
        ("caption_skin", summarize_config(kit.caption_skin)),
        ("color_grade", summarize_config(kit.color_grade)),
        ("hook_motion", summarize_config(kit.hook_motion)),
        ("intro_video_file", kit.intro_video_file or "(none)"),
        ("youtube_handle", kit.youtube_handle or "(unset)"),
        ("logo", kit.logo_path or "(missing)"),
        ("banner", kit.banner_path or "(missing)"),
    )
    return [(name, value, kit.provenance.get(name, "?")) for name, value in values]


class BrandWindow(QMainWindow):
    def __init__(self, channel_id: str = "tapin", kit: BrandKit | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"Content OS - brand kit ({channel_id})")
        self.resize(760, 560)
        flags = look_flags()
        self.setStyleSheet(
            build_qss(
                channel_id,
                reduced_chroma=flags["reduced_chroma"],
                high_contrast=flags["high_contrast"],
                reduced_motion=flags["reduced_motion"],
                colorblind=flags["colorblind"],
            )
        )
        self.kit = kit if kit is not None else compile_kit(channel_id)

        root = QWidget()
        layout = QVBoxLayout(root)
        brand = QLabel(f"Brand kit - {channel_id}")
        brand.setObjectName("title_brand")
        layout.addWidget(brand)

        self.status = QLabel(
            "resolved from all three sources"
            if self.kit.complete
            else f"incomplete - missing: {'; '.join(self.kit.missing)}"
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        rows = kit_rows(self.kit)
        self.table = QTableWidget(len(rows), 3)
        self.table.setHorizontalHeaderLabels(["field", "value", "source"])
        for r, (name, value, source) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(name))
            value_item = QTableWidgetItem(value)
            if name in _SWATCH_FIELDS and value.startswith("#"):
                swatch = QPixmap(14, 14)
                swatch.fill(QColor(value))
                value_item.setData(1, swatch)  # Qt.DecorationRole
            self.table.setItem(r, 1, value_item)
            self.table.setItem(r, 2, QTableWidgetItem(source))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        note = QLabel(
            "Read-only. Editing the kit means editing config/design_tokens.json, "
            "config/channels.json or assets/branding/ - this window does not "
            "change how a video renders."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.setCentralWidget(root)
