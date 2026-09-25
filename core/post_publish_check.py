"""Look at every upload again 48 hours after it goes public (#600).

The public Data API does not expose the yellow-dollar monetisation icon - that lives in
Studio and the partner Content ID API only. It does expose what usually sits behind it, and
with third-party gameplay in the backgrounds (#786) these are the ones worth a morning line:

  - the video is gone (removed, or deleted in Studio)
  - upload rejected or failed, with YouTube's reason
  - blocked in some countries - the usual trace of a copyright claim
  - age-restricted - limited or no ads
  - marked made for kids - no personalised ads, comments off

One `videos.list` call per 50 videos (1 quota unit). Each video is checked once; results
are kept in data/post_publish_<channel>.json. The nightly `ops overnight` prints the line;
`ops post-publish-check` runs it by hand.

    POST_PUBLISH_CHECK=true      # default; false = the nightly run skips it
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger("core.post_publish_check")

CHECK_AFTER_HOURS = 48


def enabled() -> bool:
    raw = (os.getenv("POST_PUBLISH_CHECK", "") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def store_path_for(channel_id: str) -> str:
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, f"post_publish_{channel_id}.json")


def _load(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def due(
    rows: list[Any],
    *,
    now: datetime,
    checked: set[str],
    hours: int = CHECK_AFTER_HOURS,
) -> list[Any]:
    """Uploaded rows public for `hours`+ that have not been checked yet."""
    cutoff = (now if now.tzinfo else now.replace(tzinfo=UTC)) - timedelta(hours=hours)
    out = []
    for row in rows:
        vid = (getattr(row, "youtube_video_id", "") or "").strip()
        when = _aware(getattr(row, "published_at", None))
        if not vid or vid in checked or when is None or when > cutoff:
            continue
        if getattr(row, "status", "") == "cancelled":
            continue
        out.append(row)
    return out


def assess(item: dict[str, Any] | None) -> list[str]:
    """Plain-language flags for one videos.list item; [] when nothing is wrong."""
    if not item:
        return ["removed from YouTube"]
    status = item.get("status") or {}
    details = item.get("contentDetails") or {}
    flags: list[str] = []
    upload = str(status.get("uploadStatus") or "")
    if upload == "rejected":
        flags.append(f"upload rejected: {status.get('rejectionReason') or 'no reason given'}")
    elif upload == "failed":
        flags.append(f"upload failed: {status.get('failureReason') or 'no reason given'}")
    blocked = (details.get("regionRestriction") or {}).get("blocked") or []
    if blocked:
        flags.append(f"blocked in {len(blocked)} countries (usually a copyright claim)")
    allowed = (details.get("regionRestriction") or {}).get("allowed")
    if isinstance(allowed, list):
        flags.append(f"only viewable in {len(allowed)} countries (usually a copyright claim)")
    if (details.get("contentRating") or {}).get("ytRating") == "ytAgeRestricted":
        flags.append("age-restricted (limited or no ads)")
    if status.get("madeForKids"):
        flags.append("made for kids (no personalised ads, comments off)")
    return flags


def run_post_publish_checks(
    channel_id: str,
    *,
    service=None,
    rows: list[Any] | None = None,
    now: datetime | None = None,
    store_path: str | None = None,
) -> dict[str, Any]:
    """Check every due video once. Returns {checked, flagged: {id: [flags]}, error}."""
    report: dict[str, Any] = {"checked": 0, "flagged": {}, "error": ""}
    now = now or datetime.now(UTC)
    path = store_path or store_path_for(channel_id)
    data = _load(path)
    results: dict[str, Any] = dict(data.get("videos") or {})
    if rows is None:
        from storage.repositories.publish_log import get_publish_log_repository

        rows = list(get_publish_log_repository().list_uploaded_for_channel(channel_id) or [])
    pending = due(rows, now=now, checked=set(results))
    if not pending:
        return report
    if service is None:
        from youtube.oauth import get_youtube_service
        from youtube.upload import is_upload_configured

        if not is_upload_configured(channel_id):
            report["error"] = "YouTube upload is not configured for this channel"
            return report
        service = get_youtube_service(channel_id)
    ids = [r.youtube_video_id for r in pending]
    items: dict[str, dict[str, Any]] = {}
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        resp = (
            service.videos()
            .list(part="status,contentDetails", id=",".join(chunk), maxResults=50)
            .execute()
        )
        for item in resp.get("items") or []:
            items[str(item.get("id") or "")] = item
    stamp = now.isoformat(timespec="seconds")
    for vid in ids:
        flags = assess(items.get(vid))
        results[vid] = {"checked_at": stamp, "flags": flags}
        if flags:
            report["flagged"][vid] = flags
    report["checked"] = len(ids)
    data["videos"] = results
    _save(path, data)
    return report


def render_report(report: dict[str, Any]) -> str:
    if report.get("error"):
        return f"48h check: not run - {report['error']}"
    if not report.get("checked"):
        return "48h check: nothing due"
    flagged = report.get("flagged") or {}
    if not flagged:
        return f"48h check: {report['checked']} video(s) look fine"
    lines = [f"48h check: {len(flagged)} of {report['checked']} video(s) need a look in Studio"]
    for vid, flags in flagged.items():
        lines.append(f"  https://youtu.be/{vid}: {'; '.join(flags)}")
    return "\n".join(lines)


def post_publish_line(channel_id: str) -> str:
    """The nightly line. Empty when switched off or nothing was due. Never raises."""
    if not enabled():
        return ""
    try:
        report = run_post_publish_checks(channel_id)
    except Exception as exc:
        logger.debug("post-publish check skipped: %s", exc)
        return ""
    if not report.get("checked") and not report.get("error"):
        return ""
    return render_report(report)
