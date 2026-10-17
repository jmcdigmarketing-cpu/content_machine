"""Retire rendered videos that sat unuploaded past their news date (2026-09-16).

`ops status` counted "5 rendered, not on YouTube" - runs from June and July about a
third-place match and a UFC card long over. They are not a backlog to publish, they are
noise in the number the operator reads every morning. Retiring marks
`features.retired_at`; `scripts.requeue_upload.list_recyclable` then skips the run. The
mp4 stays on disk and `requeue_upload --run-id N --queue` still takes it by id.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.run_features import merge_features

logger = get_logger("core.stale_renders")


def render_age_days(run: Any, *, now: float | None = None) -> float | None:
    path = str(getattr(run, "mp4_path", "") or "")
    try:
        modified = os.path.getmtime(path)
    except OSError:
        return None
    return max(0.0, ((now or time.time()) - modified) / 86400.0)


def find_stale_renders(channel_id: str, *, days: int = 30) -> list[Any]:
    """Unuploaded, unretired renders whose mp4 is older than `days`."""
    from scripts.requeue_upload import list_recyclable

    out = []
    for run in list_recyclable(channel_id):
        age = render_age_days(run)
        if age is not None and age >= days:
            out.append(run)
    return out


STALE_DAYS = 30


def shelf(channel_id: str, *, days: int = STALE_DAYS) -> dict[str, int]:
    """Finished videos that are not public (#1122).

    129 runs had produced 32 public videos; 13 renders were never uploaded and 5 uploads were
    still unlisted, and no line the operator reads each morning said so. `renders` is every
    unuploaded, unretired render, `stale` those past `days`; `unlisted` is every upload still
    unlisted, `claim` those rendered past the grounding gate (they need `verify-claim` first).
    """
    from publishing.go_public import override_held, unlisted_holds
    from scripts.requeue_upload import list_recyclable

    renders = list_recyclable(channel_id)
    waiting = _queued_runs(channel_id)
    stale = queued = past = 0
    for run in renders:
        if int(run.id) in waiting:  # #1131: queued is waiting on the worker, not on a decision
            queued += 1
            continue
        age = render_age_days(run)
        if age is not None and age >= days:
            stale += 1
        elif age is not None and age > 2 * _news_window(run, channel_id):
            past += 1  # #1237: run 114 was "recent - requeue_upload" at 12 days of a 2-day story
    held = unlisted_holds(channel_id)
    claim = sum(1 for row in held if override_held(getattr(row, "content_run_id", None)))
    counts = {
        "renders": len(renders),
        "stale": stale,
        "queued": queued,
        "unlisted": len(held),
        "claim": claim,
    }
    if past:
        counts["past_window"] = past
    return counts


def _queued_runs(channel_id: str) -> dict[int, Any]:
    """{run id: its pending upload job} - a render that is queued is not "never uploaded"."""
    try:
        from core.job_queue import list_active_jobs

        return {
            int(job.content_run_id): job
            for job in list_active_jobs()
            if job.job_type == "upload"
            and job.status == "pending"
            and job.channel_id == channel_id
            and job.content_run_id
        }
    except Exception as exc:
        logger.debug("queued uploads not read: %s", exc)
        return {}


def _signed_out(channel_id: str) -> bool:
    try:
        from youtube.oauth import signed_out

        return signed_out(channel_id)
    except Exception:
        return False


def shelf_rows(channel_id: str, *, days: int = STALE_DAYS) -> list[dict[str, Any]]:
    """One row per finished video that is not public, with the exact command (#1131).

    `ops status` gave counts and placeholders ("VIDEO_ID", "--run-id N"). Each row here has the
    run, the title, how old it is, what it is waiting on and the command with the id filled in.
    """
    from publishing.go_public import override_held, unlisted_holds
    from scripts.requeue_upload import list_recyclable

    rows: list[dict[str, Any]] = []
    queued = _queued_runs(channel_id)
    signed_out = bool(queued) and _signed_out(channel_id)  # #1153
    for run in list_recyclable(channel_id):
        age = render_age_days(run)
        base = {
            "run_id": int(run.id),
            "title": str(getattr(run, "title", "") or "(untitled)"),
            "age_days": age,
        }
        if int(run.id) in queued and signed_out:
            rows.append(
                dict(
                    base,
                    state="queued - the YouTube sign-in has expired",
                    command=f"py -m youtube.oauth_setup --channel {channel_id}",
                )
            )
        elif int(run.id) in queued:
            rows.append(
                dict(
                    base,
                    state="queued, waiting for the worker",
                    command="py -m scripts.ops worker",
                )
            )
        elif age is not None and age >= days:
            rows.append(
                dict(
                    base,
                    state=f"rendered {age:.0f} days ago, never uploaded",
                    command=f"py -m scripts.ops retire-renders --channel {channel_id} "
                    f"--run-id {run.id} --apply",
                    stale=True,
                )
            )
        elif age is not None and age > 2 * _news_window(run, channel_id):
            # #1231: run 114 (UFC news, a 2-day window) sat 12 days on the shelf and held one of
            # overnight's three places. It no longer counts; its file stays.
            rows.append(
                dict(
                    base,
                    state=f"rendered {age:.0f} days ago, past its window - nothing uploads it",
                    command=f"py -m scripts.ops retire-renders --channel {channel_id} "
                    f"--run-id {run.id} --apply",
                    stale=True,
                )
            )
        else:
            rows.append(
                dict(
                    base,
                    state="rendered, never uploaded",
                    command=f"py -m scripts.requeue_upload --channel {channel_id} "
                    f"--run-id {run.id} --queue",
                )
            )
    for row in unlisted_holds(channel_id):
        run_id = getattr(row, "content_run_id", None)
        held = override_held(run_id)
        rows.append(
            {
                "run_id": int(run_id) if run_id else 0,
                "title": _upload_title(row),
                "age_days": None,
                "state": "unlisted, held for a claim" if held else "unlisted on YouTube",
                "command": (
                    f"py -m scripts.ops verify-claim --run-id {run_id}"
                    if held
                    else f"py -m scripts.ops go-public {row.youtube_video_id} "
                    f"--channel {channel_id} --apply"
                ),
            }
        )
    return rows


def _news_window(run: Any, channel_id: str) -> float:
    """The render's freshness window in days, read the way a draft's is (`batch_review`)."""
    try:
        from core.batch_review import freshness_window_days

        meta = {
            "topic": str(getattr(run, "topic", "") or ""),
            "title": str(getattr(run, "title", "") or ""),
            "channel_id": channel_id,
        }
        return float(freshness_window_days(meta))
    except Exception as exc:
        logger.debug("render window unread for run %s: %s", getattr(run, "id", "?"), exc)
        return float(STALE_DAYS)


def _upload_title(row: Any) -> str:
    try:
        from storage.repositories.publish_log import video_title

        return video_title(row)
    except Exception as exc:
        logger.debug("shelf title unavailable: %s", exc)
        return "(untitled)"


def shelf_report(channel_id: str) -> list[str]:
    """`ops shelf`."""
    rows = shelf_rows(channel_id)
    if not rows:
        return [f"Shelf - {channel_id}: every finished video is public."]
    lines = [f"Shelf - {channel_id}: {len(rows)} finished video(s) not public"]
    for row in rows:
        lines.append(f"  run {row['run_id']}  {row['title'][:70]}")
        lines.append(f"      {row['state']}")
        lines.append(f"      {row['command']}")
    return lines


def gone_reason(run_id: int, channel_id: str) -> str:
    """Why a finished run is off the shelf, when the record says (#1166): the reason its
    upload was cancelled, or the day it was retired. "" when neither is on record.

    Runs 136 and 139 were pulled on 2026-10-13 with a reason on the cancelled job, and
    `ops overnight-last` said "already public, or retired".
    """
    import json

    try:
        from core.job_queue import list_active_jobs

        for job in list_active_jobs():
            error = str(getattr(job, "last_error", "") or "")
            if (
                int(getattr(job, "content_run_id", 0) or 0) == int(run_id)
                and getattr(job, "channel_id", "") == channel_id
                and getattr(job, "job_type", "") == "upload"
                and error.startswith("Pulled")
            ):
                return f"pulled - {error}"
    except Exception as exc:
        logger.debug("pulled reason unreadable for run %s: %s", run_id, exc)
    try:
        from storage.repositories.content_runs import get_content_run_repository

        run = get_content_run_repository().get(int(run_id))
        features = json.loads(getattr(run, "features_json", None) or "{}") if run else {}
        stamp = str(features.get("retired_at") or "") if isinstance(features, dict) else ""
        if stamp:
            return f"retired on {stamp[:10]}"
    except Exception as exc:
        logger.debug("retire stamp unreadable for run %s: %s", run_id, exc)
    return ""


def shelf_total(counts: dict[str, int]) -> int:
    return int(counts.get("renders") or 0) + int(counts.get("unlisted") or 0)


def shelf_lines(channel_id: str, counts: dict[str, int], *, days: int = STALE_DAYS) -> list[str]:
    """One line per kind of unpublished video, each with the command that moves it."""
    out: list[str] = []
    unlisted, claim = int(counts.get("unlisted") or 0), int(counts.get("claim") or 0)
    if unlisted:
        parts = []
        if unlisted - claim:
            parts.append(
                f"{unlisted - claim} ready - py -m scripts.ops go-public --channel {channel_id}"
            )
        if claim:
            parts.append(f"{claim} held for a claim - py -m scripts.ops verify-claim --run-id N")
        out.append(f"Unlisted, not public: {unlisted} video(s) ({'; '.join(parts)})")
    renders, stale = int(counts.get("renders") or 0), int(counts.get("stale") or 0)
    queued = int(counts.get("queued") or 0)
    past = int(counts.get("past_window") or 0)
    if renders:
        parts = []
        if queued and _signed_out(channel_id):
            parts.append(
                f"{queued} queued, the sign-in has expired - "
                f"py -m youtube.oauth_setup --channel {channel_id}"
            )
        elif queued:
            parts.append(f"{queued} queued, waiting for the worker - py -m scripts.ops worker")
        if renders - stale - queued - past:
            parts.append(
                f"{renders - stale - queued - past} recent - "
                f"py -m scripts.requeue_upload --channel {channel_id}"
            )
        if past:
            parts.append(
                f"{past} past their window - py -m scripts.ops shelf --channel {channel_id}"
            )
        if stale:
            parts.append(
                f"{stale} older than {days} days - "
                f"py -m scripts.ops retire-renders --channel {channel_id}"
            )
        out.append(f"Rendered, not on YouTube: {renders} video(s) ({'; '.join(parts)})")
    return out


def shelf_short(counts: dict[str, int]) -> str:
    """The header's few words, or "" when everything finished is public."""
    total = shelf_total(counts)
    return f"{total} finished, not public" if total else ""


def retire_renders(runs: list[Any]) -> list[int]:
    """Mark each run retired. Returns the ids marked. Never deletes a file."""
    stamp = datetime.now().isoformat(timespec="seconds")
    marked: list[int] = []
    for run in runs:
        try:
            merge_features(int(run.id), {"retired_at": stamp})
            marked.append(int(run.id))
        except Exception as exc:
            logger.warning("retire skipped for run %s: %s", getattr(run, "id", "?"), exc)
    return marked
