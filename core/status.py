"""Read-only operator status (Phase J minimal)."""

from __future__ import annotations

from analytics.upload_queue import list_queue_entries, queue_lines, two_week_line
from config.channels import resolve_channel_id
from core.logging import get_logger
from youtube.check_setup import check_channel_setup

logger = get_logger("core.status")

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def ci_red_line(runs: list[dict], failed_jobs: list[str]) -> str:
    """#1263: one line when the newest finished CI run on main failed, else "".

    The grand audit (2026-10-17): CI had failed on every push for six days and nothing in
    the operator's or the agents' day said so. ``runs`` is `gh run list` JSON, newest first.
    """
    done = [r for r in runs or [] if str(r.get("status") or "") == "completed"]
    if not done or str(done[0].get("conclusion") or "") == "success":
        return ""
    if any(str(r.get("status") or "") != "completed" for r in (runs or [])[:1]):
        return ""  # a run is going; its verdict is the one that counts
    streak = []
    for run in done:
        if str(run.get("conclusion") or "") == "success":
            break
        streak.append(run)
    since = str(streak[-1].get("createdAt") or "")[:10]
    try:
        _year, month, day = (int(x) for x in since.split("-"))
        when = f"{_MONTHS[month - 1]} {day}"
    except ValueError:
        when = since or "?"
    jobs = ", ".join(failed_jobs[:2]) or "a job"
    plural = "run" if len(streak) == 1 else "runs"
    return (
        f"CI on main: RED since {when} - {len(streak)} {plural}; failing: {jobs} - "
        f"gh run view {streak[0].get('databaseId')} --log-failed"
    )


