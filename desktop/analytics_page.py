"""The app's Analytics page (#984).

`ops growth` (#983), the hook-learning line (#985), the scoreboard (#934) and the prediction
ledger (#113) were terminal-only. `analytics_data` gathers them, each reader fail-open, and
`AnalyticsPage` draws: four tiles, one bar per video of its organic 7-day views shaded by its
stayed-share third, and the lines underneath. Under `growth._MIN_VIDEOS` measured videos the
page says "collecting" with the backfill command.

The bar shades are one blue ramp, validated against the app's dark surface (#0B0F14) with the
dataviz validator's ordinal checks: bottom third #184f95, middle #3987e5, top third #9ec5f4.
A video with no stayed share yet is grey, and the legend names all four.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from core.logging import get_logger

logger = get_logger("desktop.analytics_page")

BANDS = (("bottom third", "#184f95"), ("middle third", "#3987e5"), ("top third", "#9ec5f4"))
UNSYNCED = ("not synced yet", "#6b6a64")
_GRID = "#2c2c2a"
_INK = "#c3c2b7"
_MAX_BARS = 30


def _bands(videos: list[dict[str, Any]]) -> list[int | None]:
    """Each video's stayed-share third by rank (0 bottom, 2 top); None when not synced."""
    known = sorted((v["stayed"], i) for i, v in enumerate(videos) if v.get("stayed") is not None)
    out: list[int | None] = [None] * len(videos)
    for rank, (_stayed, i) in enumerate(known):
        out[i] = min(2, int(rank * 3 / len(known)))
    return out


def analytics_data(channel_id: str) -> dict[str, Any]:
    """{tiles: [(label, value)], bars: [{title, views, stayed, band}], lines, note}."""
    from analytics import growth

    data: dict[str, Any] = {"tiles": [], "bars": [], "lines": [], "note": ""}
    try:
        rep = growth.report(channel_id)
    except Exception as exc:
        logger.debug("growth report unavailable: %s", exc)
        data["note"] = f"Growth numbers unavailable ({type(exc).__name__})"
        rep = {}
    if rep:
        split = rep.get("stayed_split") or {}
        stayed = (
            f"{split['high_views']:,} vs {split['low_views']:,} views "
            f"({split['high_stayed']:.0%} vs {split['low_stayed']:.0%} stayed)"
            if split
            else "not synced yet"
        )
        data["tiles"] = [
            ("Median 7-day views", f"{rep.get('median_views', 0):,}"),
            ("Stayed: top vs bottom third", stayed),
            ("Posts a week", f"{float(rep.get('per_week') or 0):.1f}"),
            ("Paid share", f"{float(rep.get('paid_share') or 0):.0%}"),
        ]
        if int(rep.get("n") or 0) < growth._MIN_VIDEOS:
            data["note"] = (
                f"collecting: {rep.get('n', 0)} video(s) with a full first week; the page needs "
                f"{growth._MIN_VIDEOS}. Fill older ones: py -m scripts.ops backfill view-curve "
                "--apply"
            )
    try:
        vids = growth.videos(channel_id)[-_MAX_BARS:]
    except Exception as exc:
        logger.debug("growth videos unavailable: %s", exc)
        vids = []
    for video, band in zip(vids, _bands(vids), strict=True):
        data["bars"].append({
            "title": str(video.get("title") or ""),
            "views": int(video.get("views7") or 0),
            "stayed": video.get("stayed"),
            "band": band,
        })  # fmt: skip

    def hook() -> list[str]:
        from analytics.hook_learning import render_line

        return [render_line(channel_id)]

    def scoreboard() -> list[str]:
        from core.success.goals import scoreboard_lines

        return scoreboard_lines(channel_id)

    def predictions() -> list[str]:
        from core.predictions.ledger import summary_line

        return [summary_line(channel_id) or ""]

    def intro() -> list[str]:
        return [growth.intro_line(channel_id)]  # #988

    readers = (
        ("intro", intro),
        ("hook", hook),
        ("scoreboard", scoreboard),
        ("predictions", predictions),
    )
    for name, read in readers:
        try:
            data["lines"].extend(line for line in read() or [] if line)
        except Exception as exc:
            logger.debug("analytics %s line skipped: %s", name, exc)
    return data


