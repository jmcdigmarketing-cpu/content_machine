"""
YouTube upload — OAuth, resumable videos.insert, idempotent publish_log.
"""

from __future__ import annotations

import json
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


def _dry_run_enabled() -> bool:
    return os.getenv("PUBLISH_DRY_RUN", "").strip().lower() in ("1", "true", "yes", "on")


def dry_run_insert_body(request: PublishRequest, *, channel_id: str) -> dict[str, Any]:
    """The videos.insert `body` that publish() would send. Never calls insert."""
    snippet = {
        "title": (request.title or "")[:100],
        "description": (request.description or "")[:5000],
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
    if not snippet.get("categoryId"):
        snippet["categoryId"] = "20"
    # Reuse the real status builder rather than restating it: it carries the #107
    # `selfDeclaredMadeForKids` declaration and the #115/#116 `publishAt` bump, and
    # those are exactly the fields an operator opens a dry run to check. `_window_reason`
    # is internal bookkeeping publish() pops before sending, so it is not part of the body.
    try:
        status = build_video_status(request, channel_id=channel_id)
        status.pop("_window_reason", None)
    except Exception as exc:
        logger.debug("dry-run status defaults skipped: %s", exc)
        status = {"privacyStatus": request.privacy_status or "private"}
    return {"snippet": snippet, "status": status}


def redact_publish_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop token/secret values from a payload copy (never print credentials)."""
    redacted = json.loads(json.dumps(payload, default=str))

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, val in list(obj.items()):
                low = str(key).lower()
                if any(
                    tok in low for tok in ("token", "secret", "authorization", "api_key", "apikey")
                ):
                    obj[key] = "[redacted]"
                else:
                    walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(redacted)
    return redacted


def _post_upload_extras(service, video_id: str | None, request: PublishRequest) -> None:
    """Caption track + opt-in comment. Fail-open; never blocks the publish result."""
    if not service or not video_id:
        return
    try:
        from youtube.captions import maybe_upload_captions, resolve_caption_path

        maybe_upload_captions(
            service,
            video_id=video_id,
            caption_path=resolve_caption_path(request.file_path, request.caption_path),
        )
    except Exception as exc:
        logger.debug("caption track skipped: %s", exc)
    try:
        from youtube.pin_comment import maybe_pin_top_answer

        maybe_pin_top_answer(service, video_id=video_id, topic=request.title)
    except Exception as exc:
        logger.debug("pin comment skipped: %s", exc)


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


def queued_privacy_label(privacy_status: str, publish_at=None) -> str:
    """What the operator should be told at queue time, not what they asked for.

    The queue confirmation used to echo the requested privacy, so an immediate
    public upload printed "public" and then landed unlisted because the review
    hold is on by default (live run 69). Routed through apply_unlisted_review so
    the message and the upload cannot drift apart.
    """
    effective, held = apply_unlisted_review(privacy_status, publish_at=publish_at)
    if not held:
        return effective
    return f"{privacy_status} -> {effective} first, for review"


def build_video_status(request: PublishRequest, *, channel_id: str | None = None) -> dict[str, Any]:
    status: dict[str, Any] = {"selfDeclaredMadeForKids": False}
    publish_at = request.publish_at
    try:
        from core.publish_windows import adjust_publish_at

        domain = ""
        try:
            from apis.topic_scorer import infer_domain

            domain = infer_domain(request.title or "", channel_id)
        except Exception as exc:
            logger.debug("publish window domain skipped: %s", exc)
            domain = ""
        bumped, why = adjust_publish_at(
            publish_at,
            channel_id=channel_id,
            topic=request.title or "",
            domain=domain,
            privacy=request.privacy_status,
        )
        if why and bumped:
            logger.warning("publish window: %s - scheduling %s", why, bumped.isoformat())
            try:
                print(f"  Publish window: {why}; going public at {bumped.isoformat()}")
            except Exception as print_exc:
                logger.debug("publish window operator print skipped: %s", print_exc)
            publish_at = bumped
            status["_window_reason"] = why
    except Exception as exc:
        logger.warning("publish window check failed (uploading anyway): %s", exc)
        try:
            print(f"  Publish window check failed (uploading anyway): {exc}")
        except Exception as print_exc:
            logger.debug("publish window operator print skipped: %s", print_exc)
        publish_at = request.publish_at

    if not publish_at:
        privacy, _held = apply_unlisted_review(request.privacy_status)
        status["privacyStatus"] = privacy
        try:
            from core.youtube_meta import audit_made_for_kids

            status = audit_made_for_kids(status)
        except Exception as exc:
            logger.debug("madeForKids audit skipped: %s", exc)
            status["selfDeclaredMadeForKids"] = False
        return status

    publish_at = _to_utc(publish_at)
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
            _post_upload_extras(service, existing.youtube_video_id, request)
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
    _post_upload_extras(service, video_id, request)
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

        if os.path.splitext(request.file_path)[0].lower().endswith("_preview"):
            return PublishResult(
                video_id=None,
                status="blocked",
                detail="Draft preview files are review-only and cannot be uploaded",
                platform=PLATFORM_YOUTUBE,
            )

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

        try:
            from core.shorts_eligibility import shorts_refuse_reason

            refuse = shorts_refuse_reason(file_path=request.file_path, title=request.title)
            if refuse:
                return PublishResult(
                    video_id=None,
                    status="blocked",
                    detail=refuse,
                    platform=PLATFORM_YOUTUBE,
                )
        except Exception as exc:
            logger.debug("shorts eligibility skipped: %s", exc)

        if _dry_run_enabled():
            body = redact_publish_payload(dry_run_insert_body(request, channel_id=channel_id))
            return PublishResult(
                video_id=None,
                status="dry_run",
                detail=json.dumps(body, indent=2),
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
            from core.cross_channel_dup import cross_channel_dup_block_reason

            lens_hit = cross_channel_dup_block_reason(
                request.title, channel_id, exclude_run_id=content_run_id
            )
            if lens_hit:
                logger.warning("%s", lens_hit)
                return PublishResult(
                    video_id=None,
                    status="blocked",
                    detail=lens_hit,
                    platform=PLATFORM_YOUTUBE,
                )
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

        video_status = build_video_status(request, channel_id=channel_id)
        window_why = video_status.pop("_window_reason", None)
        is_youtube_scheduled = "publishAt" in video_status
        held_at = request.publish_at
        if not held_at and is_youtube_scheduled:
            held_at = datetime.now(timezone.utc)
        effective_privacy, held_review = apply_unlisted_review(
            request.privacy_status, publish_at=held_at
        )
        target_privacy = request.privacy_status

        snippet = dry_run_insert_body(request, channel_id=channel_id)["snippet"]
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

            if video_id:
                try:
                    from core.operator_minutes import record_publish_minutes
                    from core.operator_timer import snapshot

                    snap = snapshot()
                    minutes = (snap["wall_s"] / 60.0) if snap else 0.0
                    record_publish_minutes(channel_id, minutes)
                except Exception as exc:
                    logger.debug("operator minutes skipped: %s", exc)

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
            if window_why and is_youtube_scheduled:
                detail = f"{detail} [window: {window_why}]"
            if held_review and video_id:
                watch = f"https://www.youtube.com/watch?v={video_id}"
                detail = (
                    f"Unlisted for review (requested public): {watch} "
                    "- promote to public after eyeball"
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
            _post_upload_extras(service, video_id, request)
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
            try:
                from core.topic_graph import record_published_topic
                from storage.repositories.content_runs import get_content_run_repository

                seed = request.title
                if content_run_id:
                    run = get_content_run_repository().get(content_run_id)
                    if run is not None:
                        seed = run.input_topic or run.selected_topic or request.title
                record_published_topic(channel_id, seed)
            except Exception as exc:
                logger.debug("topic graph record skipped: %s", exc)
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
