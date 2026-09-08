"""Stage 1 — the run window.

Channel, topic, a large facts paste (run 73), output from emit(), ask() gates as
buttons, angle mode from core.angle_intent. The pipeline runs on a worker thread.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.channels import get_channel_profiles, list_channel_ids
from core.ask_bridge import AskBridge, AskRequest
from desktop.session import angle_mode_line, start_run_worker

_GATE_LABELS = {
    "authenticity": "Authenticity gate",
    "grounding": "Grounding gate",
    "thin_facts": "Thin facts",
    "over_length": "Over length for TTS",
    "metrics": "Metrics gate",
}


class RunWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Content OS — run")
        self.resize(920, 720)
        self._bridge = AskBridge()
        self._log: list[str] = []
        self._log_lock = threading.Lock()
        self._log_seen = 0
        self._pending: AskRequest | None = None
        self._worker: threading.Thread | None = None
        self._done_box: list[BaseException | None] = []

        root = QWidget()
        layout = QVBoxLayout(root)

        row = QHBoxLayout()
        row.addWidget(QLabel("Channel"))
        self.channel = QComboBox()
        for cid in list_channel_ids():
            profile = get_channel_profiles()[cid]
            self.channel.addItem(f"{profile.name} ({cid})", cid)
        row.addWidget(self.channel, 1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Topic"))
        self.topic = QLineEdit()
        self.topic.setPlaceholderText("The video idea — not a PowerShell one-liner")
        self.topic.textChanged.connect(self._refresh_angle)
        row.addWidget(self.topic, 1)
        layout.addLayout(row)

        self.angle = QLabel("Angle mode: standard")
        layout.addWidget(self.angle)

        layout.addWidget(QLabel("Key facts (paste the article here — this is what run 73 needed)"))
        self.facts = QPlainTextEdit()
        self.facts.setPlaceholderText(
            "Paste the article, trades, or dated facts. Empty line in PowerShell "
            "is how run 74 died; this box keeps the whole paste."
        )
        self.facts.setMinimumHeight(160)
        layout.addWidget(self.facts)

        self.start_btn = QPushButton("Start video")
        self.start_btn.clicked.connect(self._start)
        layout.addWidget(self.start_btn)

        self.progress = QLabel("Idle")
        layout.addWidget(self.progress)

        layout.addWidget(QLabel("Output"))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        self.prompt_label = QLabel("")
        self.prompt_label.setWordWrap(True)
        layout.addWidget(self.prompt_label)

        btns = QHBoxLayout()
        self.ask_input = QLineEdit()
        self.ask_input.returnPressed.connect(self._submit_text)
        btns.addWidget(self.ask_input, 1)
        self.ok_btn = QPushButton("Override / Yes")
        self.ok_btn.clicked.connect(lambda: self._submit("y"))
        self.no_btn = QPushButton("Stop / No")
        self.no_btn.clicked.connect(lambda: self._submit(""))
        self.render_btn = QPushButton("Approve (render)")
        self.render_btn.clicked.connect(lambda: self._submit("y"))
        self.regen_btn = QPushButton("Regenerate (+)")
        self.regen_btn.clicked.connect(lambda: self._submit("+"))
        self.reject_btn = QPushButton("Reject")
        self.reject_btn.clicked.connect(lambda: self._submit("n"))
        for widget in (
            self.ok_btn,
            self.no_btn,
            self.render_btn,
            self.regen_btn,
            self.reject_btn,
        ):
            btns.addWidget(widget)
        layout.addLayout(btns)
        self._set_ask_enabled()

        self.setCentralWidget(root)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pump)
        self._timer.start(100)

    def _refresh_angle(self, text: str) -> None:
        self.angle.setText(angle_mode_line(text))

    def _channel_id(self) -> str:
        data = self.channel.currentData()
        if data:
            return str(data)
        return list_channel_ids()[0]

    def _start(self) -> None:
        topic = self.topic.text().strip()
        if not topic:
            self.progress.setText("Topic required.")
            return
        self.start_btn.setEnabled(False)
        self.output.clear()
        self._log.clear()
        self._log_seen = 0
        self.progress.setText("Running…")
        from core.pinned_status import set_pin_context
        from core.themes import set_channel_theme

        cid = self._channel_id()
        set_channel_theme(cid)
        set_pin_context(cid)
        self._worker = start_run_worker(
            channel_id=cid,
            topic=topic,
            facts_text=self.facts.toPlainText(),
            bridge=self._bridge,
            log_lines=self._log,
            log_lock=self._log_lock,
            on_done=self._on_done,
        )

    def _on_done(self, err: BaseException | None) -> None:
        self._done_box.append(err)

    def _pump(self) -> None:
        with self._log_lock:
            new = self._log[self._log_seen :]
            self._log_seen = len(self._log)
        if new:
            self.output.appendPlainText("\n".join(new))
        tick = self._bridge.progress()
        if tick is not None:
            extra = f" {tick.done}/{tick.total}" if tick.total else ""
            detail = f" · {tick.detail}" if tick.detail else ""
            self.progress.setText(f"{tick.phase}{extra}{detail}")
        if self._pending is None:
            req = self._bridge.wait_request(timeout=0.0)
            if req is not None:
                self._show_request(req)
        if self._done_box:
            err = self._done_box.pop(0)
            self.start_btn.setEnabled(True)
            self._set_ask_enabled()
            if err is not None and not isinstance(err, KeyboardInterrupt):
                self.progress.setText(f"Stopped: {err}")
            else:
                self.progress.setText("Idle — draft is in the output pane / output folder")

    def _show_request(self, req: AskRequest) -> None:
        self._pending = req
        if req.kind == "confirm":
            title = _GATE_LABELS.get(req.gate or "", "Confirm")
            self.prompt_label.setText(f"{title}\n{req.prompt.strip()}")
            self._set_ask_enabled(confirm=True)
        elif req.kind == "proceed":
            self.prompt_label.setText(req.prompt.strip())
            self._set_ask_enabled(proceed=True)
        elif req.kind == "choice":
            self.prompt_label.setText(req.prompt.strip())
            self.ask_input.setPlaceholderText("1-5, or Enter for default")
            self._set_ask_enabled(text=True)
        else:
            self.prompt_label.setText(req.prompt.strip() or "(input)")
            self._set_ask_enabled(text=True)

    def _set_ask_enabled(
        self,
        *,
        text: bool = False,
        confirm: bool = False,
        proceed: bool = False,
    ) -> None:
        enabled = text or confirm or proceed
        self.ask_input.setEnabled(text)
        self.ok_btn.setEnabled(confirm)
        self.no_btn.setEnabled(confirm)
        self.render_btn.setEnabled(proceed)
        self.regen_btn.setEnabled(proceed)
        self.reject_btn.setEnabled(proceed)
        if not enabled:
            self.prompt_label.setText("")
            self.ask_input.clear()

    def _submit_text(self) -> None:
        self._submit(self.ask_input.text())

    def _submit(self, answer: str) -> None:
        if self._pending is None:
            return
        self._pending = None
        self._bridge.submit(answer)
        self._set_ask_enabled()

    def closeEvent(self, event) -> None:
        self._bridge.cancel()
        super().closeEvent(event)
