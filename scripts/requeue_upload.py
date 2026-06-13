"""
List rendered videos not yet on YouTube, and optionally queue upload jobs.

Usage:
    py -m scripts.requeue_upload --channel tapin
    py -m scripts.requeue_upload --channel tapin --run-id 4
    py -m scripts.requeue_upload --channel tapin --run-id 4 --queue
"""

from __future__ import annotations

import argparse
import json
import os

from config.channels import resolve_channel_id
from storage.repositories.content_runs import get_content_run_repository
from storage.repositories.jobs import enqueue_upload_job
from storage.repositories.publish_log import get_publish_log_repository

_DONE_STATUSES = frozenset({"uploaded", "scheduled"})


def _publish_rows_for_run(run_id: int, channel_id: str) -> list:
    repo = get_publish_log_repository()
    primary = repo._primary() if hasattr(repo, "_primary") else repo
    if hasattr(primary, "_read"):
        return [
            r
            for r in primary._read()
            if int(r.get("content_run_id", 0)) == run_id and r.get("channel_id") == channel_id
        ]
    matches = []
    for row in repo.list_uploaded_for_channel(channel_id):
        if row.content_run_id == run_id:
            matches.append({"status": row.status, "youtube_video_id": row.youtube_video_id})
    for row in repo.list_future_scheduled(channel_id):
        if row.content_run_id == run_id:
            matches.append({"status": row.status, "youtube_video_id": row.youtube_video_id})
    return matches


def _is_uploaded(run_id: int, channel_id: str) -> bool:
    for row in _publish_rows_for_run(run_id, channel_id):
        status = str(row.get("status", ""))
        vid = str(row.get("youtube_video_id", ""))
        if status in _DONE_STATUSES:
            return True
        if vid and not vid.startswith("seed_"):
            return True
    return False


def _resolve_mp4_path(run) -> str:
    path = (run.mp4_path or "").strip()
    if path and os.path.isfile(path):
        return path
    return ""


def list_recyclable(channel_id: str):
    channel_id = resolve_channel_id(channel_id)
    repo = get_content_run_repository()
    runs = repo.list_for_channel(channel_id)
    recyclable = []
    for run in runs:
        if run.status not in ("rendered", "drafted"):
            continue
        mp4 = _resolve_mp4_path(run)
        if not mp4:
            continue
        if _is_uploaded(run.id, channel_id):
            continue
        recyclable.append(run)
    return recyclable


def _print_channel_runs(channel_id: str) -> None:
    runs = get_content_run_repository().list_for_channel(channel_id)
    if not runs:
        print(f"  (no runs in database for channel '{channel_id}')")
        return
    for run in runs:
        mp4 = _resolve_mp4_path(run)
        flag = "MP4" if mp4 else "no file"
        print(f"  [{run.id}] {run.status:8} {flag:7}  " f"{(run.title or run.selected_topic)[:50]}")
        if mp4:
            print(f"         {mp4}")


def _lookup_run(run_id: int, channel_id: str, *, any_channel: bool):
    repo = get_content_run_repository()
    run = repo.get(run_id)
    if not run:
        return None, f"Run {run_id} does not exist in the database."

    if run.channel_id != channel_id and not any_channel:
        return (
            None,
            f"Run {run_id} belongs to channel '{run.channel_id}', not '{channel_id}'. "
            f"Use: --channel {run.channel_id}",
        )
    return run, None


