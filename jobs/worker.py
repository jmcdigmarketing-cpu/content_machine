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
from typing import Any

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
    from analytics.post_timing import format_scheduled_local

    msg = (
        f"Job {job.id} deferred — YouTube upload quota exhausted "
        f"({summary['remaining']:,} units left; upload needs ~1,600). "
        f"It goes after the reset, {format_scheduled_local(retry_at, job.channel_id or 'tapin')}"
        " - nothing to do (#1526)"
    )
    logger.warning(msg)
    print(msg)
    return True


SIGN_IN_HOLD = "held - the YouTube sign-in has ended"
_SIGN_IN_RETRY_MINUTES = 15  # the UploadWorker task's pass
_SLOT_LEAD_MINUTES = 15  # youtube_publisher's YOUTUBE_PUBLISH_MIN_LEAD_MINUTES


def _hold_for_sign_in(job, result) -> bool:
    """#1439 (wave 116): an ended sign-in holds the upload; it does not fail it. `auth_error` was
    terminal, so the Testing-mode lapse (Wed 10-21 9:36 PM EDT) would have failed every queued
    upload for a requeue by hand - and a refresh that failed on the network did the same. The
    job waits for the next pass with its attempt given back; one toast a day says why."""
    if result.status != "auth_error":
        return False
    from datetime import timedelta

    from youtube.oauth import short_sign_in

    channel = resolve_channel_id(job.channel_id)
    note = short_sign_in(channel)
    get_job_repository().update(
        job.id,
        {
            "status": JOB_PENDING,
            "last_error": f"{SIGN_IN_HOLD}: {note}"[:500],
            "scheduled_at": datetime.now(timezone.utc) + timedelta(minutes=_SIGN_IN_RETRY_MINUTES),
            "attempts": max(0, (job.attempts or 1) - 1),
        },
    )
    print(
        f"Upload job {job.id} (run {job.content_run_id}) {SIGN_IN_HOLD} - it goes on the "
        "first pass after you sign in again"
    )
    try:
        from core.win_notify import toast_daily

        toast_daily(f"signin:{channel}", "Content OS: YouTube sign-in", note[:180])
    except Exception as exc:
        logger.debug("sign-in toast skipped: %s", exc)
    return True


def _reslot_after_hold(job, payload: dict, channel_id: str) -> dict:
    """#1439 (the operator: the next free slot): an upload held through an ended sign-in whose
    slot has passed goes public at the next free slot, not minutes after it uploads - which could
    land it on another video. A quota hold keeps today's rule. The new slot is stored."""
    from datetime import timedelta

    publish_at = _parse_publish_at(payload)
    if publish_at is None or SIGN_IN_HOLD not in (job.last_error or ""):
        return payload
    if publish_at > datetime.now(timezone.utc) + timedelta(minutes=_SLOT_LEAD_MINUTES):
        return payload
    try:
        from core.spaced_queue import free_slots

        slots = free_slots(channel_id, 1)
    except Exception as exc:
        logger.warning("next free slot unread for job %s: %s", job.id, exc)
        return payload
    if not slots:
        return payload
    moved = {**payload, "youtube_publish_at": slots[0].isoformat()}
    try:
        get_job_repository().update(job.id, {"payload_json": json.dumps(moved)})
    except Exception as exc:
        logger.debug("re-slot not stored for job %s: %s", job.id, exc)
    print(
        f"Upload job {job.id}: its slot passed while signed out - now {slots[0].isoformat()[:16]}Z"
    )
    return moved


def _toast_public(videos: list[tuple[str, str]]) -> None:
    """#1404 (wave 117): a toast with the watch link when a video goes public, once per video -
    run 173 went public at 6 PM EDT on 10-20 and nothing said so. Fail-open."""
    try:
        from core.win_notify import toast_daily

        for video_id, title in videos:
            if video_id:
                body = f"{(title or 'A video')[:90]} - https://youtu.be/{video_id}"
                toast_daily(f"public:{video_id}", "Content OS: now public", body)
    except Exception as exc:
        logger.debug("public toast skipped: %s", exc)


def _titled(rows: list, video_ids: list[str]) -> list[tuple[str, str]]:
    """(video id, title) for the publish-log rows of the given videos."""
    from storage.repositories.publish_log import video_title

    by_id = {str(getattr(r, "youtube_video_id", "") or ""): r for r in rows}
    return [(vid, video_title(by_id[vid]) if vid in by_id else "") for vid in video_ids if vid]


