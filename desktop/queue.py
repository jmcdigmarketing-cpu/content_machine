"""Stage 3 job queue: one store, drag-reorder via payload sort_key."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from core.chrome import build_qss, look_flags
from core.job_queue import apply_drag_order, display_status, list_active_jobs, queue_depth_badge
from storage.repositories.jobs import JobRecord, get_job_repository


class QueueWindow(QMainWindow):
    def __init__(self, jobs: list[JobRecord] | None = None, repo=None) -> None:
        super().__init__()
        self.setWindowTitle("Content OS — queue")
        self.resize(720, 540)
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
        self._repo = repo or get_job_repository()
        rows = list(jobs) if jobs is not None else list_active_jobs(self._repo)
        root = QWidget()
        layout = QVBoxLayout(root)
        brand = QLabel("Job queue")
        brand.setObjectName("title_brand")
        layout.addWidget(brand)
        self.badge = QLabel(f"depth {queue_depth_badge(rows)}")
        layout.addWidget(self.badge)
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        for job in rows:
            label = (
                f"{display_status(job)} #{job.id} {job.job_type} "
                f"{job.status} {job.scheduled_at or ''}"
            ).strip()
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, int(job.id))
            self.list_widget.addItem(item)
        self.list_widget.model().rowsMoved.connect(self._persist_order)
        layout.addWidget(self.list_widget, 1)
        self.setCentralWidget(root)

    def _persist_order(self, *_args) -> None:
        ordered: list[int] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item is None:
                continue
            job_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                ordered.append(int(job_id))
            except (TypeError, ValueError):
                continue
        try:
            apply_drag_order(self._repo, ordered)
        except Exception as exc:
            from core.logging import get_logger

            get_logger("desktop.queue").debug("queue reorder skipped: %s", exc)
