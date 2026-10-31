"""Every clip in rotation, and what each clip did (look_and_feel.md L3 + L4, wave 135).

Read on 899ff58: a folder's clips were listed by file name and the fast cut took at most 12; the
"recently used" memory held 8 clips of one process unless CLIP_MEMORY was on - so videos rendered
in different runs drew from the same first files, and two GTA 6 Shorts opened on one dark car.

This ledger is on disk and always on: each clip's use times (`data/clip_uses.json`). The fast
cut's pool is the clips used least recently - never used first - so a folder of 30 shows all 30
before any is used a third time. `report_lines` is `ops footage`'s per-folder use in 30 days.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.clip_ledger")

_KEEP = 20  # use times kept per clip


def _file() -> str:
    from config import paths

    return paths.CLIP_USES_FILE


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def uses() -> dict[str, list[str]]:
    """{clip: [ISO times it was used]}, {} when unread."""
    try:
        with open(_file(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    rows = data.get("clips") if isinstance(data, dict) else None
    return {str(k): [str(t) for t in v] for k, v in (rows or {}).items() if isinstance(v, list)}


def record_uses(clips: list[str], *, when: datetime | None = None) -> None:
    """Stamp each clip once for this video. Fail-open."""
    stamp = (when or datetime.now(timezone.utc)).isoformat()
    try:
        data = uses()
        for clip in dict.fromkeys(_norm(c) for c in clips if c):
            data[clip] = [*data.get(clip, []), stamp][-_KEEP:]
        path = _file()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"clips": data}, handle)
        os.replace(tmp, path)
    except Exception as exc:
        logger.debug("clip uses not recorded: %s", exc)


def least_used(clips: list[str], limit: int) -> list[str]:
    """L3: up to `limit` clips - the fewest uses first (never used before all), then the
    longest since their last use; the file name only breaks ties."""
    seen = uses()

    def key(clip: str) -> tuple[int, str, str]:
        times = seen.get(_norm(clip)) or []
        return (len(times), max(times) if times else "", os.path.basename(clip).lower())

    return sorted(clips, key=key)[:limit]


def folder_rows(
    folders: list[str], *, now: datetime | None = None, days: int = 30
) -> list[dict[str, Any]]:
    """L4: per folder - its clips, the uses in `days`, the clips never used, the most used."""
    moment = now or datetime.now(timezone.utc)
    since = (moment - timedelta(days=days)).isoformat()
    seen = uses()
    rows: list[dict[str, Any]] = []
    for folder in folders:
        try:
            names = sorted(f for f in os.listdir(folder) if f.lower().endswith((".mp4", ".mov")))
        except OSError:
            continue
        counts = {n: sum(1 for t in seen.get(_norm(os.path.join(folder, n)), []) if t >= since)
                  for n in names}  # fmt: skip
        ever = {n for n in names if seen.get(_norm(os.path.join(folder, n)))}
        top = max(counts.items(), key=lambda kv: kv[1]) if counts else ("", 0)
        rows.append({
            "folder": os.path.basename(folder), "clips": len(names),
            "uses": sum(counts.values()), "never": [n for n in names if n not in ever],
            "most": top if top[1] else ("", 0),
        })  # fmt: skip
    return rows


def report_lines(folders: list[str], *, now: datetime | None = None) -> list[str]:
    lines = ["Clip use in 30 days (L4) - every clip plays before any repeats (L3):"]
    for row in folder_rows(folders, now=now):
        line = f"  {row['folder']:<26} {row['clips']:>3} clips, {row['uses']:>3} uses"
        if row["never"]:
            line += f", {len(row['never'])} never used"
        if row["most"][1] >= 3:
            line += f"; most: {row['most'][0][:40]} ({row['most'][1]})"
        lines.append(line)
    return lines