def _crosspost_after_upload(job) -> None:
    """#1202 (operator, 2026-10-15: "right away"): an upload that went out public is sent to
    TikTok and Instagram now - the same round `go-public --apply` starts. A video still unlisted
    or scheduled is not public, and the round leaves it."""
    try:
        from publishing.crosspost import step

        for line in step(resolve_channel_id(job.channel_id)):
            print(line)
    except Exception as exc:
        logger.warning("crosspost after upload %s skipped: %s", job.id, exc)


def send_queued_uploads(limit: int) -> int:
    """#1203: send up to `limit` queued uploads now - uploads only, never a render. Returns how
    many were tried."""
    from apis.youtube_quota import has_quota_for_upload

    repo = get_job_repository()
    tried = 0
    while tried < limit and has_quota_for_upload():
        job = repo.claim_next(job_type="upload")
        if not job:
            break
        tried += 1
        try:
            _process_upload(job)
        except Exception as e:
            logger.exception("Upload job %s failed: %s", job.id, e)
            repo.update(job.id, {"status": JOB_FAILED, "last_error": str(e)[:500]})
    return tried


def _finalize_upload_job(job, result) -> None:
    repo = get_job_repository()

    if _defer_for_quota(job, result):
        return
    if _hold_for_sign_in(job, result):  # #1439
        return

    if result.status in UPLOAD_STATUS_SUCCESS:
        repo.update(job.id, {"status": JOB_COMPLETED, "last_error": result.detail or ""})
        # Run 77: the upload went through with nothing on the console (INFO log only).
        link = f" -> https://youtu.be/{result.video_id}" if result.video_id else ""
        print(f"Job {job.id} {result.status}{link}")
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
        if result.status == "uploaded":
            _crosspost_after_upload(job)
            try:  # never a reason the upload's record is not finished
                payload = json.loads(getattr(job, "payload_json", "") or "{}")
                # #1404: an overnight render goes up unlisted - only a public one is announced.
                if result.video_id and str(payload.get("privacy_status") or "") == "public":
                    _toast_public([(str(result.video_id), str(payload.get("title") or ""))])
            except (TypeError, ValueError, AttributeError) as exc:
                logger.debug("public toast skipped for job %s: %s", job.id, exc)
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


def _after_its_game(job, channel_id: str) -> bool:
    """#1547 (2026-10-23): run 181, the Cavaliers-76ers "Opening Tip" preview, was held through
    the lapsed sign-in past its 7 PM EDT tip-off; after the sign-in it would have uploaded (1,600
    units) and waited unlisted for a game already played. A preview whose game has started is
    taken off the queue before any call - the file stays, and `requeue_upload --run-id N
    --queue` still takes it by id."""
    if not job.content_run_id:
        return False
    try:
        from core.batch_review import _zone_clock
        from core.stale_renders import started_event

        run = get_content_run_repository().get(int(job.content_run_id))
        when = started_event(run, channel_id)
        if when is None:
            return False
        note = (
            f"its game started {_zone_clock(when, channel_id, day=True)} - nothing uploads it "
            "(the file stays)"
        )
    except Exception as exc:
        logger.debug("game check skipped for job %s: %s", job.id, exc)
        return False
    get_job_repository().update(job.id, {"status": JOB_FAILED, "last_error": note[:500]})
    print(f"Upload job {job.id} (run {job.content_run_id}) taken off the queue: {note}")
    return True


def _before_its_event(job, payload: dict, channel_id: str) -> dict:
    """#1552 (2026-10-23): run 184, a UFC 333 preview, was queued for Sun noon - the day after the
    card - because its title named the card by number and matched no event (#1551). A job whose
    publish time is at or after its event's start takes `slot_for_run`'s slot: before the event,
    or as it uploads when none is left. The new slot is stored."""
    publish_at = _parse_publish_at(payload)
    if publish_at is None or not job.content_run_id:
        return payload
    try:
        from core.spaced_queue import slot_for_run
        from core.stale_renders import render_age_days, run_event

        run = get_content_run_repository().get(int(job.content_run_id))
        event = run_event(run, channel_id, render_age_days(run)) if run is not None else None
        if event is None or publish_at < event:
            return payload
        title = str(getattr(run, "title", "") or "")
        when, why = slot_for_run(channel_id, int(job.content_run_id), title=title)
    except Exception as exc:
        logger.debug("event check skipped for job %s: %s", job.id, exc)
        return payload
    if when is None:
        print(
            f"Upload job {job.id} (run {job.content_run_id}): its slot is after its event and {why}"
        )
        return payload
    moved = {**payload, "youtube_publish_at": when.isoformat()}
    try:
        get_job_repository().update(job.id, {"payload_json": json.dumps(moved)})
    except Exception as exc:
        logger.debug("new slot not stored for job %s: %s", job.id, exc)
    from analytics.post_timing import format_scheduled_local

    print(
        f"Upload job {job.id} (run {job.content_run_id}): its slot was after its event - moved "
        f"before its event, to {format_scheduled_local(when, channel_id)}"
    )
    return moved


