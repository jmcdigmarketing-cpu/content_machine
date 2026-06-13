"""Read-only operator status (Phase J minimal)."""

from __future__ import annotations

from analytics.upload_queue import list_queue_entries
from config.channels import resolve_channel_id
from youtube.check_setup import check_channel_setup


def build_status_lines(channel_id: str) -> list[str]:
    channel_id = resolve_channel_id(channel_id)
    lines: list[str] = []

    report = check_channel_setup(channel_id)
    lines.append(f"YouTube upload: {'OK' if report.ok else 'NOT READY'}")
    if not report.ok and report.issues:
        for issue in report.issues[:3]:
            lines.append(f"  - {issue}")

    try:
        from apis.youtube_quota import format_quota_detail, has_quota_for_upload

        if has_quota_for_upload():
            lines.append(f"YouTube API quota: {format_quota_detail()}")
        else:
            lines.append(
                f"YouTube API quota: BLOCKED for uploads — {format_quota_detail()} "
                "(upload ~1,600 units; discovery search ~101 each)"
            )
    except Exception:
        pass

    try:
        from sqlalchemy import select

        from storage.db import get_session
        from storage.models import Job
        from storage.repositories.jobs import JOB_FAILED, JOB_PENDING

        session = get_session()
        try:
            failed = session.scalars(
                select(Job).where(
                    Job.channel_id == channel_id,
                    Job.job_type == "upload",
                    Job.status == JOB_FAILED,
                )
            ).all()
            quota_failed = [j for j in failed if j.last_error and "quota" in j.last_error.lower()]
            if quota_failed:
                lines.append(
                    f"Failed upload jobs (quota): {len(quota_failed)} — "
                    "re-queue after reset: py -m scripts.requeue_upload --channel "
                    f"{channel_id} --run-id ID --queue"
                )
            pending = session.scalars(
                select(Job).where(
                    Job.channel_id == channel_id,
                    Job.job_type == "upload",
                    Job.status == JOB_PENDING,
                )
            ).all()
            if pending:
                lines.append(f"Pending upload jobs: {len(pending)}")
        finally:
            session.close()
    except Exception:
        pass

    try:
        from scripts.requeue_upload import list_recyclable

        recyclable = list_recyclable(channel_id)
        if recyclable:
            lines.append(
                f"Rendered, not on YouTube: {len(recyclable)} video(s) — "
                f"py -m scripts.requeue_upload --channel {channel_id}"
            )
    except Exception:
        pass

    entries = list_queue_entries(channel_id)
    awaiting = [e for e in entries if not e.on_youtube]
    lines.append(f"Publish queue: {len(entries)} reserved slot(s)")
    if awaiting:
        lines.append(
            f"  ({len(awaiting)} not on YouTube yet — upload must succeed before publishAt)"
        )
    for e in entries[:5]:
        lines.append(f"  - {e.publish_at.isoformat()[:16]}  {e.title[:35]}  [{e.status}]")

    from analytics.queue_manager import list_requeue_candidates

    requeue = list_requeue_candidates(channel_id)
    lines.append(f"Re-queue candidates (deleted on YT): {len(requeue)}")

    from storage.repositories.content_runs import get_content_run_repository

    runs = get_content_run_repository().list_for_channel(channel_id)[:5]
    lines.append(f"Recent content runs: {len(runs)} shown")
    for run in runs:
        lines.append(f"  - [{run.id}] {run.status:8} {(run.title or run.selected_topic)[:40]}")

    try:
        import os

        from config.seo import hints_path

        hints = hints_path(channel_id)
        if os.path.isfile(hints):
            lines.append(f"SEO hints: {hints}")
        else:
            lines.append("SEO hints: (none — run py -m analytics.seo_refresh)")
    except Exception:
        pass

    try:
        from analytics.competitor_context import (
            list_recent_competitor_titles,
            snapshot_age_hours,
        )

        age = snapshot_age_hours(channel_id)
        if age is None:
            lines.append("Competitors: not synced — py -m scripts.ops daily-sync")
        else:
            lines.append(f"Competitors: snapshot {age:.0f}h old")
            for row in list_recent_competitor_titles(channel_id, limit=3):
                lines.append(f"  - {row.get('title', '')[:45]}")
    except Exception:
        pass

    return lines
