"""
Process pending jobs from the Content OS queue.

Usage:
    py -m jobs.worker              # one pass
    py -m jobs.worker --loop 30    # poll every 30s
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

from config.channels import resolve_channel_id
from core.logging import get_logger, setup_logging
from core.pipeline import run_media_only
from publishing.base import (
    PLATFORM_YOUTUBE,
    PUBLISH_STATUS_RETRYABLE,
    PUBLISH_STATUS_SUCCESS,
    PUBLISH_STATUS_TERMINAL_FAILURE,
    PublishRequest,
)
from publishing.registry import get_publisher
from storage.repositories.content_runs import get_content_run_repository
from storage.repositories.jobs import (
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_PENDING,
    get_job_repository,
)

UPLOAD_STATUS_SUCCESS = PUBLISH_STATUS_SUCCESS
UPLOAD_STATUS_TERMINAL_FAILURE = PUBLISH_STATUS_TERMINAL_FAILURE
UPLOAD_STATUS_RETRYABLE = PUBLISH_STATUS_RETRYABLE

logger = get_logger("jobs.worker")
setup_logging()


def _defer_for_quota(job, result) -> bool:
    """Keep job pending when upload blocked by daily quota (resets ~midnight Pacific)."""
    if result.status != "quota_exceeded":
        return False
    repo = get_job_repository()

    from apis.youtube_quota import get_usage_summary, next_quota_retry_at

    summary = get_usage_summary()
    retry_at = next_quota_retry_at()
    repo.update(
        job.id,
        {
            "status": JOB_PENDING,
            "last_error": (result.detail or "quota_exceeded")[:500],
            "scheduled_at": retry_at,
            "attempts": max(0, (job.attempts or 1) - 1),
        },
    )
    msg = (
        f"Job {job.id} deferred — YouTube upload quota exhausted "
        f"({summary['remaining']:,} units left; upload needs ~1,600). "
        f"Retry scheduled ~{retry_at.isoformat()[:16]} UTC. "
        f"Or wait for daily reset and run: py -m scripts.requeue_upload --channel tapin --run-id {job.content_run_id} --queue"
    )
    logger.warning(msg)
    print(msg)
    return True


def _finalize_upload_job(job, result) -> None:
    repo = get_job_repository()

    if _defer_for_quota(job, result):
        return

    if result.status in UPLOAD_STATUS_SUCCESS:
        repo.update(job.id, {"status": JOB_COMPLETED, "last_error": result.detail or ""})
        if result.thumbnail_status == "set":
            logger.info("YouTube thumbnail set for job %s", job.id)
        elif result.thumbnail_status == "ineligible":
            logger.warning(
                "Upload job %s: video OK but thumbnail ineligible — %s",
                job.id,
                result.thumbnail_detail or "",
            )
        if job.content_run_id and result.video_id:
            run_status = "scheduled" if result.status == "scheduled" else "published"
            get_content_run_repository().update(job.content_run_id, {"status": run_status})
        return

    if result.status in UPLOAD_STATUS_TERMINAL_FAILURE:
        repo.update(
            job.id,
            {
                "status": JOB_FAILED,
                "last_error": result.detail or result.status,
            },
        )
        detail = result.detail or result.status
        logger.warning("Upload job %s failed (terminal): %s", job.id, detail)
        print(f"Upload job {job.id} failed: {detail}")
        return

    attempts = job.attempts or 0
    max_attempts = job.max_attempts or 3
    if attempts >= max_attempts or result.status not in UPLOAD_STATUS_RETRYABLE:
        repo.update(
            job.id,
            {"status": JOB_FAILED, "last_error": result.detail or result.status},
        )
    else:
        repo.update(
            job.id,
            {"status": JOB_PENDING, "last_error": result.detail or result.status},
        )


def _parse_publish_at(payload: dict):
    raw = payload.get("youtube_publish_at")
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _process_upload(job) -> None:
    payload = json.loads(job.payload_json or "{}")
    channel_id = resolve_channel_id(job.channel_id)

    request = PublishRequest(
        file_path=payload.get("file_path", ""),
        title=payload.get("title", ""),
        description=payload.get("description", ""),
        tags=payload.get("tags"),
        privacy_status=payload.get("privacy_status", "private"),
        publish_at=_parse_publish_at(payload),
        thumbnail_path=payload.get("thumbnail_path"),
    )
    from publishing.youtube_publisher import YouTubePublisher

    publisher = get_publisher(PLATFORM_YOUTUBE) or YouTubePublisher()
    result = publisher.publish(
        request,
        channel_id=channel_id,
        content_run_id=job.content_run_id,
    )
    _finalize_upload_job(job, result)


def _process_render(job) -> None:
    repo = get_job_repository()
    payload = json.loads(job.payload_json or "{}")
    topic = payload.get("topic", "")
    script = payload.get("script", "")
    channel_id = resolve_channel_id(job.channel_id)

    try:
        mp3_path, mp4_path, _thumb = run_media_only(
            topic,
            script,
            channel_id=channel_id,
            content_run_id=job.content_run_id,
        )
        repo.update(
            job.id,
            {
                "status": JOB_COMPLETED,
                "payload_json": json.dumps({**payload, "mp3_path": mp3_path, "mp4_path": mp4_path}),
            },
        )
    except Exception as e:
        attempts = job.attempts or 0
        max_attempts = job.max_attempts or 3
        status = JOB_FAILED if attempts >= max_attempts else JOB_PENDING
        repo.update(job.id, {"status": status, "last_error": str(e)[:500]})


_HANDLERS = {
    "upload": _process_upload,
    "render": _process_render,
}


def _reclaim_stuck_jobs() -> int:
    try:
        minutes = int(os.getenv("JOB_STUCK_MINUTES", "45"))
    except ValueError:
        minutes = 45
    return get_job_repository().reclaim_stuck_running(minutes)


def process_one() -> bool:
    from apis.youtube_quota import has_quota_for_upload

    repo = get_job_repository()
    reclaimed = _reclaim_stuck_jobs()
    if reclaimed:
        logger.warning("Reclaimed %s stuck running job(s)", reclaimed)

    job = repo.claim_next() if has_quota_for_upload() else repo.claim_next(job_type="render")

    if not job:
        return False

    handler = _HANDLERS.get(job.job_type)
    if not handler:
        repo.update(
            job.id,
            {"status": JOB_FAILED, "last_error": f"Unknown job_type: {job.job_type}"},
        )
        return True

    logger.info("Processing job %s (%s)", job.id, job.job_type)
    try:
        handler(job)
    except Exception as e:
        logger.exception("Job %s failed: %s", job.id, e)
        repo.update(job.id, {"status": JOB_FAILED, "last_error": str(e)[:500]})
    return True


def main():
    parser = argparse.ArgumentParser(description="Content OS job worker")
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        help="Poll interval in seconds (0 = single pass)",
    )
    args = parser.parse_args()

    if args.loop <= 0:
        processed = process_one()
        if not processed:
            from apis.youtube_quota import format_quota_detail, has_quota_for_upload

            print("No pending jobs.")
            if not has_quota_for_upload():
                print(
                    f"YouTube upload blocked today — {format_quota_detail()}. "
                    "Uploads need ~1,600 units. Wait for daily quota reset (midnight Pacific) "
                    "then: py -m scripts.requeue_upload --channel tapin --run-id ID --queue"
                )
        return

    from apis.youtube_quota import format_quota_detail, has_quota_for_upload

    print(f"Worker polling every {args.loop}s (Ctrl+C to stop)")
    while True:
        did_work = False
        while process_one():
            did_work = True
        if not did_work and not has_quota_for_upload():
            print(
                f"Waiting for YouTube quota reset — {format_quota_detail()}. "
                "Upload jobs deferred until scheduled_at passes."
            )
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
