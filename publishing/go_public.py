"""#864: flip a review-held unlisted upload to public.

The review hold (#109, `YOUTUBE_UNLISTED_REVIEW`) lands an immediate public upload
unlisted so the operator can watch it once. Before this, promoting it meant YouTube
Studio by hand. Mirrors `publishing/rollback.py`: dry run by default, and the YouTube
client is never built unless `apply` *and* YOUTUBE_UPLOAD_ENABLED are both on.

A run rendered past the grounding gate - or a Short cut from one - stays unlisted until
the claim is fixed (#754), so it is refused here too.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from core.run_features import load_features

logger = get_logger("publishing.go_public")


@dataclass
class GoPublicResult:
    status: str
    detail: str = ""
    video_id: str = ""


def go_public_plan(video_id: str) -> dict[str, Any]:
    """videos.update body - status part only, so title/description are untouched."""
    return {"id": video_id, "status": {"privacyStatus": "public"}}


def _override_held(run_id: int | None) -> bool:
    features = load_features(run_id)
    if features.get("grounding_override"):
        return True
    parent = features.get("parent_run_id")
    try:
        return bool(parent and load_features(int(parent)).get("grounding_override"))
    except (TypeError, ValueError):
        return False


def _find(rows: list, video_id: str):
    rows = [r for r in (rows or []) if str(getattr(r, "youtube_video_id", "") or "").strip()]
    if video_id:
        matches = [r for r in rows if str(r.youtube_video_id).strip() == video_id]
    else:
        matches = [r for r in rows if str(r.privacy_status or "").lower() == "unlisted"]
    if not matches:
        return None
    return max(matches, key=lambda r: int(getattr(r, "id", 0) or 0))


def apply_go_public(
    video_id: str = "",
    *,
    channel_id: str = "tapin",
    dry_run: bool = True,
    repo=None,
) -> GoPublicResult:
    """Promote `video_id` (or the newest unlisted hold) to public."""
    video_id = (video_id or "").strip()
    try:
        if repo is None:
            from storage.repositories.publish_log import get_publish_log_repository

            repo = get_publish_log_repository()
        rows = repo.list_uploaded_for_channel(channel_id)
    except Exception as exc:
        logger.warning("go-public: publish log unreadable: %s", exc)
        rows = []
    record = _find(rows, video_id)
    if record is None and not video_id:
        return GoPublicResult("invalid", f"No unlisted upload on record for {channel_id}")
    target = video_id or str(record.youtube_video_id).strip()
    if record is not None and _override_held(record.content_run_id):
        return GoPublicResult(
            "refused",
            f"run {record.content_run_id} was rendered past the grounding gate; it stays "
            "unlisted until the flagged claim is fixed (#754)",
            target,
        )
    body = go_public_plan(target)
    if dry_run:
        return GoPublicResult("dry_run", json.dumps(body), target)
    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        return GoPublicResult(
            "blocked", "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent", target
        )
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return GoPublicResult("blocked", problem, target)
    try:
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        service.videos().update(part="status", body=body).execute()
    except Exception as exc:
        from publishing.snippet_update import edit_error_text

        logger.warning("go-public update failed: %s", exc)
        return GoPublicResult("error", edit_error_text(exc, channel_id), target)
    if record is not None:
        try:
            repo.update(record.id, {"privacy_status": "public"})
        except Exception as exc:
            logger.warning("go-public: publish log not updated: %s", exc)
    return GoPublicResult("updated", f"{target} is public", target)