def ci_line() -> str:
    """#1263: `ci_red_line` from `gh`, or "" - no gh, no sign-in, or `CI_STATUS_LINE=false`."""
    import json
    import os
    import subprocess

    if os.getenv("CI_STATUS_LINE", "true").strip().lower() in ("0", "false", "no", "off"):
        return ""
    from config.paths import ROOT_DIR

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def gh(*args: str) -> object:
        out = subprocess.run(["gh", *args], cwd=ROOT_DIR, capture_output=True, text=True,
                             timeout=5, check=False, creationflags=flags)  # fmt: skip
        return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None

    try:
        runs = gh("run", "list", "--branch", "main", "--limit", "30", "--json",
                  "status,conclusion,createdAt,databaseId")  # fmt: skip
        if not isinstance(runs, list):
            return ""
        newest = next((r for r in runs if r.get("status") == "completed"), None)
        if not newest or newest.get("conclusion") == "success":
            return ""
        view = gh("run", "view", str(newest.get("databaseId")), "--json", "jobs")
        jobs = view.get("jobs", []) if isinstance(view, dict) else []
        failed = [str(j.get("name") or "") for j in jobs if j.get("conclusion") == "failure"]
        return ci_red_line(runs, [name.split(" (")[0] for name in failed if name])
    except Exception as exc:
        logger.debug("CI line skipped: %s", exc)
        return ""


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
        from apis.youtube_quota import format_usage_split

        split = format_usage_split()  # wave 113: what spent today's units
        if split:
            lines.append(f"  spent on: {split}")
    except Exception as exc:
        logger.debug("format_quota_detail skipped: %s", exc)

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
    except Exception as exc:
        logger.debug("Pending-jobs count unavailable: %s", exc)

    try:
        from core.batch_review import deadline_line, drafts_line

        waiting = drafts_line(channel_id)  # #1132
        if waiting:
            lines.append(waiting)
        deadline = deadline_line(channel_id)  # wave 109: a game preview waiting
        if deadline:
            lines.append(deadline)
    except Exception as exc:
        logger.debug("drafts line skipped: %s", exc)

    try:
        from core.job_queue import list_active_jobs, overdue_lines

        lines.extend(overdue_lines(list_active_jobs(), channel_id))  # #1129
    except Exception as exc:
        logger.debug("overdue uploads skipped: %s", exc)

    try:
        from core.stale_renders import shelf, shelf_lines

        lines.extend(shelf_lines(channel_id, shelf(channel_id)))  # #1122
    except Exception as exc:
        logger.debug("shelf skipped: %s", exc)

    try:
        from core.playlists import missing_line

        line = missing_line(channel_id)  # #1240
        if line:
            lines.append(line)
    except Exception as exc:
        logger.debug("playlist line skipped: %s", exc)

    try:
        from core.cadence import cadence_status, target_line

        week = target_line(cadence_status(channel_id))
        if week:
            lines.append(week)
    except Exception as exc:
        logger.debug("weekly target line skipped: %s", exc)

    try:
        from core.money.ledger import spend_line

        lines.append(spend_line())  # #980: everything paid, all time
    except Exception as exc:
        logger.debug("spend total line skipped: %s", exc)
    try:
        from core.money.ledger import ads_budget_line

        ads = ads_budget_line()  # #996: this month's ads against ADS_MONTHLY_CAP
        if ads:
            lines.append(ads)
    except Exception as exc:
        logger.debug("ads cap line skipped: %s", exc)

    try:
        from core.spend_week import spend_warning_line

        spend = spend_warning_line()
        if spend:
            lines.append(spend)
    except Exception as exc:
        logger.debug("weekly spend line skipped: %s", exc)

    entries = list_queue_entries(channel_id)
    awaiting = [e for e in entries if not e.on_youtube]
    lines.append(f"Publish queue: {len(entries)} reserved slot(s)")
    if awaiting:
        lines.append(
            f"  ({len(awaiting)} not on YouTube yet — upload must succeed before publishAt)"
        )
    lines.extend(queue_lines(entries, channel_id))  # #1527: one zone, a clash named
    lines.append(f"  {two_week_line(entries, channel_id)}")  # #1429

    from analytics.queue_manager import list_requeue_candidates

    requeue = list_requeue_candidates(channel_id)
    lines.append(f"Re-queue candidates (deleted on YT): {len(requeue)}")

    from storage.repositories.content_runs import get_content_run_repository

    runs = get_content_run_repository().list_for_channel(channel_id)[:5]
    lines.append(f"Recent content runs: {len(runs)} shown")
    for run in runs:
        lines.append(f"  - [{run.id}] {run_state(run):8} {(run.title or run.selected_topic)[:40]}")

    try:
        import os

        from config.seo import hints_path

        hints = hints_path(channel_id)
        if os.path.isfile(hints):
            lines.append(f"SEO hints: {hints}")
        else:
            lines.append("SEO hints: (none — run py -m analytics.seo_refresh)")
    except Exception as exc:
        logger.debug("SEO hints line skipped: %s", exc)

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
    except Exception as exc:
        logger.debug("Database status section skipped: %s", exc)

    try:
        from analytics.first_day import recent_lines

        lines.extend(recent_lines(channel_id))  # #49: a first day far from the usual
    except Exception as exc:
        logger.debug("first-day lines skipped: %s", exc)

    try:
        from publishing.crosspost import week_line

        line = week_line(channel_id)  # #979: TikTok and Instagram, from the Buffer packs
        if line:
            lines.append(line)
    except Exception as exc:
        logger.debug("buffer week line skipped: %s", exc)
    try:
        from analytics.growth import flag_line

        flagged = flag_line(channel_id)  # #1325: a video that brought 2+ subscribers
        if flagged:
            lines.append(flagged)
    except Exception as exc:
        logger.debug("subscriber flag skipped: %s", exc)
    try:
        from youtube.pin_comment import call_comment_line

        line = call_comment_line(channel_id)  # #1327: pinning is Studio-only
        if line:
            lines.append(line)
    except Exception as exc:
        logger.debug("call comment line skipped: %s", exc)

    try:
        from analytics.unconfirmed_check import status_line as unconfirmed_line

        line = unconfirmed_line(channel_id)  # #977: once a labelled claim has resolved
        if line:
            lines.append(line)
    except Exception as exc:
        logger.debug("unconfirmed claims line skipped: %s", exc)

    try:
        from analytics.promotions import status_line

        line = status_line(channel_id)  # #959: the last finished ad campaign's call
        if line:
            lines.append(line)
    except Exception as exc:
        logger.debug("promotions line skipped: %s", exc)

    try:
        from analytics.auto_research_report import verdict_line

        line = verdict_line(channel_id)  # #863: once ten runs carry it
        if line:
            lines.append(line)
    except Exception as exc:
        logger.debug("auto-research verdict line skipped: %s", exc)

    ci = ci_line()  # #1263
    if ci:
        lines.insert(1, ci)
    return lines


