"""#437: unlist a published video and file a correction dossier.

Default is dry-run. The YouTube client is never constructed unless the
operator passes apply=True *and* YOUTUBE_UPLOAD_ENABLED is on.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger("publishing.rollback")


@dataclass
class RollbackResult:
    status: str
    detail: str = ""
    dossier_path: str | None = None


def rollback_plan(video_id: str, correction: str) -> dict[str, Any]:
    """videos.update body. Never sent until apply_rollback(apply=True)."""
    note = (correction or "").strip() or "Correction filed from Content OS."
    return {
        "id": video_id,
        "status": {"privacyStatus": "unlisted"},
        "snippet": {"description": f"Correction: {note}"},
    }


def _write_dossier(
    channel_id: str, video_id: str, correction: str, body: dict[str, Any]
) -> str | None:
    try:
        from core.vault_dossiers import write_report_note

        rendered = (
            f"video_id: {video_id}\n"
            f"privacy: unlisted\n"
            f"correction: {correction}\n\n"
            f"{json.dumps(body, indent=2)}"
        )
        path = write_report_note(
            channel_id,
            "rollback",
            f"Publish rollback {video_id}",
            rendered,
            fenced=True,
        )
        return str(path) if path else None
    except Exception as exc:
        logger.warning("rollback dossier not written: %s", exc)
        return None


def apply_rollback(
    video_id: str,
    *,
    correction: str,
    channel_id: str = "tapin",
    dry_run: bool = True,
) -> RollbackResult:
    if not (video_id or "").strip():
        return RollbackResult("invalid", "No video_id")
    body = rollback_plan(video_id, correction)
    dossier = _write_dossier(channel_id, video_id, correction, body)
    if dry_run:
        return RollbackResult("dry_run", json.dumps(body, indent=2), dossier)

    enabled = os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() in ("1", "true", "yes")
    if not enabled:
        return RollbackResult(
            "blocked",
            "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent",
            dossier,
        )
    try:
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        service.videos().update(part="status,snippet", body=body).execute()
    except Exception as exc:
        logger.warning("rollback update failed: %s", exc)
        return RollbackResult("error", str(exc)[:300], dossier)
    return RollbackResult("updated", f"{video_id} unlisted", dossier)