def _process_upload(job) -> None:
    payload = json.loads(job.payload_json or "{}")
    channel_id = resolve_channel_id(job.channel_id)
    if _after_its_game(job, channel_id):
        return

    try:
        from core.rpm_cost_gate import next_retry_utc, rpm_cost_gate_reason

        rpm_blocked = rpm_cost_gate_reason(channel_id)
    except Exception as exc:
        logger.debug("rpm-cost check skipped: %s", exc)
        rpm_blocked = None
    if rpm_blocked:
        repo = get_job_repository()
        retry_at = next_retry_utc()
        repo.update(
            job.id,
            {
                "status": JOB_PENDING,
                "last_error": rpm_blocked[:500],
                "scheduled_at": retry_at,
                "attempts": max(0, (job.attempts or 1) - 1),
            },
        )
        logger.warning("Upload job %s deferred: %s", job.id, rpm_blocked)
        print(rpm_blocked)
        return

    payload = _before_its_event(job, payload, channel_id)  # #1552
    payload = _reslot_after_hold(job, payload, channel_id)  # #1439
    request = PublishRequest(
        file_path=payload.get("file_path", ""),
        title=payload.get("title", ""),
        description=payload.get("description", ""),
        tags=payload.get("tags"),
        privacy_status=payload.get("privacy_status", "private"),
        publish_at=_parse_publish_at(payload),
        thumbnail_path=payload.get("thumbnail_path"),
        caption_path=payload.get("caption_path")
        or (
            os.path.splitext(payload.get("file_path", "") or "")[0] + ".srt"
            if payload.get("file_path")
            else None
        ),
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

    blocked = None
    try:
        from core.render_gate import block_reason_for_run

        blocked = block_reason_for_run(job.content_run_id)
    except Exception as exc:
        logger.debug("render-gate check skipped: %s", exc)
        blocked = None
    if blocked:
        repo.update(job.id, {"status": JOB_FAILED, "last_error": blocked[:500]})
        logger.warning("Render job %s skipped: %s", job.id, blocked)
        print(blocked)
        return

    try:
        from core.human_presence import unattended_render_block_reason as human_block

        blocked = human_block()
    except Exception as exc:
        logger.debug("human-presence check skipped: %s", exc)
        blocked = None
    if blocked:
        repo.update(job.id, {"status": JOB_FAILED, "last_error": blocked[:500]})
        logger.warning("Render job %s skipped: %s", job.id, blocked)
        print(blocked)
        return

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


_LOCK_HANDLE: Any = None


def _lock_path() -> str:
    raw = (os.getenv("WORKER_LOCK_FILE") or "").strip()
    if raw:
        return raw
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, "worker.lock")


def _try_lock(path: str) -> Any:
    """An open handle holding an exclusive lock on `path`, or None when another process holds
    it. The OS frees the lock when its process dies - a crash included (#1284)."""
    import sys

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    handle = open(path, "a+")  # noqa: SIM115 - held for the life of the worker
    try:
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _release_lock(handle: Any) -> None:
    import sys

    try:
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    handle.close()


def _sole_worker() -> bool:
    """True while this process holds the worker lock - no other worker is alive."""
    global _LOCK_HANDLE
    if _LOCK_HANDLE is None:
        try:
            _LOCK_HANDLE = _try_lock(_lock_path())
        except OSError as exc:
            logger.debug("worker lock unavailable: %s", exc)
            return False
    return _LOCK_HANDLE is not None


def _reclaim_stuck_jobs() -> int:
    """#1284 (job 61 sat "running" after an interrupted worker): alone, a worker frees every
    running job at once - whoever claimed it is gone. Beside a live worker the 45 minutes
    (`JOB_STUCK_MINUTES`) stand."""
    if _sole_worker():
        return get_job_repository().reclaim_stuck_running(0)
    try:
        minutes = int(os.getenv("JOB_STUCK_MINUTES", "45") or 45)
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


# #1230: how many jobs one pass may take - enough for a day's uploads, never a spin.
PASS_CAP = 10


