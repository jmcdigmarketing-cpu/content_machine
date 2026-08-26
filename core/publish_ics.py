"""#133 .ics of scheduled publishes — written beside HTML dumps, not under data/."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from core.html_report import html_dir
from core.logging import get_logger

logger = get_logger("core.publish_ics")


def _ics_stamp(when: datetime | None) -> str:
    if when is None:
        when = datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _vevent(log) -> str:
    summary = (log.detail or f"{log.channel_id} scheduled publish").replace("\n", " ")[:70]
    uid = f"publish-{log.id}@content-os"
    start = _ics_stamp(log.published_at)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{start}",
        f"DTSTART:{start}",
        f"SUMMARY:{summary}",
        "END:VEVENT",
    ]
    return "\r\n".join(lines)


def write_scheduled_ics(channel_id: str) -> str:
    """Write a VCALENDAR of future scheduled publish_log rows under html_dir()."""
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_publish_log_repository()
    rows = list(repo.list_future_scheduled(channel_id) or [])
    dest_dir = html_dir()
    path = os.path.join(dest_dir, f"scheduled_{channel_id}.ics")
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Content OS//scheduled publishes//EN",
        "CALSCALE:GREGORIAN",
    ]
    for row in rows:
        body.append(_vevent(row))
    body.append("END:VCALENDAR")
    text = "\r\n".join(body) + "\r\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path
