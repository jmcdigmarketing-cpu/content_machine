"""A video's privacy, read back from YouTube (#1128).

The publish log kept the privacy a video was uploaded with and never asked again. A scheduled
upload goes up private and turns public at its slot; a held one is made public in Studio. On
2026-10-10 the log said 32 public, 5 unlisted and 6 private, and YouTube said all 43 were
public - so "finished, not public" counted five videos that were live, and cost per published
minute left eleven out. The operator found it: asked about three "unlisted" videos, the answer
was "all 3 were published".

One `videos.list(part="status")` per 50 videos, 1 quota unit each, inside the metrics sync.
A video YouTube no longer returns is reported and left alone - nothing here deletes a row.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.privacy_sync")

GONE = "gone"
_KNOWN = frozenset({"public", "unlisted", "private"})


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def drift(
    stored: dict[str, str], live: dict[str, str], *, held: Any = frozenset()
) -> dict[str, list[str]]:
    """{video_id: [was, now]} for every video whose stored privacy is not YouTube's.

    A video missing from `live` is `GONE`. An answer that is not a privacy YouTube has
    (an empty status) is not a change. A video in `held` (#1519: private with a publishAt -
    YouTube holds it for its slot) is not a change either; `sync_privacy` keeps its record.
    """
    out: dict[str, list[str]] = {}
    for video_id, was in stored.items():
        if video_id in held:
            continue
        now = live.get(video_id, GONE)
        if now != GONE and now not in _KNOWN:
            continue
        if now != str(was or "").strip().lower():
            out[video_id] = [str(was or ""), now]
    return out


def fetch_status(service: Any, video_ids: list[str]) -> dict[str, dict[str, str]] | None:
    """{video_id: {"privacy", "publish_at"}} for the ids YouTube returns, or None when the read
    failed. `publish_at` (#1519) is YouTube's scheduled slot, "" when none is set."""
    live: dict[str, dict[str, str]] = {}
    try:
        for start in range(0, len(video_ids), 50):
            chunk = video_ids[start : start + 50]
            _spend(1)
            reply = (
                service.videos().list(part="status", id=",".join(chunk), maxResults=50).execute()
            )
            for item in reply.get("items") or []:
                status = item.get("status") or {}
                live[str(item.get("id") or "")] = {
                    "privacy": str(status.get("privacyStatus") or "").lower(),
                    "publish_at": str(status.get("publishAt") or ""),
                }
    except Exception as exc:
        logger.warning("privacy read failed: %s", exc)
        return None
    return live


def fetch_privacy(service: Any, video_ids: list[str]) -> dict[str, str] | None:
    """{video_id: privacyStatus} for the ids YouTube returns, or None when the read failed."""
    live = fetch_status(service, video_ids)
    return None if live is None else {vid: s["privacy"] for vid, s in live.items()}


def held_slots(live: dict[str, dict[str, str]]) -> dict[str, datetime]:
    """#1519: {video_id: slot} for each video YouTube holds private until a publishAt."""
    out: dict[str, datetime] = {}
    for video_id, status in live.items():
        if status.get("privacy") != "private" or not status.get("publish_at"):
            continue
        try:
            when = datetime.fromisoformat(str(status["publish_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        out[video_id] = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return out


def _spend(units: int) -> None:
    try:
        from apis.youtube_quota import record_usage

        record_usage(units=units, caller="privacy")
    except Exception as exc:
        logger.debug("privacy sync: usage not recorded: %s", exc)


def _service(channel_id: str) -> Any:
    from youtube.oauth import get_youtube_service

    return get_youtube_service(channel_id)


def sync_privacy(channel_id: str, *, service: Any = None, apply: bool = True) -> dict[str, Any]:
    """Bring `privacy_status` level with YouTube, and a run's status with its video (#1126).

    Returns {checked, changed: [{run_id, video_id, was, now}], gone: [...], runs_published,
    error}. `apply=False` reports without writing.
    """
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    report: dict[str, Any] = {
        "checked": 0,
        "changed": [],
        "gone": [],
        "runs_published": [],
        "error": "",
    }
    repo = get_publish_log_repository()
    rows = [
        r
        for r in repo.list_uploaded_for_channel(channel_id) or []
        if str(getattr(r, "youtube_video_id", "") or "").strip() and not is_seeded(r)
    ]
    if not rows:
        return report
    try:
        service = service or _service(channel_id)
    except Exception as exc:
        report["error"] = f"no YouTube sign-in: {exc}"
        return report
    if service is None:
        report["error"] = "no YouTube sign-in for this channel"
        return report
    status = fetch_status(service, [str(r.youtube_video_id) for r in rows])
    if status is None:
        report["error"] = "YouTube did not answer"
        return report
    live = {vid: s["privacy"] for vid, s in status.items()}
    held = held_slots(status)
    report["checked"] = len(rows)
    report["rescheduled"] = []
    stored = {str(r.youtube_video_id): str(r.privacy_status or "") for r in rows}
    for row in rows:  # #1519: run 154 was moved to 10-21 on YouTube; its record kept 10-19
        slot = held.get(str(row.youtube_video_id))
        if slot is None:
            continue
        fix: dict[str, Any] = {}
        if str(row.privacy_status or "").strip().lower() != "public":
            fix["privacy_status"] = "public"  # a scheduled upload's record holds its target
        was = getattr(row, "published_at", None)
        if was is None or abs((slot - _aware(was)).total_seconds()) > 60:
            fix["published_at"] = slot
        if fix:
            report["rescheduled"].append(
                {"run_id": row.content_run_id, "video_id": str(row.youtube_video_id),
                 "slot": slot.isoformat()}
            )  # fmt: skip
            if apply:
                repo.update(row.id, fix)
    changes = drift(stored, live, held=held)
    for row in rows:
        video_id = str(row.youtube_video_id)
        if video_id not in changes:
            continue
        was, now = changes[video_id]
        entry = {"run_id": row.content_run_id, "video_id": video_id, "was": was, "now": now}
        if now == GONE:
            report["gone"].append(entry)
            continue
        report["changed"].append(entry)
        if apply:
            repo.update(row.id, {"privacy_status": now})
    public_runs = [
        int(r.content_run_id)
        for r in rows
        if r.content_run_id and live.get(str(r.youtube_video_id)) == "public"
    ]
    report["runs_published"] = _publish_runs(public_runs, apply=apply)
    return report


def _publish_runs(run_ids: list[int], *, apply: bool) -> list[int]:
    """#1126: a run whose video is public and whose own status still says "scheduled"."""
    from storage.repositories.content_runs import get_content_run_repository

    moved: list[int] = []
    try:
        repo = get_content_run_repository()
        for run_id in sorted(set(run_ids)):
            run = repo.get(run_id)
            if run is None or str(getattr(run, "status", "") or "") != "scheduled":
                continue
            if apply:
                repo.update(run_id, {"status": "published"})
            moved.append(run_id)
    except Exception as exc:
        logger.warning("run status not reconciled: %s", exc)
    return moved


def _runs(entries: list[dict[str, Any]]) -> str:
    names = [f"run {e['run_id']}" if e.get("run_id") else str(e["video_id"]) for e in entries]
    return ", ".join(names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")


def sync_lines(report: dict[str, Any]) -> list[str]:
    """What the metrics sync prints. Nothing when the record already matches."""
    if report.get("error"):
        return [f"Privacy: not checked ({report['error']})"]
    lines: list[str] = []
    by_now: dict[str, list[dict[str, Any]]] = {}
    for entry in report.get("changed") or []:
        by_now.setdefault(str(entry["now"]), []).append(entry)
    for now, entries in sorted(by_now.items()):
        lines.append(
            f"Privacy: {len(entries)} video(s) are {now} on YouTube and the record said "
            f"otherwise - corrected ({_runs(entries)})"
        )
    gone = report.get("gone") or []
    if gone:
        lines.append(
            f"Privacy: {len(gone)} video(s) are no longer on YouTube ({_runs(gone)}) - "
            "the record is left as it was"
        )
    moved = report.get("runs_published") or []
    if moved:
        lines.append(f'Run status: {len(moved)} run(s) were still "scheduled" - now published')
    rescheduled = report.get("rescheduled") or []
    if rescheduled:
        slots = ", ".join(f"run {e['run_id']} {str(e['slot'])[:16]}Z" for e in rescheduled)
        lines.append(f"Schedule: {len(rescheduled)} video(s) YouTube publishes at another time - "
                     f"the record now has YouTube's slot ({slots})")  # fmt: skip
    return lines