def _post_due_pins() -> None:
    """Post a pin comment whose peak has passed. A missing file does not build a YouTube client."""
    try:
        from datetime import datetime, timezone

        from youtube.oauth import get_youtube_service
        from youtube.pin_comment import due_channels, post_due

        channels = due_channels()
        if not channels:
            return
        for channel_id in channels:
            service = get_youtube_service(channel_id)
            if service is None:
                logger.debug("pin comment due but YouTube is not configured for %s", channel_id)
                continue
            post_due(service, now=datetime.now(timezone.utc), channel_id=channel_id)
    except Exception as exc:
        logger.debug("due pin comments skipped: %s", exc)


def _crosspost_channels() -> list[str]:
    """Channels whose videos go to TikTok and Instagram through Buffer."""
    from config.channels import get_channel_profiles
    from publishing import buffer_api, crosspost

    if not crosspost.auto_enabled() or not buffer_api.configured():
        return []
    return [cid for cid in get_channel_profiles() if crosspost.buffer_channel_ids(cid)]


_LIVE_LOOKBACK_DAYS = 3


def _crosspost_scheduled_live(now: datetime | None = None) -> int:
    """Wave 105: a scheduled upload turns public at its slot on YouTube, and the publish log
    learned it in the morning sync - so Buffer waited until then. Each pass: when a private row's
    time has passed, its privacy is read back (1 unit per 50 videos) and the crosspost round
    runs for a channel where one turned public. Returns how many rounds ran."""
    from datetime import timedelta

    moment = now or datetime.now(timezone.utc)
    rounds = 0
    try:
        from publishing import crosspost
        from storage.repositories.publish_log import get_publish_log_repository

        for channel_id in _crosspost_channels():
            rows = get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
            posts = crosspost._load(channel_id).get("posts") or {}
            private, public = [], []
            for row in rows:
                when = getattr(row, "published_at", None)
                privacy = str(getattr(row, "privacy_status", "") or "").lower()
                if not when or privacy not in ("private", "public"):
                    continue
                when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
                if not moment - timedelta(days=_LIVE_LOOKBACK_DAYS) <= when <= moment:
                    continue
                if privacy == "private":
                    private.append(row)
                # #1299: the uploader logs a scheduled video with the privacy it goes public
                # with, so its slot passing is the signal - unless the round has it already.
                elif str(getattr(row, "status", "") or "") == "scheduled" and not posts.get(
                    str(getattr(row, "content_run_id", "") or "")
                ):
                    public.append(row)
            if not private and not public:
                continue
            if not public:
                from analytics.privacy_sync import sync_privacy

                report = sync_privacy(channel_id)
                changed = report.get("changed") or []
                went = [str(c.get("video_id") or "") for c in changed if c.get("now") == "public"]
                if not went:
                    continue
            else:
                went = [str(getattr(r, "youtube_video_id", "") or "") for r in public]
            _toast_public(_titled(rows, went))  # #1404
            from publishing.crosspost import step

            for line in step(channel_id):
                print(line)
            rounds += 1
    except Exception as exc:
        logger.debug("scheduled-live crosspost skipped: %s", exc)
    return rounds


def drain_due(cap: int = PASS_CAP) -> int:
    """Every job that is due, in one pass. 2026-10-16: `ops worker` uploaded job 58 and stopped;
    job 59 (run 155), due since 5:10 PM, stayed pending. Each job keeps its own scheduled time
    and the quota check in `process_one`."""
    _post_due_pins()
    _crosspost_scheduled_live()
    done = 0
    while done < cap and process_one():
        done += 1
    return done


def _overnight_watch() -> None:
    """#1372: a toast, once a day, when overnight has not started for 26 hours. Fail-open."""
    try:
        from core.nightly_task import keep_crash_log, overdue_line
        from core.win_notify import toast_daily

        line = overdue_line()
        if line:
            toast_daily("overnight-missed", "Content OS: overnight", line)
        kept = keep_crash_log()  # #1466: before the next 5:00 empties the log
        if kept:
            print(f"Overnight never finished - its log is kept: {kept}")
    except Exception as exc:
        logger.debug("overnight watch skipped: %s", exc)


def _sign_in_watch(now: datetime | None = None) -> None:
    """#1438 (wave 116): a toast, once a day, from 24 hours before a Testing-mode sign-in lapses
    - the morning line says the date, but nobody reads it on the day. Quiet once the app is
    published (the expiry line is then ""). Fail-open."""
    from datetime import timedelta

    try:
        from config.channels import active_channel_ids
        from core.win_notify import toast_daily
        from youtube.oauth import sign_in_expiry, sign_in_expiry_line, token_path_for_channel

        moment = now or datetime.now(timezone.utc)
        for channel in active_channel_ids():
            if not os.path.isfile(token_path_for_channel(channel)):
                continue
            line = sign_in_expiry_line(channel, now=moment)
            when = sign_in_expiry(channel)
            if line and when is not None and when - moment <= timedelta(hours=24):
                toast_daily(
                    f"signin-soon:{channel}",
                    "Content OS: YouTube sign-in",
                    f"The {channel} sign-in {line} - ops check-youtube has the link",
                )
    except Exception as exc:
        logger.debug("sign-in watch skipped: %s", exc)


