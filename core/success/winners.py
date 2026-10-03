"""The winners library: what worked on this channel, shown to the script writer (#937).

The writer saw the channel persona, the playbook and the facts - never which of the
channel's own videos the audience watched most. `winners` takes the top videos by views
among the measured ones (top 10%, at least 3, at most 5) once there are
`WINNERS_MIN_MEASURED`; below that floor a "winner" is noise and nothing is shown. Each
carries its title, hook, length and domain - from the run's features when this machine made
it, from the publish log otherwise (seeded videos: real titles and views).

`winners_block` puts them in the script prompt as a pattern to learn from, never as words or
facts to reuse. A finished-output change, disclosed; `WINNERS_IN_PROMPT=false` turns it off.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.winners")

WINNERS_MIN_MEASURED = 8
WINNERS_MAX = 5


def _enabled() -> bool:
    return os.getenv("WINNERS_IN_PROMPT", "true").strip().lower() not in ("0", "false", "no", "off")


def measured_count(channel_id: str) -> int:
    from core.success.videos import channel_videos

    return sum(1 for v in channel_videos(channel_id) if v.views > 0)


def _features(run_id: int | None) -> dict[str, Any]:
    if run_id is None:
        return {}
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
        data = json.loads(getattr(record, "features_json", None) or "{}") if record else {}
    except Exception as exc:
        logger.debug("features for run %s unavailable: %s", run_id, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _ranked(channel_id: str) -> tuple[list[tuple[Any, int]], str, str]:
    from core.success.videos import channel_videos, comparable_views

    return comparable_views(channel_videos(channel_id), min_count=WINNERS_MIN_MEASURED)


def winners(channel_id: str) -> list[dict[str, Any]]:
    """[{title, views, unit, domain, format, hook}] best first, or [] below the floor.

    #940: ranked on views in the first 7 days once enough videos have them, else views
    to date, else the sync's 28-day window - never a mix.
    """
    ranked, _heading, unit = _ranked(channel_id)
    if len(ranked) < WINNERS_MIN_MEASURED:
        return []
    top = min(WINNERS_MAX, max(3, math.ceil(len(ranked) * 0.1)))
    out = []
    for video, value in ranked[:top]:
        features = _features(video.run_id)
        out.append(
            {
                "title": video.title,
                "views": value,
                "unit": unit,
                "domain": str(features.get("domain") or video.domain or ""),
                "format": str(features.get("format") or ""),
                "hook": str(features.get("hook_text") or "").strip(),
            }
        )
    return out


def _line(w: dict[str, Any]) -> str:
    parts = [f'"{w["title"]}" - {w["views"]:,} {w.get("unit") or "views"}']
    parts += [p for p in (w["domain"], w["format"]) if p]
    if w["hook"]:
        parts.append(f'hook: "{w["hook"]}"')
    return " · ".join(parts)


def winners_block(channel_id: str) -> str:
    """The script prompt's block, or "" below the floor or when switched off."""
    if not _enabled():
        return ""
    try:
        top = winners(channel_id)
    except Exception as exc:
        logger.debug("winners block skipped: %s", exc)
        return ""
    if not top:
        return ""
    lines = "\n".join(f"- {_line(w)}" for w in top)
    return (
        "WHAT WORKS ON THIS CHANNEL (your top videos by views - learn what made them land: "
        "the hook's shape, the length, the subject. Never copy their words, and never take "
        "a fact from them):\n" + lines
    )


def winners_lines(channel_id: str) -> list[str]:
    """`ops winners`."""
    count = measured_count(channel_id)
    top = winners(channel_id)
    if not top:
        return [
            f"Winners - {channel_id}: {count} measured video(s); the library needs "
            f"{WINNERS_MIN_MEASURED} before a top video means anything."
        ]
    state = "in the script prompt" if _enabled() else "off (WINNERS_IN_PROMPT=false)"
    _ranked_list, heading, _unit = _ranked(channel_id)
    lines = [
        f"Winners - {channel_id}: top {len(top)} of {count} measured videos by {heading} ({state})"
    ]
    lines += [f"  {i}. {_line(w)}" for i, w in enumerate(top, 1)]
    return lines
