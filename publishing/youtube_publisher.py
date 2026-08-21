"""
YouTube upload — OAuth, resumable videos.insert, idempotent publish_log.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from apis.signal_contract import classify_exception, classify_http
from apis.youtube_quota import (
    format_quota_detail,
    has_quota_for_upload,
    record_upload_usage,
)
from config.channels import resolve_channel_id
from core.logging import get_logger
from publishing.base import (
    PLATFORM_YOUTUBE,
    PUBLISH_STATUS_SUCCESS,
    Publisher,
    PublishRequest,
    PublishResult,
)
from publishing.idempotency import idempotency_key
from storage.repositories.publish_log import get_publish_log_repository
from youtube.oauth import (
    _client_secrets_path,
    get_youtube_service,
    token_path_for_channel,
)
from youtube.thumbnails import (
    maybe_upload_thumbnail,
    merge_thumbnail_into_upload_detail,
)

logger = get_logger("publishing.youtube")

YOUTUBE_PUBLISH_MIN_LEAD_MINUTES = 15
TERMINAL_LOG_STATUSES = PUBLISH_STATUS_SUCCESS


def is_youtube_configured(channel_id: str | None = None) -> bool:
    channel_id = resolve_channel_id(channel_id)
    enabled = os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not enabled:
        return False
    secrets = _client_secrets_path()
    token = token_path_for_channel(channel_id)
    return os.path.isfile(secrets) and os.path.isfile(token)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_publish_at_rfc3339(dt: datetime) -> str:
    return _to_utc(dt).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def unlisted_review_enabled() -> bool:
    return os.getenv("YOUTUBE_UNLISTED_REVIEW", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def apply_unlisted_review(privacy_status: str, *, publish_at=None) -> tuple[str, bool]:
    """Hold immediate public uploads as unlisted for an operator eyeball.

    Scheduled publishAt already lands private until the slot — leave that path.
    Returns (effective_privacy, held_for_review).
    """
    if publish_at:
        return privacy_status, False
    if (privacy_status or "").strip().lower() != "public":
        return privacy_status, False
    if not unlisted_review_enabled():
        return privacy_status, False
    return "unlisted", True


def build_video_status(request: PublishRequest) -> dict[str, Any]:
    status: dict[str, Any] = {"selfDeclaredMadeForKids": False}
    if not request.publish_at:
        privacy, _held = apply_unlisted_review(request.privacy_status)
        status["privacyStatus"] = privacy
        try:
            from core.youtube_meta import audit_made_for_kids

            status = audit_made_for_kids(status)
        except Exception as exc:
            logger.debug("madeForKids audit skipped: %s", exc)
            status["selfDeclaredMadeForKids"] = False
        return status

    publish_at = _to_utc(request.publish_at)
    min_at = datetime.now(timezone.utc) + timedelta(minutes=YOUTUBE_PUBLISH_MIN_LEAD_MINUTES)
    if publish_at < min_at:
        publish_at = min_at

    status["privacyStatus"] = "private"
    status["publishAt"] = _to_publish_at_rfc3339(publish_at)
    try:
        from core.youtube_meta import audit_made_for_kids

        status = audit_made_for_kids(status)
    except Exception as exc:
        logger.debug("madeForKids audit skipped: %s", exc)
        status["selfDeclaredMadeForKids"] = False
    return status


def _find_video_on_channel(service, title: str, *, max_results: int = 20) -> str | None:
    try:
        channels = service.channels().list(part="contentDetails", mine=True).execute()
        items = channels.get("items") or []
        if not items:
            return None
        uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        playlist = (
            service.playlistItems()
            .list(playlistId=uploads_id, part="snippet", maxResults=max_results)
            .execute()
        )
        target = title.strip()[:100]
        for item in playlist.get("items") or []:
            snippet = item.get("snippet") or {}
            if snippet.get("title") == target:
                return (snippet.get("resourceId") or {}).get("videoId")
    except HttpError as e:
        if "insufficientPermissions" in str(e) or "insufficient authentication scopes" in str(e):
            logger.warning(
                "Duplicate-upload check skipped: OAuth token lacks youtube.readonly. "
                "Re-run `py -m youtube.oauth_setup --channel <id>` to enable it."
            )
        else:
            logger.warning("YouTube playlist lookup failed: %s", e)
    except Exception as e:
        logger.debug("Channel video lookup failed: %s", e)
    return None


def _result_from_existing_log(
    existing,
    *,
    service=None,
    request: PublishRequest | None = None,
    channel_id: str = "",
    content_run_id: int | None = None,
) -> PublishResult | None:
    if existing.status == "cancelled":
        return None
    if existing.status in TERMINAL_LOG_STATUSES and existing.youtube_video_id:
        base = f"Idempotent: publish_log already {existing.status}"
        if service and request:
            thumb = maybe_upload_thumbnail(
                service,
                video_id=existing.youtube_video_id,
                channel_id=channel_id,
                content_run_id=content_run_id,
                thumbnail_path=request.thumbnail_path,
            )
            return PublishResult(
                video_id=existing.youtube_video_id,
                status=existing.status,
                detail=merge_thumbnail_into_upload_detail(base, thumb),
                publish_log_id=existing.id,
                thumbnail_status=thumb.status,
                thumbnail_detail=thumb.detail,
                platform=PLATFORM_YOUTUBE,
            )
        return PublishResult(
            video_id=existing.youtube_video_id,
            status=existing.status,
            detail=base,
            publish_log_id=existing.id,
            platform=PLATFORM_YOUTUBE,
        )
    return None


def _resolve_prior_upload(
    request: PublishRequest,
    *,
    channel_id: str,
    content_run_id: int | None,
    service,
) -> PublishResult | None:
    if not content_run_id:
        return None

    repo = get_publish_log_repository()
    key = idempotency_key(content_run_id, channel_id, PLATFORM_YOUTUBE)
    existing = repo.find_by_idempotency(key)
    if existing and existing.status == "cancelled":
        existing = None

    if not existing:
        return None

    prior = _result_from_existing_log(
        existing,
        service=service,
        request=request,
        channel_id=channel_id,
        content_run_id=content_run_id,
    )
    if prior:
        return prior

    if existing.status != "pending" or not service:
        return None

    video_id = _find_video_on_channel(service, request.title)
    if not video_id:
        logger.info(
            "publish_log %s pending with no matching YouTube video — will upload",
            existing.id,
        )
        return None

    log_status = "scheduled" if request.publish_at else "uploaded"
    publish_when = _to_utc(request.publish_at) if request.publish_at else datetime.now(timezone.utc)
    repo.update(
        existing.id,
        {
            "status": log_status,
            "youtube_video_id": video_id,
            "detail": "Recovered from YouTube after pending publish_log (crash window)",
            "published_at": publish_when,
        },
    )
    logger.warning("Healed pending publish_log %s with youtube_video_id=%s", existing.id, video_id)
    base_detail = "Healed pending row from YouTube — no re-upload"
    thumb = maybe_upload_thumbnail(
        service,
        video_id=video_id,
        channel_id=channel_id,
        content_run_id=content_run_id,
        thumbnail_path=request.thumbnail_path,
    )
    return PublishResult(
        video_id=video_id,
        status=log_status,
        detail=merge_thumbnail_into_upload_detail(base_detail, thumb),
        publish_log_id=existing.id,
        thumbnail_status=thumb.status,
        thumbnail_detail=thumb.detail,
        platform=PLATFORM_YOUTUBE,
    )


def _ensure_publish_log(
    *,
    content_run_id: int | None,
    channel_id: str,
    privacy_status: str,
    status: str,
    detail: str = "",
    idempotency_key_value: str = "",
) -> int:
    if content_run_id is None:
        return 0

    repo = get_publish_log_repository()
    if idempotency_key_value:
        existing = repo.find_by_idempotency(idempotency_key_value)
        if existing:
            if existing.status not in TERMINAL_LOG_STATUSES:
                repo.update(
                    existing.id,
                    {
                        "status": status,
                        "detail": detail or existing.detail,
                        "privacy_status": privacy_status,
                    },
                )
            return existing.id

    record = repo.create(
        {
            "content_run_id": content_run_id,
            "channel_id": channel_id,
            "youtube_video_id": "",
            "privacy_status": privacy_status,
            "status": status,
            "detail": detail,
            "idempotency_key": idempotency_key_value,
        }
    )
    return record.id


def _update_publish_log(log_id: int, data: dict) -> None:
    if log_id:
        get_publish_log_repository().update(log_id, data)


class YouTubePublisher(Publisher):
    platform = PLATFORM_YOUTUBE

    def is_configured(self, channel_id: str) -> bool:
        return is_youtube_configured(channel_id)

    def publish(
        self,
        request: PublishRequest,
        *,
        channel_id: str,
        content_run_id: int | None = None,
    ) -> PublishResult:
        channel_id = resolve_channel_id(channel_id)
        idem = idempotency_key(content_run_id, channel_id, PLATFORM_YOUTUBE)

        if not self.is_configured(channel_id):
            log_id = _ensure_publish_log(
                content_run_id=content_run_id,
                channel_id=channel_id,
                privacy_status=request.privacy_status,
                status="not_configured",
                detail="OAuth not configured",
                idempotency_key_value=idem,
            )
            return PublishResult(
                video_id=None,
                status="not_configured",
                detail=(
                    "Set YOUTUBE_UPLOAD_ENABLED=true, client secrets, and run "
                    "py -m youtube.oauth_setup --channel <id>"
                ),
                publish_log_id=log_id or None,
                platform=PLATFORM_YOUTUBE,
            )

        if not os.path.isfile(request.file_path):
            return PublishResult(
                video_id=None,
                status="invalid_file",
                detail=f"File not found: {request.file_path}",
                platform=PLATFORM_YOUTUBE,
            )

        service = get_youtube_service(channel_id)
        if not service:
            return PublishResult(
                video_id=None,
                status="auth_error",
                detail="OAuth token invalid or expired — re-run youtube.oauth_setup",
                platform=PLATFORM_YOUTUBE,
            )

        prior = _resolve_prior_upload(
            request, channel_id=channel_id, content_run_id=content_run_id, service=service
        )
        if prior:
            return prior

        if not has_quota_for_upload():
            return PublishResult(
                video_id=None,
                status="quota_exceeded",
                detail=f"Upload quota exhausted — {format_quota_detail()}",
                platform=PLATFORM_YOUTUBE,
            )

        try:
            from core.youtube_meta import lint_ufc_title, title_collision, uniqueness_mode

            hit = title_collision(request.title, channel_id, exclude_run_id=content_run_id)
            if hit:
                logger.warning("%s", hit)
                if uniqueness_mode() == "block":
                    return PublishResult(
                        video_id=None,
                        status="blocked",
                        detail=hit,
                        platform=PLATFORM_YOUTUBE,
                    )
            domain = ""
            try:
                from apis.topic_scorer import infer_domain

                domain = infer_domain(request.title, channel_id)
            except Exception as exc:
                logger.debug("title lint domain skipped: %s", exc)
            for warn in lint_ufc_title(request.title, domain=domain):
                logger.warning("%s", warn)
        except Exception as exc:
            logger.debug("title uniqueness/lint skipped: %s", exc)

        log_id = _ensure_publish_log(
            content_run_id=content_run_id,
            channel_id=channel_id,
            privacy_status=request.privacy_status,
            status="pending",
            detail="Upload in progress",
            idempotency_key_value=idem,
        )

        video_status = build_video_status(request)
        is_youtube_scheduled = "publishAt" in video_status
        effective_privacy, held_review = apply_unlisted_review(
            request.privacy_status, publish_at=request.publish_at
        )
        target_privacy = request.privacy_status

        snippet = {
            "title": request.title[:100],
            "description": request.description[:5000],
            "tags": (request.tags or [])[:30],
            "categoryId": request.category_id or "",
        }
        try:
            from core.youtube_meta import apply_snippet_defaults

            snippet = apply_snippet_defaults(snippet, topic=request.title, channel_id=channel_id)
        except Exception as exc:
            logger.debug("snippet defaults skipped: %s", exc)
            if not snippet.get("categoryId"):
                snippet["categoryId"] = "20"

        body = {
            "snippet": snippet,
            "status": video_status,
        }

        try:
            record_upload_usage()

            from core.output_paths import windows_long_prefix

            media = MediaFileUpload(
                windows_long_prefix(request.file_path),
                mimetype="video/mp4",
                chunksize=1024 * 1024,
                resumable=True,
            )
            insert_request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    logger.info("Upload progress: %s%%", int(status.progress() * 100))

            video_id = response.get("id") or ""

            if video_id and log_id:
                _update_publish_log(log_id, {"youtube_video_id": video_id})

            publish_when = _to_utc(request.publish_at) if request.publish_at else None
            log_status = "scheduled" if is_youtube_scheduled else "uploaded"
            detail = (
                f"YouTube scheduled publish at {video_status.get('publishAt')} "
                f"(target visibility: {target_privacy})"
                if is_youtube_scheduled
                else "videos.insert completed"
            )
            if held_review and video_id:
                watch = f"https://www.youtube.com/watch?v={video_id}"
                detail = (
                    f"Unlisted for review (requested public): {watch} "
                    "— promote to public after eyeball"
                )
            if is_youtube_scheduled:
                try:
                    from core.win_notify import notify_upload_scheduled

                    notify_upload_scheduled(request.title, video_status.get("publishAt") or "")
                except Exception as exc:
                    logger.debug("scheduled toast skipped: %s", exc)

            _update_publish_log(
                log_id,
                {
                    "status": log_status,
                    "youtube_video_id": video_id,
                    "detail": detail,
                    "privacy_status": (
                        target_privacy if is_youtube_scheduled else effective_privacy
                    ),
                    "published_at": publish_when or datetime.now(timezone.utc),
                },
            )

            result_status = "scheduled" if is_youtube_scheduled else "uploaded"
            base_detail = detail if is_youtube_scheduled else format_quota_detail()
            thumb = maybe_upload_thumbnail(
                service,
                video_id=video_id,
                channel_id=channel_id,
                content_run_id=content_run_id,
                thumbnail_path=request.thumbnail_path,
            )
            if thumb.status == "set":
                detail_suffix = thumb.detail or "Thumbnail set"
                _update_publish_log(
                    log_id,
                    {"detail": f"{base_detail} | {detail_suffix}"[:500]},
                )
            try:
                from core.events import emit_event

                emit_event(
                    "video_published",
                    {
                        "platform": PLATFORM_YOUTUBE,
                        "video_id": video_id,
                        "url": f"https://youtu.be/{video_id}" if video_id else "",
                        "status": result_status,
                        "channel_id": channel_id,
                        "content_run_id": content_run_id,
                        "title": request.title,
                        "scheduled_for": video_status.get("publishAt", "")
                        if is_youtube_scheduled
                        else "",
                    },
                )
            except Exception as exc:
                logger.debug("video_published event not emitted: %s", exc)
            return PublishResult(
                video_id=video_id,
                status=result_status,
                detail=merge_thumbnail_into_upload_detail(base_detail, thumb),
                publish_log_id=log_id,
                thumbnail_status=thumb.status,
                thumbnail_detail=thumb.detail,
                platform=PLATFORM_YOUTUBE,
            )

        except HttpError as e:
            status_code = e.resp.status if e.resp else 0
            st, detail = classify_http(status_code, str(e))
            if "quota" in str(e).lower():
                st = "quota_exceeded"
            _update_publish_log(log_id, {"status": st, "detail": detail[:500]})
            return PublishResult(
                video_id=None,
                status=st,
                detail=detail,
                publish_log_id=log_id or None,
                platform=PLATFORM_YOUTUBE,
            )

        except Exception as e:
            st, detail = classify_exception(e)
            _update_publish_log(log_id, {"status": st, "detail": detail[:500]})
            return PublishResult(
                video_id=None,
                status=st,
                detail=detail,
                publish_log_id=log_id or None,
                platform=PLATFORM_YOUTUBE,
            )
