"""#1541: is our thumbnail the one YouTube shows?

The Data API cannot say which image is live (#1391): `snippet.thumbnails` lists the same
`*default.jpg` names for a custom image and for YouTube's own frame (#1540, run 180). The live
image itself is public at `i.ytimg.com/vi/<id>/hqdefault.jpg` - no quota - letterboxed for a
vertical Short. This cuts the black bars and compares a difference hash of it with the file we
uploaded: close enough means ours is live.
"""

from __future__ import annotations

import io
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("youtube.thumbnail_check")

_LIVE_URL = "https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
_HASH_SIZE = 8
_MAX_DISTANCE = 12  # of 64 bits: a re-encoded, letterboxed copy of the same image


def _fetch_live(video_id: str) -> bytes | None:
    """The live thumbnail's bytes, or None. No YouTube quota; 10 s."""
    try:
        with urllib.request.urlopen(_LIVE_URL.format(video_id=video_id), timeout=10) as resp:
            return resp.read()
    except Exception as exc:
        logger.debug("live thumbnail unread for %s: %s", video_id, exc)
        return None


def _cut_letterbox(image: Any) -> Any:
    """The image without the black side bars YouTube adds around a vertical thumbnail."""
    gray = image.convert("L")
    width, height = gray.size
    columns = [sum(gray.getpixel((x, y)) for y in range(0, height, 8)) for x in range(width)]
    rows = max(1, len(range(0, height, 8)))
    lit = [x for x, total in enumerate(columns) if total / rows > 18]
    if not lit:
        return image
    return image.crop((lit[0], 0, lit[-1] + 1, height))


def _dhash(image: Any) -> int:
    small = image.convert("L").resize((_HASH_SIZE + 1, _HASH_SIZE))
    bits = 0
    for y in range(_HASH_SIZE):
        for x in range(_HASH_SIZE):
            bits = (bits << 1) | int(small.getpixel((x, y)) > small.getpixel((x + 1, y)))
    return bits


def same_image(ours: Any, live: Any) -> bool:
    """True when the live (letterboxed) thumbnail is our image."""
    distance = bin(_dhash(ours) ^ _dhash(_cut_letterbox(live))).count("1")
    return distance <= _MAX_DISTANCE


def check_video(video_id: str, ours: Any) -> str:
    """ "ours", "another image" or "unread"."""
    raw = _fetch_live(video_id)
    if not raw:
        return "unread"
    try:
        from PIL import Image

        live = Image.open(io.BytesIO(raw))
        live.load()
    except Exception as exc:
        logger.debug("live thumbnail unreadable for %s: %s", video_id, exc)
        return "unread"
    return "ours" if same_image(ours, live) else "another image"


def _uploaded_thumbnail(run_id: int) -> str | None:
    """The thumbnail file recorded for the run - never a new one (`resolve_thumbnail_path` may
    make one)."""
    try:
        from storage.repositories.assets import get_asset_repository

        for asset in get_asset_repository().list_for_run(run_id):
            if asset.asset_type == "thumbnail" and asset.path and os.path.isfile(asset.path):
                return str(asset.path)
    except Exception as exc:
        logger.debug("thumbnail asset unread for run %s: %s", run_id, exc)
    return None


def recent_lines(channel_id: str, *, days: int = 7) -> list[str]:
    """`ops thumbnail-check`: each upload of the last `days` - whether its thumbnail is live."""
    from PIL import Image

    from storage.repositories.publish_log import get_publish_log_repository

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = [
        r
        for r in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
        if r.youtube_video_id and r.content_run_id and getattr(r, "published_at", None)
    ]
    seen: set[str] = set()
    out = [f"Thumbnails - {channel_id}: the live image against ours, the last {days} days"]
    counts: dict[str, int] = {}
    for row in sorted(rows, key=lambda r: str(r.published_at), reverse=True):
        published, run_id = row.published_at, row.content_run_id
        if published is None or run_id is None:
            continue
        when = published if published.tzinfo else published.replace(tzinfo=timezone.utc)
        if when < cutoff or row.youtube_video_id in seen:
            continue
        seen.add(row.youtube_video_id)
        path = _uploaded_thumbnail(int(run_id))
        if not path:
            verdict = "no thumbnail of ours on record"
        else:
            with Image.open(path) as ours:
                ours.load()
                verdict = check_video(str(row.youtube_video_id), ours)
        counts[verdict] = counts.get(verdict, 0) + 1
        out.append(f"  run {row.content_run_id} {row.youtube_video_id}: {verdict}")
    if len(out) == 1:
        out.append("  no uploads in that time")
    else:
        out.append("  " + ", ".join(f"{n} {v}" for v, n in sorted(counts.items())))
    return out
