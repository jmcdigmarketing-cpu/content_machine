"""#153 caption choreography timeline. Keyframes over real word timings."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from core.caption_timeline import (
    PX_PER_SEC,
    CaptionCue,
    CaptionTimeline,
    clamp_cue_time,
    clamp_margin_v,
    cue_rect,
    load_edits,
    save_edits,
    timeline_from_audio,
    timeline_from_words,
)
from core.chrome import build_qss, look_flags


class MovableCueItem(QGraphicsRectItem):
    def __init__(self, cue: CaptionCue, *, px_per_sec: float, duration: float, audio_path: str):
        x, y, w, h = cue_rect(cue, px_per_sec=px_per_sec)
        super().__init__(0, 0, max(1, w), max(1, h))
        self.setPos(x, y)
        self._cue = cue
        self._px = px_per_sec
        self._duration = duration
        self._audio = audio_path
        self._origin_x = x
        self._lane_y = y
        self._span = max(0.05, cue.end - cue.start)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setData(0, "cue")
        color = QColor(80, 180, 255) if cue.lane == "karaoke" else QColor(220, 180, 80)
        self.setPen(QPen(color, 2))
        self.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 70)))
        label = QGraphicsSimpleTextItem(cue.text[:24], self)
        label.setBrush(QBrush(QColor(240, 240, 240)))
        label.setPos(4, 4)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if not self._audio:
            self.setPos(self._origin_x, self._lane_y)
            return
        pos = self.pos()
        start = float(pos.x()) / self._px
        start, end = clamp_cue_time(start, start + self._span, duration=self._duration)
        x, _y, _w, _h = cue_rect(
            CaptionCue(
                lane=self._cue.lane,
                index=self._cue.index,
                text=self._cue.text,
                start=start,
                end=end,
            ),
            px_per_sec=self._px,
        )
        self.setPos(x, self._lane_y)
        dt = round(start - self._cue.start, 3)
        margin_v = None
        if self._cue.lane == "karaoke":
            margin_v = clamp_margin_v(260 + int((self._lane_y - pos.y()) * 2))
        _upsert_edit(self._audio, self._cue.lane, self._cue.index, dt, margin_v)


def _upsert_edit(audio_path: str, lane: str, index: int, dt: float, margin_v: int | None) -> None:
    edits = load_edits(audio_path)
    found = False
    for row in edits:
        if str(row.get("lane") or "") == lane and int(row.get("index") or -1) == index:
            row["dt"] = dt
            if margin_v is not None:
                row["margin_v"] = margin_v
            found = True
            break
    if not found:
        payload: dict[str, Any] = {"lane": lane, "index": index, "dt": dt}
        if margin_v is not None:
            payload["margin_v"] = margin_v
        edits.append(payload)
    save_edits(audio_path, edits)


def _timeline_for(context: dict[str, Any]) -> CaptionTimeline:
    raw = context.get("words")
    audio = str(context.get("mp3_path") or "")
    if isinstance(raw, list):
        return timeline_from_words(raw, audio_path=audio)
    return timeline_from_audio(audio)


class CaptionTimelineWindow(QMainWindow):
    def __init__(self, context: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Content OS — captions")
        self.resize(960, 420)
        ctx = dict(context or {})
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
        brand = QLabel("Caption timeline")
        brand.setObjectName("title_brand")
        layout.addWidget(brand)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        layout.addWidget(self.view, 1)

        self.empty_label = QLabel("")
        self.empty_label.setObjectName("empty_state")
        self.empty_label.setWordWrap(True)
        self.status = QLabel("")
        tl = _timeline_for(ctx)
        if tl.source != "word_timing":
            self.empty_label.setText(tl.reason)
            layout.addWidget(self.empty_label)
            self.status.setText("missing word timings")
        else:
            audio = str(ctx.get("mp3_path") or "")
            for cue in (*tl.karaoke, *tl.srt):
                self.scene.addItem(
                    MovableCueItem(
                        cue, px_per_sec=PX_PER_SEC, duration=tl.duration, audio_path=audio
                    )
                )
            self.status.setText(
                f"karaoke {len(tl.karaoke)} cues · srt {len(tl.srt)} cues · "
                "drag horizontally to nudge timing"
            )
        layout.addWidget(self.status)
        self.setCentralWidget(root)