class ViewsChart(QWidget):
    """One bar per video, organic 7-day views, shaded by stayed third; a tooltip per bar."""

    def __init__(self, bars: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bars = bars
        self.setMinimumHeight(240)
        self.setMouseTracking(True)

    def bar_count(self) -> int:
        return len(self._bars)

    def tip_for(self, index: int) -> str:
        bar = self._bars[index]
        stayed = bar["stayed"]
        kept = f"{stayed:.0%} stayed past the swipe" if stayed is not None else "stayed: not synced"
        return f"{bar['title']}\n{bar['views']:,} organic views in 7 days\n{kept}"

    def _plot(self) -> QRectF:
        return QRectF(56, 12, max(10, self.width() - 72), max(10, self.height() - 40))

    def _slot(self) -> float:
        return self._plot().width() / max(1, len(self._bars))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        top = max([b["views"] for b in self._bars] + [1])
        painter.setPen(QColor(_GRID))
        for frac in (0.5, 1.0):
            y = plot.bottom() - plot.height() * frac
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
        painter.setPen(QColor(_INK))
        for frac in (0.0, 0.5, 1.0):
            y = plot.bottom() - plot.height() * frac
            painter.drawText(QRectF(0, y - 8, 50, 16), Qt.AlignmentFlag.AlignRight,
                             f"{int(top * frac):,}")  # fmt: skip
        slot = self._slot()
        width = max(2.0, min(28.0, slot * 0.64))
        painter.setPen(Qt.PenStyle.NoPen)
        for i, bar in enumerate(self._bars):
            height = plot.height() * bar["views"] / top
            x = plot.left() + i * slot + (slot - width) / 2
            band = bar["band"]
            painter.setBrush(QColor(UNSYNCED[1] if band is None else BANDS[band][1]))
            radius = min(4.0, width / 2, height)
            left, right, base, top_y = x, x + width, plot.bottom(), plot.bottom() - height
            path = QPainterPath()  # rounded data end, square on the baseline
            path.moveTo(left, base)
            path.lineTo(left, top_y + radius)
            path.quadTo(left, top_y, left + radius, top_y)
            path.lineTo(right - radius, top_y)
            path.quadTo(right, top_y, right, top_y + radius)
            path.lineTo(right, base)
            path.closeSubpath()
            painter.drawPath(path)
        painter.setPen(QColor(_GRID))
        painter.drawLine(
            int(plot.left()), int(plot.bottom()), int(plot.right()), int(plot.bottom())
        )
        painter.setPen(QColor(_INK))
        painter.drawText(QRectF(plot.left(), plot.bottom() + 6, plot.width(), 18),
                         Qt.AlignmentFlag.AlignLeft, "oldest")  # fmt: skip
        painter.drawText(QRectF(plot.left(), plot.bottom() + 6, plot.width(), 18),
                         Qt.AlignmentFlag.AlignRight, "newest")  # fmt: skip
        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        plot = self._plot()
        x = event.position().x()
        if self._bars and plot.left() <= x <= plot.right():
            index = min(len(self._bars) - 1, int((x - plot.left()) / self._slot()))
            QToolTip.showText(event.globalPosition().toPoint(), self.tip_for(index), self)
        else:
            QToolTip.hideText()


def _card(label: str, value: str) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    box = QVBoxLayout(card)
    box.setContentsMargins(16, 12, 16, 14)
    head = QLabel(label.upper())
    head.setObjectName("section_head")
    body = QLabel(value)
    body.setObjectName("tile_value")
    body.setWordWrap(True)
    body.setStyleSheet("font-size: 20px; font-weight: 700;")
    box.addWidget(head)
    box.addWidget(body)
    return card


class AnalyticsPage(QWidget):
    def __init__(self, channel_id: str = "tapin", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        data = analytics_data(channel_id)
        self._texts: list[str] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = QLabel("Analytics")
        title.setObjectName("title_brand")
        layout.addWidget(title)
        if data["note"]:
            note = QLabel(data["note"])
            note.setWordWrap(True)
            layout.addWidget(note)
            self._texts.append(data["note"])
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, (label, value) in enumerate(data["tiles"]):
            grid.addWidget(_card(label, value), i // 2, i % 2)
            self._texts.extend([label, value])
        layout.addLayout(grid)
        head = QLabel("ORGANIC VIEWS IN THE FIRST 7 DAYS, PER VIDEO")
        head.setObjectName("section_head")
        layout.addWidget(head)
        layout.addWidget(QLabel("Shade: the share of viewers who stayed past the swipe"))
        legend = QHBoxLayout()
        for name, colour in (*BANDS, UNSYNCED):
            chip = QLabel()
            chip.setFixedSize(12, 12)
            chip.setStyleSheet(f"background: {colour}; border-radius: 2px;")
            legend.addWidget(chip)
            legend.addWidget(QLabel(name))
        legend.addStretch(1)
        layout.addLayout(legend)
        self.chart = ViewsChart(data["bars"])
        layout.addWidget(self.chart)
        for line in data["lines"]:
            label = QLabel(line)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
            self._texts.append(line)
        layout.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll)

    def page_text(self) -> str:
        return "\n".join(self._texts)


__all__ = ["AnalyticsPage", "ViewsChart", "analytics_data"]
