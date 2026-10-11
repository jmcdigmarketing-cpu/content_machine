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


STALE_DAYS = 30


def shelf(channel_id: str, *, days: int = STALE_DAYS) -> dict[str, int]:
    """Finished videos that are not public (#1122).

    129 runs had produced 32 public videos; 13 renders were never uploaded and 5 uploads were
    still unlisted, and no line the operator reads each morning said so. `renders` is every
    unuploaded, unretired render, `stale` those past `days`; `unlisted` is every upload still
    unlisted, `claim` those rendered past the grounding gate (they need `verify-claim` first).
    """
    from publishing.go_public import override_held, unlisted_holds
    from scripts.requeue_upload import list_recyclable

    renders = list_recyclable(channel_id)
    stale = 0
    for run in renders:
        age = render_age_days(run)
        if age is not None and age >= days:
            stale += 1
    held = unlisted_holds(channel_id)
    claim = sum(1 for row in held if override_held(getattr(row, "content_run_id", None)))
    return {"renders": len(renders), "stale": stale, "unlisted": len(held), "claim": claim}


def shelf_total(counts: dict[str, int]) -> int:
    return int(counts.get("renders") or 0) + int(counts.get("unlisted") or 0)


def shelf_lines(channel_id: str, counts: dict[str, int], *, days: int = STALE_DAYS) -> list[str]:
    """One line per kind of unpublished video, each with the command that moves it."""
    out: list[str] = []
    unlisted, claim = int(counts.get("unlisted") or 0), int(counts.get("claim") or 0)
    if unlisted:
        parts = []
        if unlisted - claim:
            parts.append(
                f"{unlisted - claim} ready - py -m scripts.ops go-public --channel {channel_id}"
            )
        if claim:
            parts.append(f"{claim} held for a claim - py -m scripts.ops verify-claim --run-id N")
        out.append(f"Unlisted, not public: {unlisted} video(s) ({'; '.join(parts)})")
    renders, stale = int(counts.get("renders") or 0), int(counts.get("stale") or 0)
    if renders:
        parts = []
        if renders - stale:
            parts.append(
                f"{renders - stale} recent - py -m scripts.requeue_upload --channel {channel_id}"
            )
        if stale:
            parts.append(
                f"{stale} older than {days} days - "
                f"py -m scripts.ops retire-renders --channel {channel_id}"
            )
        out.append(f"Rendered, not on YouTube: {renders} video(s) ({'; '.join(parts)})")
    return out


def shelf_short(counts: dict[str, int]) -> str:
    """The header's few words, or "" when everything finished is public."""
    total = shelf_total(counts)
    return f"{total} finished, not public" if total else ""


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
