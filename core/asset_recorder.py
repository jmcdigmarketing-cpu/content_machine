"""Persist background + thumbnail assets linked to a content run."""

from __future__ import annotations

import os

from assets.flux_thumbnail import generate_thumbnail
from assets.types import AssetResult
from config.channels import resolve_channel_id
from core.logging import get_logger
from core.output_paths import ensure_channel_output_dirs
from storage.repositories.assets import get_asset_repository

logger = get_logger("core.asset_recorder")


def _safe_create(repo, data: dict) -> None:
    try:
        repo.create(data)
    except Exception as exc:
        logger.warning(
            "Asset record skipped (%s): %s",
            data.get("asset_type", "unknown"),
            exc,
        )


def record_render_assets(
    *,
    channel_id: str,
    content_run_id: int,
    topic: str,
    title: str,
    mp4_path: str,
    background: AssetResult | None = None,
    thumbnail_path: str | None = None,
) -> None:
    channel_id = resolve_channel_id(channel_id)
    repo = get_asset_repository()

    if background and background.path:
        _safe_create(
            repo,
            {
                "channel_id": channel_id,
                "content_run_id": content_run_id,
                "asset_type": "background",
                "provider": background.provider,
                "path": background.path,
                "source_id": background.source_id or "",
                "query": topic,
                "attribution": background.attribution or "",
            },
        )

    if mp4_path:
        _safe_create(
            repo,
            {
                "channel_id": channel_id,
                "content_run_id": content_run_id,
                "asset_type": "render",
                "provider": "ffmpeg",
                "path": mp4_path,
                "query": topic,
            },
        )

    if thumbnail_path and os.path.isfile(thumbnail_path):
        _safe_create(
            repo,
            {
                "channel_id": channel_id,
                "content_run_id": content_run_id,
                "asset_type": "thumbnail",
                "provider": "flux" if "flux" in thumbnail_path.lower() else "pillow",
                "path": thumbnail_path,
                "query": topic,
            },
        )
    elif os.getenv("THUMBNAIL_MODE", "auto").lower() != "off":
        thumb_dir = ensure_channel_output_dirs(channel_id)["thumbnails"]
        grade_letter = None
        try:
            from core.video_grade import grade_run

            graded = grade_run(content_run_id)
            grade_letter = graded.letter if graded else None
        except Exception as exc:
            logger.debug("thumbnail grade lookup skipped: %s", exc)
        thumb = generate_thumbnail(
            topic,
            title or topic,
            output_dir=thumb_dir,
            content_run_id=content_run_id,
            channel_id=channel_id,
            grade_letter=grade_letter,
        )
        if thumb.path:
            _safe_create(
                repo,
                {
                    "channel_id": channel_id,
                    "content_run_id": content_run_id,
                    "asset_type": "thumbnail",
                    "provider": "flux" if thumb.detail and "Flux" in thumb.detail else "pillow",
                    "path": thumb.path,
                    "query": topic,
                    "attribution": thumb.detail or "",
                },
            )
        elif thumb.status not in ("not_configured",):
            logger.debug("Thumbnail skipped: %s", thumb.detail or thumb.status)
