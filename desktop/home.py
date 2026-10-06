"""The app's Home page as text, no Qt (#981): what matters at a glance, each line fail-open.

Money spent (#980), the YouTube sign-in and its reminder (#971 #974), the queue, the last five
videos with their organic views and first-day verdict (#49), and the auto-research call once it
is due (#863). A reader that breaks says "unavailable", never takes Home down.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger("desktop.home")


def _money(_channel_id: str) -> str:
    from core.money.ledger import spend_line

    return spend_line()


def _sign_in(channel_id: str) -> str:
    from youtube.oauth import sign_in_reminder, sign_in_status

    problem = sign_in_status(channel_id)
    if problem:
        return problem
    return sign_in_reminder(channel_id) or f"YouTube sign-in ok ({channel_id})"


def _queue_line(channel_id: str) -> str:
    from core.job_queue import channel_queue_text, list_active_jobs

    return channel_queue_text(list_active_jobs(), channel_id, label="Queue:")  # #989


def _recent_lines(channel_id: str, limit: int = 5) -> list[str]:
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    rows = [
        r
        for r in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
        if getattr(r, "youtube_video_id", "") and not is_seeded(r)
    ]
    rows.sort(key=lambda r: str(getattr(r, "published_at", "") or ""), reverse=True)
    out: list[str] = []
    for row in rows[:limit]:
        try:
            metrics = json.loads(row.metrics_json or "{}")
        except (TypeError, ValueError):
            metrics = {}
        views = int(metrics.get("views") or 0) - int(metrics.get("paid_views") or 0)
        verdict = (metrics.get("first_day") or {}).get("verdict")
        tail = f" (first day {verdict})" if verdict in ("low", "high") else ""
        out.append(
            f"{str(row.detail or row.youtube_video_id)[:50]} - {max(0, views):,} views{tail}"
        )
    return out


def _last_videos(channel_id: str) -> str:
    return "\n".join(_recent_lines(channel_id)) or "No uploads yet"


def _research(_channel_id: str) -> str:
    from analytics.auto_research_report import verdict_line

    return verdict_line(_channel_id)


# Readers by name, looked up at call time.
SECTIONS: list[tuple[str, str]] = [
    ("Money", "_money"),
    ("Sign-in", "_sign_in"),
    ("Queue", "_queue_line"),
    ("Last videos", "_last_videos"),
    ("Research", "_research"),
]


def home_lines(channel_id: str) -> list[tuple[str, str]]:
    """[(label, text)] in display order; an empty optional line is left out."""
    out: list[tuple[str, str]] = []
    for label, name in SECTIONS:
        try:
            reader: Callable[[str], Any] = globals()[name]
            text: Any = reader(channel_id)
        except Exception as exc:
            logger.debug("home %s skipped: %s", label, exc)
            text = f"unavailable ({type(exc).__name__})"
        if text:
            out.append((label, str(text)))
    return out
