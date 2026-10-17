"""The app's Home page as text, no Qt (#981): what matters at a glance, each line fail-open.

Money spent (#980), the YouTube sign-in and its reminder (#971 #974), the queue, the last five
videos with their organic views and first-day verdict (#49), and the auto-research call once it
is due (#863). A reader that breaks says "unavailable", never takes Home down.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("desktop.home")

# #532: what this process already showed and stamped, by launch-state file and channel.
_LAUNCH_SEEN: dict[str, list[str]] = {}


def _money(_channel_id: str) -> str:
    from core.money.ledger import spend_line

    return spend_line()


def _ads(_channel_id: str) -> str:
    from core.money.ledger import ads_budget_line

    return ads_budget_line()  # #996: "" with no cap and no campaign


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


def changelog_since_last_launch(
    channel_id: str,
    *,
    root: str | None = None,
    state_path: str | Path | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Commit subjects since this channel last opened the app (#532). Stamps last_launch.

    Once per process: Home fills again on Refresh, and a second stamp emptied the card (the
    grand audit, 2026-10-17).
    """
    from config.paths import ROOT_DIR
    from desktop.session import launch_state_path

    when = now or datetime.now(timezone.utc)
    path = Path(state_path) if state_path is not None else launch_state_path()
    seen_key = f"{path}|{(channel_id or '').strip().lower()}"
    if seen_key in _LAUNCH_SEEN:
        return list(_LAUNCH_SEEN[seen_key])
    repo = str(root or ROOT_DIR)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("launch state unreadable: %s", exc)
    key = (channel_id or "").strip().lower()
    row = data.get(key) if isinstance(data.get(key), dict) else {}
    last = str((row or {}).get("last_launch") or "").strip()
    lines: list[str] = []
    if last:
        try:
            proc = subprocess.run(
                ["git", "-C", repo, "log", f"--since={last}", "--pretty=format:%s"],
                capture_output=True,
                text=True,
                check=False,
                # No console window flashes up from the app (pythonw has none to share).
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0:
                lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            else:
                lines = ["unavailable"]
        except OSError as exc:
            logger.debug("git changelog skipped: %s", exc)
            lines = ["unavailable"]
    data[key] = {**(row or {}), "last_launch": when.isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _LAUNCH_SEEN[seen_key] = list(lines)
    return lines


def _changelog(channel_id: str) -> str:
    return "\n".join(changelog_since_last_launch(channel_id))


# Readers by name, looked up at call time.
SECTIONS: list[tuple[str, str]] = [
    ("Money", "_money"),
    ("Ads", "_ads"),
    ("Sign-in", "_sign_in"),
    ("Queue", "_queue_line"),
    ("Last videos", "_last_videos"),
    ("Research", "_research"),
    ("Changelog", "_changelog"),
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
