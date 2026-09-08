"""Stage 3 review room: last mp4, grade from gather_booth_context, J/K/L, Approve."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.chrome import build_qss, look_flags
from core.review_keys import apply_review_key, approve_command

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
except ImportError:
    QAudioOutput = None  # type: ignore[misc, assignment]
    QMediaPlayer = None  # type: ignore[misc, assignment]
    QVideoWidget = None  # type: ignore[misc, assignment]


class ReviewWindow(QMainWindow):
    def __init__(self, context: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Content OS — review")
        self.resize(960, 720)
        ctx = dict(context or {})
        self._ctx = ctx
        self._paused = False
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

        mp4 = str(ctx.get("mp4") or ctx.get("mp4_path") or "")
        self.empty_label = QLabel("")
        self.empty_label.setObjectName("empty_state")
        self.empty_label.setWordWrap(True)
        self._player: Any = None
        self._audio: Any = None
        if mp4 and os.path.isfile(mp4) and QMediaPlayer is not None and QVideoWidget is not None:
            video = QVideoWidget()
            layout.addWidget(video, 1)
            self._audio = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(video)
            self._player.setSource(QUrl.fromLocalFile(os.path.abspath(mp4)))
            self.empty_label.setText("")
        elif mp4 and os.path.isfile(mp4):
            self.empty_label.setText(
                "QtMultimedia is missing. The mp4 is on disk; install the full PySide6 extra."
            )
            layout.addWidget(self.empty_label, 1)
        else:
            self.empty_label.setText(
                "No last mp4 on disk. Render first, then reopen the review room."
            )
            layout.addWidget(self.empty_label, 1)

        hint = QLabel("J back · K pause · L forward")
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.approve_btn = QPushButton("Approve")
        self.approve_btn.clicked.connect(self._approve)
        row.addWidget(self.approve_btn)
        layout.addLayout(row)
        self.setCentralWidget(root)

    def keyPressEvent(self, event) -> None:
        key = event.text() if event is not None else ""
        player = self._player
        if player is None or not hasattr(player, "position"):
            super().keyPressEvent(event)
            return
        token = (key or "").lower()
        if token not in {"j", "k", "l"}:
            super().keyPressEvent(event)
            return
        pos, paused = apply_review_key(
            token,
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

    def _approve(self) -> None:
        cmd = approve_command(self._ctx)
        parts = cmd.split()
        if len(parts) >= 3 and parts[1] == "-m":
            subprocess.Popen([sys.executable, "-m", *parts[2:]])
        elif parts:
            subprocess.Popen(parts)
