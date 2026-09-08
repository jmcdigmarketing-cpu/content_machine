"""Same-run bind for the review room: never pair a leftover mp4 with a drafted run."""

from __future__ import annotations

import os
from typing import Any

from core.review_keys import approve_command


def bind_review_media(
    *,
    run_id: Any,
    run_status: str,
    run_mp4: str | None,
    leftover_mp4: str | None,
) -> dict[str, Any]:
    """Pick one run whose file exists. A leftover output/default mp4 is not that run."""
    run_file = str(run_mp4 or "").strip()
    leftover = str(leftover_mp4 or "").strip()
    status = str(run_status or "").strip().lower()
    if run_file and os.path.isfile(run_file) and status != "drafted":
        return {
            "mp4_path": os.path.abspath(run_file),
            "run_id": run_id,
            "run_status": status,
            "can_approve": True,
            "refuse_reason": "",
        }
    label = run_id if run_id not in (None, "") else "(unknown)"
    reason = f"Run {label} has no MP4 on disk. Status: {status or 'unknown'}"
    if leftover and os.path.isfile(leftover):
        reason += f". Player will not load leftover {os.path.basename(leftover)}"
    return {
        "mp4_path": "",
        "run_id": run_id,
        "run_status": status,
        "can_approve": False,
        "refuse_reason": reason,
    }


def queued_approve_command(ctx: dict[str, Any] | None) -> str | None:
    """None when Approve would queue a drafted or empty-path run."""
    data = dict(ctx or {})
    if data.get("can_approve") is False:
        return None
    status = str(data.get("run_status") or "").strip().lower()
    if status == "drafted":
        return None
    mp4 = str(data.get("mp4_path") or data.get("mp4") or "").strip()
    if not mp4 or not os.path.isfile(mp4):
        return None
    cmd = approve_command(data)
    if "requeue-upload" in cmd and status == "drafted":
        return None
    return cmd
