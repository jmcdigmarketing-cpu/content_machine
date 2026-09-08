"""Stage 3 review room: last mp4, grade from gather_booth_context, J/K/L, Approve."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.chrome import build_qss, look_flags
from core.logging import get_logger
from core.review_bind import queued_approve_command
from core.review_keys import apply_review_key
from core.review_player import start_review_player
from core.review_still import review_stills_dir, save_review_frame
from core.safe_title_grid import safe_title_rects

logger = get_logger("desktop.review")

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
except ImportError:
    QAudioOutput = None  # type: ignore[misc, assignment]
    QMediaPlayer = None  # type: ignore[misc, assignment]
    QVideoWidget = None  # type: ignore[misc, assignment]


class SafeTitleOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rects = safe_title_rects(self.width(), self.height())
        chrome = rects["chrome"]
        painter.fillRect(
            chrome[0],
            chrome[1],
            max(1, chrome[2] - chrome[0]),
            max(1, chrome[3] - chrome[1]),
            QColor(255, 80, 80, 50),
        )
        safe = rects["title_safe"]
        painter.setPen(QPen(QColor(80, 220, 120), 2))
        painter.drawRect(
            safe[0],
            safe[1],
            max(1, safe[2] - safe[0]),
            max(1, safe[3] - safe[1]),
        )


class ReviewWindow(QMainWindow):
    def __init__(self, context: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Content OS — review")
        self.resize(960, 720)
        ctx = dict(context or {})
        self._ctx = ctx
        self._paused = False
        self._mp4 = str(ctx.get("mp4") or ctx.get("mp4_path") or "")
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
        self.brand = QLabel("Review room")
        self.brand.setObjectName("title_brand")
        layout.addWidget(self.brand)

        grade = str(ctx.get("grade") or "n/a")
        layout.addWidget(QLabel(f"Grade {grade}"))
        auth = str(ctx.get("authenticity") or "")
        if auth:
            layout.addWidget(QLabel(auth))
        cost = str(ctx.get("cost") or "")
        if cost:
            layout.addWidget(QLabel(cost))

        self.empty_label = QLabel("")
        self.empty_label.setObjectName("empty_state")
        self.empty_label.setWordWrap(True)
        self._player: Any = None
        self._audio: Any = None
        self._video: Any = None
        self._overlay: SafeTitleOverlay | None = None
        refuse = str(ctx.get("refuse_reason") or "")
        if self._mp4 and os.path.isfile(self._mp4) and QMediaPlayer is not None:
            video = QVideoWidget()
            self._video = video
            layout.addWidget(video, 1)
            self._overlay = SafeTitleOverlay(video)
            self._audio = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(video)
            start_review_player(self._player, self._mp4)
        elif self._mp4 and os.path.isfile(self._mp4):
            self.empty_label.setText(
                "QtMultimedia is missing. The mp4 is on disk; install the full PySide6 extra."
            )
            layout.addWidget(self.empty_label, 1)
        else:
            self.empty_label.setText(
                refuse or "No last mp4 on disk. Render first, then reopen the review room."
            )
            layout.addWidget(self.empty_label, 1)

        mp3 = str(ctx.get("mp3_path") or "")
        if mp3 and os.path.isfile(mp3):
            try:
                from core.html_report import html_dir
                from core.player_waveform import under_player_waveform

                wave_png = os.path.join(html_dir(), "player_wave.png")
                written = under_player_waveform(mp3, wave_png)
                pix = QPixmap(written)
                if not pix.isNull():
                    wave_label = QLabel()
                    wave_label.setPixmap(pix.scaledToWidth(640))
                    layout.addWidget(wave_label)
            except Exception as exc:
                logger.debug("player waveform skipped: %s", exc)

        if refuse and self._player is not None:
            self.empty_label.setText(refuse)
            layout.addWidget(self.empty_label)

        hint = QLabel("J back · K pause · L forward · ,/. frame · S still")
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.approve_btn = QPushButton("Approve")
        self.approve_btn.clicked.connect(self._approve)
        if queued_approve_command(self._ctx) is None:
            self.approve_btn.setEnabled(False)
        row.addWidget(self.approve_btn)
        layout.addLayout(row)
        self.setCentralWidget(root)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._overlay is not None and self._video is not None:
            self._overlay.setGeometry(self._video.rect())

    def keyPressEvent(self, event) -> None:
        key = event.text() if event is not None else ""
        player = self._player
        if player is None or not hasattr(player, "position"):
            super().keyPressEvent(event)
            return
        token = key or ""
        lower = token.lower()
        if lower == "s":
            self._save_frame()
            return
        if token == "?":
            from core.review_keys import cheat_sheet_copy

            self.empty_label.setText(cheat_sheet_copy())
            return
        if lower not in {"j", "k", "l", "h"} and token not in {",", "."}:
            super().keyPressEvent(event)
            return
        pos, paused = apply_review_key(
            token if token in {",", "."} else lower,
            position_ms=int(player.position()),
            duration_ms=int(player.duration() or 0),
            paused=self._paused,
        )
        self._paused = paused
        player.setPosition(pos)
        if paused:
            player.pause()
        else:
            player.play()

    def _save_frame(self) -> None:
        if not self._mp4 or not os.path.isfile(self._mp4):
            return
        pos = 0
        if self._player is not None and hasattr(self._player, "position"):
            pos = int(self._player.position())
        dest = os.path.join(review_stills_dir(), "review_frame.png")
        try:
            save_review_frame(self._mp4, dest, position_ms=pos)
            self.empty_label.setText(f"Saved {dest}")
        except Exception as exc:
            self.empty_label.setText(f"Still not saved: {exc}")

    def _approve(self) -> None:
        cmd = queued_approve_command(self._ctx)
        if not cmd:
            reason = str(self._ctx.get("refuse_reason") or "Approve disabled for this run.")
            self.empty_label.setText(reason)
            return
        parts = cmd.split()
        if len(parts) >= 3 and parts[1] == "-m":
            subprocess.Popen([sys.executable, "-m", *parts[2:]])
        elif parts:
            subprocess.Popen(parts)
