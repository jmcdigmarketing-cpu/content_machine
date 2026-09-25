"""#444 persist minutes-per-published-video (not quota_state)."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from config.paths import DATA_DIR, ensure_data_dir
from core.logging import get_logger

logger = get_logger("core.operator_minutes")

MINUTES_FILE = os.path.join(DATA_DIR, "operator_minutes.json")


def _load(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("operator minutes read skipped: %s", exc)
        return {}


def record_publish_minutes(channel_id: str, minutes: float, *, path: str | None = None) -> None:
    dest = path or MINUTES_FILE
    try:
        ensure_data_dir()
        data = _load(dest)
        bucket = data.setdefault(channel_id, [])
        if not isinstance(bucket, list):
            bucket = []
        bucket.append(float(minutes))
        data[channel_id] = bucket[-50:]
        directory = os.path.dirname(dest) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="opmin_", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, dest)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.debug("operator minutes write skipped: %s", exc)


def trend_line(channel_id: str, *, path: str | None = None) -> str:
    data = _load(path or MINUTES_FILE)
    rows = data.get(channel_id) or []
    nums = []
    for raw in rows:
        try:
            nums.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not nums:
        return "minutes/video: n/a"
    avg = sum(nums) / len(nums)
    return f"minutes/video: {avg:.1f} ({len(nums)} published)"
