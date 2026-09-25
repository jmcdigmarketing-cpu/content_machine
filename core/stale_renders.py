"""Retire rendered videos that sat unuploaded past their news date (2026-09-16).

`ops status` counted "5 rendered, not on YouTube" - runs from June and July about a
third-place match and a UFC card long over. They are not a backlog to publish, they are
noise in the number the operator reads every morning. Retiring marks
`features.retired_at`; `scripts.requeue_upload.list_recyclable` then skips the run. The
mp4 stays on disk and `requeue_upload --run-id N --queue` still takes it by id.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.run_features import merge_features

logger = get_logger("core.stale_renders")


def render_age_days(run: Any, *, now: float | None = None) -> float | None:
    path = str(getattr(run, "mp4_path", "") or "")
    try:
        modified = os.path.getmtime(path)
    except OSError:
        return None
    return max(0.0, ((now or time.time()) - modified) / 86400.0)


def find_stale_renders(channel_id: str, *, days: int = 30) -> list[Any]:
    """Unuploaded, unretired renders whose mp4 is older than `days`."""
    from scripts.requeue_upload import list_recyclable

    out = []
    for run in list_recyclable(channel_id):
        age = render_age_days(run)
        if age is not None and age >= days:
            out.append(run)
    return out


def retire_renders(runs: list[Any]) -> list[int]:
    """Mark each run retired. Returns the ids marked. Never deletes a file."""
    stamp = datetime.now().isoformat(timespec="seconds")
    marked: list[int] = []
    for run in runs:
        try:
            merge_features(int(run.id), {"retired_at": stamp})
            marked.append(int(run.id))
        except Exception as exc:
            logger.warning("retire skipped for run %s: %s", getattr(run, "id", "?"), exc)
    return marked
