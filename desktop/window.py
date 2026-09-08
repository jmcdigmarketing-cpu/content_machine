"""Stage 2 — the run window with token chrome. Pipeline still on a worker."""

from __future__ import annotations

import threading

from PySide6.QtCore import QByteArray, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.channels import get_channel_profiles, list_channel_ids
from core.ask_bridge import AskBridge, AskRequest
from core.chrome import build_qss, empty_state_copy, error_state_copy, icon_svg, look_flags
from desktop.session import (
    angle_mode_line,
    facts_from_drop,
    facts_meter_line,
    load_window_state,
    save_window_state,
    shutdown_worker,
    start_run_worker,
)

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
        self.setAcceptDrops(True)
        self._bridge = AskBridge()
        self._log: list[str] = []
        self._log_lock = threading.Lock()
        self._log_seen = 0
        self._pending: AskRequest | None = None
        self._worker: threading.Thread | None = None
        self._done_box: list[BaseException | None] = []

        root = QWidget()
        layout = QVBoxLayout(root)

        self.brand = QLabel("Content OS")
        self.brand.setObjectName("title_brand")
        layout.addWidget(self.brand)

        row = QHBoxLayout()
        row.addWidget(QLabel("Channel"))
        self.channel = QComboBox()
        for cid in list_channel_ids():
            profile = get_channel_profiles()[cid]
            self.channel.addItem(f"{profile.name} ({cid})", cid)
        self.channel.currentIndexChanged.connect(lambda _i: self._apply_look())
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
            "is how run 74 died; this box keeps the whole paste. Drop a .txt here."
        )
        self.facts.setMinimumHeight(160)
        self.facts.textChanged.connect(self._refresh_facts_meter)
        layout.addWidget(self.facts)
        self.facts_meter = QLabel("")
        self.facts_meter.setObjectName("facts_meter")
        layout.addWidget(self.facts_meter)

        self.start_btn = QPushButton("Start video")
        self.start_btn.setObjectName("start_btn")
        self.start_btn.clicked.connect(self._start)
        layout.addWidget(self.start_btn)

        self.progress = QLabel("Idle")
        self.progress.setObjectName("progress")
        layout.addWidget(self.progress)
        self.empty_state = QLabel(empty_state_copy())
        self.empty_state.setObjectName("empty_state")
        self.empty_state.setWordWrap(True)
        layout.addWidget(self.empty_state)
        self.error_state = QLabel("")
        self.error_state.setObjectName("error_state")
        self.error_state.setWordWrap(True)
        layout.addWidget(self.error_state)

        layout.addWidget(QLabel("Output"))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        self.prompt_label = QLabel("")
        self.prompt_label.setWordWrap(True)
        layout.addWidget(self.prompt_label)

        self.angle_list = QListWidget()
        self.angle_list.setObjectName("angle_list")
        self.angle_list.itemClicked.connect(self._pick_angle)
        self.angle_list.hide()
        layout.addWidget(self.angle_list)

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
        self._apply_look()
        self._restore_geometry()
        self._refresh_facts_meter()

    def _channel_id(self) -> str:
        data = self.channel.currentData()
        if data:
            return str(data)
        return list_channel_ids()[0]

    def _apply_look(self) -> None:
        flags = look_flags()
        cid = self._channel_id()
        self.setStyleSheet(
            build_qss(
                cid,
                reduced_chroma=flags["reduced_chroma"],
                high_contrast=flags["high_contrast"],
                reduced_motion=flags["reduced_motion"],
                colorblind=flags["colorblind"],
            )
        )
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(icon_svg(cid).encode("utf-8")))
        self.setWindowIcon(QIcon(pixmap))
        self.brand.setText("TapIn" if cid == "tapin" else "MoneyWise")

    def _restore_geometry(self) -> None:
        state = load_window_state(self._channel_id())

        def _px(key: str) -> int:
            raw = state.get(key, 0)
            if isinstance(raw, bool):
                return 0
            if isinstance(raw, int):
                return raw
            if isinstance(raw, float):
                return int(raw)
            if isinstance(raw, str):
                try:
                    return int(float(raw))
                except ValueError:
                    return 0
            return 0

        w, h, x, y = _px("w"), _px("h"), _px("x"), _px("y")
        if w >= 400 and h >= 400:
            self.resize(w, h)
        if "x" in state and "y" in state:
            self.move(x, y)

    def _persist_geometry(self) -> None:
        geo = self.geometry()
        screen = self.screen()
        name = ""
        if screen is not None:
            name = str(screen.name() or "")
        save_window_state(
            self._channel_id(),
            {"x": geo.x(), "y": geo.y(), "w": geo.width(), "h": geo.height(), "screen": name},
        )

    def _refresh_facts_meter(self) -> None:
        self.facts_meter.setText(facts_meter_line(self.facts.toPlainText()))

    def _refresh_angle(self, text: str) -> None:
        self.angle.setText(angle_mode_line(text))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime is not None and (mime.hasUrls() or mime.hasText()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        if mime is None:
            return
        urls = [str(u.toLocalFile() or u.toString()) for u in mime.urls()]
        blob = facts_from_drop(urls) if urls else (mime.text() or "")
        if blob:
            existing = self.facts.toPlainText().strip()
            self.facts.setPlainText((existing + "\n" + blob).strip() if existing else blob)
            event.acceptProposedAction()

    def _start(self) -> None:
        topic = self.topic.text().strip()
        if not topic:
            self.progress.setText("Topic required.")
            self.empty_state.setText(empty_state_copy())
            return
        self.start_btn.setEnabled(False)
        self.output.clear()
        self._log.clear()
        self._log_seen = 0
        self.progress.setText("Running…")
        self.empty_state.setText("")
        self.error_state.setText("")
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
                self.error_state.setText(error_state_copy(str(err)))
            else:
                self.progress.setText("Idle — draft is in the output pane / output folder")
                self.empty_state.setText(empty_state_copy())

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
            titles = self._bridge.choices()
            self.angle_list.clear()
            if titles and (req.gate == "angles" or not req.gate):
                for title in titles:
                    self.angle_list.addItem(title)
                self.angle_list.show()
                self._set_ask_enabled(text=True, listing=True)
            else:
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
        listing: bool = False,
    ) -> None:
        enabled = text or confirm or proceed or listing
        self.ask_input.setEnabled(text)
        self.ok_btn.setEnabled(confirm)
        self.no_btn.setEnabled(confirm)
        self.render_btn.setEnabled(proceed)
        self.regen_btn.setEnabled(proceed)
        self.reject_btn.setEnabled(proceed)
        if listing:
            self.angle_list.show()
        else:
            self.angle_list.hide()
        if not enabled:
            self.prompt_label.setText("")
            self.ask_input.clear()
            self.angle_list.clear()

    def _pick_angle(self, item: QListWidgetItem) -> None:
        row = self.angle_list.row(item)
        if row >= 0:
            self._submit(str(row + 1))

    def _submit_text(self) -> None:
        self._submit(self.ask_input.text())

    def _submit(self, answer: str) -> None:
        if self._pending is None:
            return
        self._pending = None
        self._bridge.submit(answer)
        self._set_ask_enabled()

    def closeEvent(self, event) -> None:
        self._persist_geometry()
        # Cancel *and wait*. `cancel()` alone only reaches a worker blocked in an
        # ask; the thread is a daemon, so without a join a close mid-render
        # abandoned ffmpeg/TTS/an upload in silence -- the run-73 failure this
        # stage exists to prevent. Bounded, and it says so when it gives up.
        shutdown_worker(self._worker, self._bridge)
        self._worker = None
        super().closeEvent(event)