def run_state(run: object) -> str:
    """A run's status, or "retired" when it was retired (#1166 - run 139 read "rendered")."""
    import json

    try:
        features = json.loads(getattr(run, "features_json", None) or "{}")
    except (TypeError, ValueError):
        features = {}
    if isinstance(features, dict) and features.get("retired_at"):
        return "retired"
    return str(getattr(run, "status", "") or "")


# #986: one header line at startup instead of six. Each reader fails open; an empty part is
# left out. Module-level so a test patches one part at a time.
def _hdr_name(channel_id: str) -> str:
    from config.channels import get_channel_profile

    return str(get_channel_profile(channel_id).name or channel_id)


def _hdr_sign_in(channel_id: str) -> str:
    from youtube.oauth import sign_in_reminder, sign_in_status

    if sign_in_status(channel_id):
        return "signed out"
    return "sign-in due" if sign_in_reminder(channel_id) else "sign-in ok"


def _hdr_spent() -> str:
    from core.money.ledger import total_spent

    spent = total_spent()
    if not spent.get("count"):
        return "spent: not entered"
    return f"spent ${float(spent.get('total') or 0):,.2f}"


def _hdr_uploads() -> str:
    from apis.youtube_quota import uploads_remaining

    return f"~{uploads_remaining()} uploads left"


def _hdr_queue(channel_id: str) -> str:
    from core.job_queue import channel_queue_text, list_active_jobs, overdue_short

    jobs = list_active_jobs()
    text = channel_queue_text(jobs, channel_id)  # #989: this channel's jobs
    late = overdue_short(jobs, channel_id)  # #1129
    return f"{text} ({late})" if late else text


def _hdr_last(channel_id: str) -> str:
    import json

    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    rows = [
        r
        for r in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
        if getattr(r, "youtube_video_id", "") and not is_seeded(r)
    ]
    if not rows:
        return ""
    row = max(rows, key=lambda r: str(getattr(r, "published_at", "") or ""))
    try:
        metrics = json.loads(row.metrics_json or "{}")
        if not isinstance(metrics, dict):
            return ""
        if metrics.get("views") is None:
            # #1137: the 28-day window has not been read for this video yet. "0 views" said
            # it had been read and nobody came.
            lifetime = metrics.get("lifetime_views")
            if lifetime is None:
                return "last video not measured yet"
            return f"last video {max(0, int(lifetime)):,} views so far"
        views = int(metrics.get("views") or 0) - int(metrics.get("paid_views") or 0)
    except (TypeError, ValueError):
        return ""
    return f"last video {max(0, views):,} views"


def _hdr_week(channel_id: str) -> str:
    """#1133: "week 2 of 3-5" - uploads in the last seven days plus those scheduled, against
    the floor and the cap the operator set."""
    from core.cadence import cadence_status, week_band

    status = cadence_status(channel_id)
    return f"week {status.total} of {week_band(status)}"


def _hdr_shelf(channel_id: str) -> str:
    from core.stale_renders import shelf, shelf_short

    return shelf_short(shelf(channel_id))  # #1122


def header_line(channel_id: str) -> str:
    """channel · sign-in · spent · uploads left · queue · last video's views · the shelf."""
    readers = (
        lambda: _hdr_name(channel_id),
        lambda: _hdr_sign_in(channel_id),
        _hdr_spent,
        _hdr_uploads,
        lambda: _hdr_queue(channel_id),
        lambda: _hdr_last(channel_id),
        lambda: _hdr_week(channel_id),
        lambda: _hdr_shelf(channel_id),
    )
    parts: list[str] = []
    for read in readers:
        try:
            part = read()
        except Exception as exc:
            logger.debug("header part skipped: %s", exc)
            continue
        if part:
            parts.append(str(part))
    return " · ".join(parts)
