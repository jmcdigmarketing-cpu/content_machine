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
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from core.run_features import load_features

logger = get_logger("publishing.go_public")


@dataclass
class GoPublicResult:
    status: str
    detail: str = ""
    video_id: str = ""
    # #1087: what is about to go public - the operator saw only an id (CGFtzpiA1so).
    run_id: int | None = None
    title: str = ""
    holds: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        run = f"run {self.run_id}" if self.run_id else "a run not on record"
        title = f' - "{self.title}"' if self.title else ""
        return f"{run}{title} ({self.video_id})"


def go_public_plan(video_id: str) -> dict[str, Any]:
    """videos.update body - status part only, so title/description are untouched."""
    return {"id": video_id, "status": {"privacyStatus": "public"}}


def override_held(run_id: int | None) -> bool:
    """The run - or the run a Short was cut from - was rendered past the grounding gate."""
    features = load_features(run_id)
    if features.get("grounding_override"):
        return True
    parent = features.get("parent_run_id")
    try:
        return bool(parent and load_features(int(parent)).get("grounding_override"))
    except (TypeError, ValueError):
        return False


def _run_title(run_id: int | None) -> str:
    """The run's title from its record, or "" (#1087)."""
    if not run_id:
        return ""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(int(run_id))
        return str(getattr(record, "title", "") or "")
    except Exception as exc:
        logger.debug("go-public: title for run %s unavailable: %s", run_id, exc)
        return ""


def _holds(rows: list) -> list:
    """Unlisted uploads with a video id, newest first."""
    held = [
        r
        for r in (rows or [])
        if str(getattr(r, "youtube_video_id", "") or "").strip()
        and str(r.privacy_status or "").lower() == "unlisted"
    ]
    return sorted(held, key=lambda r: int(getattr(r, "id", 0) or 0), reverse=True)


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
    run_id = record.content_run_id if record is not None else None
    title = _run_title(run_id)
    # #1087: with no id and more than one hold, "the newest" is a guess the operator never
    # saw - list them on the dry run, and refuse to send until one is named.
    holds = (
        [
            f"{str(r.youtube_video_id).strip()} (run {r.content_run_id}: "
            f"{_run_title(r.content_run_id) or 'untitled'})"
            for r in _holds(rows)
        ]
        if not video_id
        else []
    )
    if len(holds) > 1 and not dry_run:
        return GoPublicResult(
            "invalid",
            f"{len(holds)} unlisted holds - name the one to publish: " + "; ".join(holds),
            target,
            holds=holds,
            run_id=run_id,
            title=title,
        )
    if record is not None and override_held(record.content_run_id):
        return GoPublicResult(
            "refused",
            f"run {record.content_run_id} was rendered past the grounding gate; it stays "
            "unlisted until the flagged claim is fixed (#754) - confirm or reject it with: "
            f"py -m scripts.ops verify-claim --run-id {record.content_run_id}",
            target,
            run_id=run_id,
            title=title,
        )
    body = go_public_plan(target)
    if dry_run:
        return GoPublicResult(
            "dry_run", json.dumps(body), target, holds=holds, run_id=run_id, title=title
        )
    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        return GoPublicResult(
            "blocked",
            "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent",
            target,
            run_id=run_id,
            title=title,
        )
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return GoPublicResult("blocked", problem, target, run_id=run_id, title=title)
    try:
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        service.videos().update(part="status", body=body).execute()
    except Exception as exc:
        from publishing.snippet_update import edit_error_text

        logger.warning("go-public update failed: %s", exc)
        return GoPublicResult(
            "error", edit_error_text(exc, channel_id), target, run_id=run_id, title=title
        )
    if record is not None:
        try:
            repo.update(record.id, {"privacy_status": "public"})
        except Exception as exc:
            logger.warning("go-public: publish log not updated: %s", exc)
    result = GoPublicResult("updated", "", target, run_id=run_id, title=title)
    result.detail = f"{result.label} is public"
    return result