_TONIGHT_HOUR = 20  # the operator: one toast at 8 PM


def _tonight_watch(now: datetime | None = None) -> None:
    """#1337 (wave 117, the operator: an 8 PM toast): from 8 PM, once a day, what overnight will
    do. Decision 69 (2026-10-23, power-on is fine): it no longer asks for Sleep. Fail-open."""
    moment = now or datetime.now()
    if moment.hour < _TONIGHT_HOUR:
        return
    try:
        from config.channels import active_channel_ids
        from core.nightly_task import tonight_line
        from core.win_notify import toast_daily

        channels = [c for c in active_channel_ids() if c != "default"] or ["tapin"]
        line = tonight_line(channels[0])
        if line:
            toast_daily("overnight-tonight", "Content OS: overnight", line, now=moment)
    except Exception as exc:
        logger.debug("tonight watch skipped: %s", exc)


def _sync_metrics() -> None:
    """Wave 113: the metrics sync, once a day - `ops morning` was its only caller, and this
    pass runs every 15 minutes from the UploadWorker task. Fail-open."""
    try:
        from analytics.sync_metrics import maybe_sync
        from config.channels import active_channel_ids
        from youtube.constants import SCOPE_YT_ANALYTICS_READONLY
        from youtube.oauth import _scopes_from_token_file, token_path_for_channel

        for channel in active_channel_ids():
            # #1518: the generic "default" channel has no sign-in; it printed "OAuth token
            # missing" and was retried every 2 hours for nothing. #1523 (10-19 16:52): it has a
            # sign-in file, for uploads only - "Token missing yt-analytics.readonly". The sync
            # needs the analytics permission, read from the file (no refresh, no network).
            path = token_path_for_channel(channel)
            if os.path.isfile(path) and SCOPE_YT_ANALYTICS_READONLY in _scopes_from_token_file(
                path
            ):
                maybe_sync(channel)
    except Exception as exc:
        logger.debug("worker metrics sync skipped: %s", exc)


def _idle_line() -> str:
    """What a pass that sent nothing says. #1526 (wave 116): with job 74 held by the quota it
    printed "No pending jobs." and a requeue command - the job was queued and went by itself
    after the reset."""
    from apis.youtube_quota import format_quota_detail, has_quota_for_upload

    if has_quota_for_upload():
        return "No pending jobs."
    from core.job_queue import quota_held_line, quota_wait

    try:
        jobs = list(get_job_repository().list_active_jobs() or [])
    except Exception as exc:
        logger.debug("held uploads unread: %s", exc)
        jobs = []
    pending = [j for j in jobs if j.job_type == "upload" and j.status == JOB_PENDING]
    reset = quota_wait(resolve_channel_id(pending[0].channel_id if pending else None))
    held = quota_held_line(jobs, reset)
    if held:
        return held
    return (
        f"No pending jobs. YouTube upload blocked today — {format_quota_detail()}; "
        f"the quota resets {reset or 'at midnight Pacific'}."
    )


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
        processed = drain_due()
        _sync_metrics()
        _overnight_watch()
        _sign_in_watch()  # #1438
        _tonight_watch()  # #1337
        if processed > 1:
            print(f"Sent {processed} due job(s) in one pass.")
        if not processed:
            print(_idle_line())
        return

    from apis.youtube_quota import format_quota_detail, has_quota_for_upload

    print(f"Worker polling every {args.loop}s (Ctrl+C to stop)")
    try:
        while True:
            did_work = False
            while process_one():
                did_work = True
            _sync_metrics()
            _overnight_watch()
            _sign_in_watch()
            _tonight_watch()
            if not did_work and not has_quota_for_upload():
                print(
                    f"Waiting for YouTube quota reset — {format_quota_detail()}. "
                    "Upload jobs deferred until scheduled_at passes."
                )
            time.sleep(args.loop)
    except KeyboardInterrupt:
        # Run 78: Ctrl+C is the documented way to stop the loop, not a crash.
        print("\nWorker stopped.")


if __name__ == "__main__":
    from core.console_encoding import ensure_utf8_stdout

    ensure_utf8_stdout()  # #767: redirected / scheduled runs are cp1252
    main()
