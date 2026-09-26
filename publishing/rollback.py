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


def rollback_plan(
    video_id: str, correction: str, current_snippet: dict[str, Any] | None = None
) -> dict[str, Any]:
    """videos.update body. Never sent until apply_rollback(apply=True).

    With the live snippet (#865) the correction is prepended to the existing
    description and every writable field is sent; YouTube rejects a snippet without
    title and categoryId. Without it (a dry run) the snippet shows only the new line.
    """
    note = (correction or "").strip() or "Correction filed from Content OS."
    line = f"Correction: {note}"
    snippet: dict[str, Any] = {"description": line}
    if current_snippet is not None:
        from publishing.snippet_update import writable_snippet

        old = str(current_snippet.get("description") or "").strip()
        snippet = writable_snippet(current_snippet, description=f"{line}\n\n{old}" if old else line)
    return {
        "id": video_id,
        "status": {"privacyStatus": "unlisted"},
        "snippet": snippet,
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
        return RollbackResult(
            "dry_run",
            json.dumps(body, indent=2)
            + "\n(on --apply the live title, category and tags are read and sent back)",
            dossier,
        )

    enabled = os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() in ("1", "true", "yes")
    if not enabled:
        return RollbackResult(
            "blocked",
            "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent",
            dossier,
        )
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return RollbackResult("blocked", problem, dossier)
    try:
        from publishing.snippet_update import fetch_snippets
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        live = fetch_snippets(service, [video_id]).get(video_id)
        if live is None:
            return RollbackResult("error", f"{video_id} not found on YouTube", dossier)
        body = rollback_plan(video_id, correction, live)
        service.videos().update(part="status,snippet", body=body).execute()
    except Exception as exc:
        from publishing.snippet_update import edit_error_text

        logger.warning("rollback update failed: %s", exc)
        return RollbackResult("error", edit_error_text(exc, channel_id), dossier)
    return RollbackResult("updated", f"{video_id} unlisted", dossier)