def reset_failed_quota_jobs(channel_id: str) -> int:
    """Reset upload jobs that failed only due to quota (so worker can retry)."""

    from sqlalchemy import select

    from apis.youtube_quota import format_quota_detail, has_quota_for_upload, next_quota_retry_at
    from storage.db import get_session
    from storage.models import Job
    from storage.repositories.jobs import JOB_FAILED, JOB_PENDING

    channel_id = resolve_channel_id(channel_id)
    when = next_quota_retry_at()
    session = get_session()
    count = 0
    try:
        rows = session.scalars(
            select(Job).where(
                Job.channel_id == channel_id,
                Job.job_type == "upload",
                Job.status == JOB_FAILED,
            )
        ).all()
        for row in rows:
            if not row.last_error or "quota" not in row.last_error.lower():
                continue
            row.status = JOB_PENDING
            row.attempts = 0
            row.last_error = ""
            row.scheduled_at = when
            count += 1
        if count:
            session.commit()
    finally:
        session.close()
    if count and not has_quota_for_upload():
        print(f"Quota still low — {format_quota_detail()}")
        print(
            f"Jobs will not run until ~{when.isoformat()[:16]} UTC "
            "(after daily reset). Keep worker running or retry tomorrow."
        )
    return count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="List or re-queue rendered MP4s that were never uploaded"
    )
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--run-id", type=int, help="Inspect or queue a specific content run")
    parser.add_argument(
        "--any-channel",
        action="store_true",
        help="Allow --run-id lookup even if channel differs",
    )
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Enqueue upload job (use with --run-id)",
    )
    parser.add_argument(
        "--retry-failed-quota",
        action="store_true",
        help="Reset failed upload jobs that hit YouTube quota (run after daily reset)",
    )
    args = parser.parse_args(argv)

    channel_id = resolve_channel_id(args.channel)

    if args.retry_failed_quota:
        n = reset_failed_quota_jobs(channel_id)
        print(f"Reset {n} quota-failed upload job(s) to pending for '{channel_id}'.")
        print("Run: py -m jobs.worker --loop 30")
        return 0

    if args.run_id:
        run, err = _lookup_run(args.run_id, channel_id, any_channel=args.any_channel)
        if err:
            print(err)
            print(f"\nRuns on channel '{channel_id}':")
            _print_channel_runs(channel_id)
            return 1

        mp4 = _resolve_mp4_path(run)
        if not mp4:
            print(f"Run {run.id} has no MP4 on disk.")
            print(f"  Stored path: {run.mp4_path or '(empty)'}")
            print(f"  Status: {run.status}")
            return 1

        upload_channel = run.channel_id
        if args.queue:
            from apis.youtube_quota import format_quota_detail, has_quota_for_upload

            if not has_quota_for_upload():
                print("WARNING: YouTube upload quota is too low for videos.insert (~1,600 units).")
                print(f"  {format_quota_detail()}")
                print(
                    "  Job will be queued but worker will defer until quota resets "
                    "(midnight Pacific). Continue anyway."
                )
            tags = []
            try:
                tags = json.loads(run.tags_json or "[]")
            except json.JSONDecodeError:
                tags = []
            job = enqueue_upload_job(
                channel_id=upload_channel,
                content_run_id=run.id,
                file_path=mp4,
                title=run.title or run.selected_topic,
                description=run.description or "",
                tags=tags if isinstance(tags, list) else [],
            )
            print(f"Queued upload job {job.id} for run {run.id} ({upload_channel})")
            print(f"  File: {mp4}")
            print("  Run: py -m jobs.worker")
            return 0

        print(f"Run {run.id} [{run.channel_id}]: {run.title or run.selected_topic}")
        print(f"  Status: {run.status}")
        print(f"  MP4: {mp4}")
        print(f"  On YouTube already: {_is_uploaded(run.id, upload_channel)}")
        print("  Queue upload: add --queue")
        return 0

    runs = list_recyclable(channel_id)
    if not runs:
        print(f"No rendered, un-uploaded videos for '{channel_id}'.")
        print("\nAll runs for this channel:")
        _print_channel_runs(channel_id)
        return 0

    print(f"Rendered videos you can upload ({channel_id}):\n")
    for run in runs:
        title = (run.title or run.selected_topic)[:70]
        print(f"  [{run.id}] {title}")
        print(f"       {_resolve_mp4_path(run)}")
    print(
        "\nQueue: py -m scripts.requeue_upload --channel",
        channel_id,
        "--run-id ID --queue",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
