"""The Buffer pack: each rendered video ready for TikTok and Instagram (#968).

Operator, 2026-10-05: "i got buffer". Buffer schedules TikToks and Instagram Reels and posts
them with the PC off, so Content OS needs no app, token or review on either platform - it
hands over, per rendered video, one folder:

- `video.mp4` - the render, as uploaded to YouTube;
- `tiktok.txt`, `instagram.txt` - the caption to paste: the title, the description without
  its footer, 3-5 hashtags from the tags, and the AI-disclosure line (Buffer has no AI-label
  field; the platforms' own toggles are named in `slot.txt`);
- `slot.txt` - the YouTube slot when the run has one, a suggested slot otherwise, and what
  to switch on in Buffer's composer.

A Reel longer than `INSTAGRAM_MAX_SECONDS` (90) is named in `instagram.txt` instead of a
caption. What was packed and what the operator marked posted is kept in
`data/crosspost_<channel>.json` - not in the publish log, whose readers all assume YouTube.

    py -m scripts.ops crosspost              pack the newest rendered videos not packed yet
    py -m scripts.ops crosspost list         packed, not marked posted
    py -m scripts.ops crosspost done --run-id N
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("publishing.crosspost")

CROSSPOST_TEMPLATE = os.path.join(DATA_DIR, "crosspost_{channel}.json")
CAPTION_MAX = 2200
_DEFAULT_DISCLOSURE = "Made with AI-assisted narration and editing."
_PACK_LIMIT = 5
_FOOTER_RE = re.compile(r"\n\s*\n.*$", re.S)


@dataclass
class Packed:
    run_id: int
    folder: str
    reel_ok: bool


def reel_max_seconds() -> float:
    try:
        return float(os.getenv("INSTAGRAM_MAX_SECONDS", "90") or 90)
    except ValueError:
        return 90.0


def _store_path(channel_id: str) -> str:
    return CROSSPOST_TEMPLATE.format(channel=channel_id)


def _load(channel_id: str) -> dict[str, Any]:
    try:
        with open(_store_path(channel_id), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(channel_id: str, data: dict[str, Any]) -> None:
    path = _store_path(channel_id)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _pack_root(channel_id: str) -> str:
    from core.output_paths import channel_output_root

    return os.path.join(channel_output_root(channel_id), "crosspost")


def _rendered_runs(channel_id: str) -> list[Any]:
    """Runs with a rendered mp4 on disk, newest first."""
    from storage.repositories.content_runs import get_content_run_repository

    runs = get_content_run_repository().list_for_channel(channel_id)
    return sorted(runs, key=lambda r: int(r.id or 0), reverse=True)


def _duration(path: str) -> float | None:
    from video.channel_intro import _probe_duration

    return _probe_duration(path)


def _suggested_slot(channel_id: str, topic: str) -> datetime:
    from analytics.post_timing import next_optimal_post_time

    return next_optimal_post_time(channel_id, topic)


def _youtube_slot(channel_id: str, run_id: int) -> datetime | None:
    try:
        from publishing.idempotency import idempotency_key
        from storage.repositories.publish_log import get_publish_log_repository

        key = idempotency_key(run_id, channel_id)
        row = get_publish_log_repository().find_by_idempotency(key) if key else None
    except Exception as exc:
        logger.debug("youtube slot for run %s unavailable: %s", run_id, exc)
        return None
    return getattr(row, "published_at", None) if row else None


def hashtags(tags: list[str], *, limit: int = 5) -> list[str]:
    """ "NBA preseason" -> "#NBApreseason": up to `limit`, deduplicated, in order."""
    out: list[str] = []
    for tag in tags:
        word = re.sub(r"[^0-9A-Za-z]", "", str(tag or ""))
        if len(word) < 3 or word[0].isdigit():
            continue
        tagged = f"#{word}"
        if tagged.lower() not in (t.lower() for t in out):
            out.append(tagged)
        if len(out) >= limit:
            break
    return out


def _disclosure() -> str:
    return os.getenv("AI_CONTENT_DISCLOSURE_LABEL", "").strip() or _DEFAULT_DISCLOSURE


def caption(run: Any) -> str:
    """Title, the description without its footer, the hashtags and the disclosure line."""
    try:
        tags = json.loads(getattr(run, "tags_json", "") or "[]")
    except (TypeError, ValueError):
        tags = []
    body = _FOOTER_RE.sub("", str(getattr(run, "description", "") or "").strip()).strip()
    title = str(getattr(run, "title", "") or getattr(run, "selected_topic", "") or "").strip()
    parts = [p for p in (title, body, " ".join(hashtags(list(tags or []))), _disclosure()) if p]
    text = "\n\n".join(parts)
    return text if len(text) <= CAPTION_MAX else text[: CAPTION_MAX - 1].rstrip() + "…"


def _local(when: datetime, channel_id: str) -> str:
    try:
        from analytics.post_timing import format_scheduled_local

        return format_scheduled_local(when, channel_id)
    except Exception:
        return when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _slug(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", (text or "").lower()).strip("_")[:40] or "video"


def pack_run(channel_id: str, run: Any) -> Packed:
    """Write one run's folder; returns where and whether it can be a Reel."""
    stamp = datetime.now().strftime("%Y%m%d")
    folder = os.path.join(
        _pack_root(channel_id), f"{stamp}_{_slug(getattr(run, 'title', ''))}_run{run.id}"
    )
    os.makedirs(folder, exist_ok=True)
    shutil.copyfile(run.mp4_path, os.path.join(folder, "video.mp4"))
    text = caption(run)
    seconds = _duration(run.mp4_path)
    limit = reel_max_seconds()
    reel_ok = seconds is None or seconds <= limit
    with open(os.path.join(folder, "tiktok.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    with open(os.path.join(folder, "instagram.txt"), "w", encoding="utf-8") as f:
        if reel_ok:
            f.write(text + "\n")
        else:
            f.write(
                f"Not a Reel: this video is {seconds:.0f}s and Instagram Reels posted through "
                f"Buffer take up to {limit:.0f}s. Post it to TikTok only, or render a shorter cut.\n"
            )
    topic = str(getattr(run, "input_topic", "") or getattr(run, "selected_topic", "") or "")
    youtube = _youtube_slot(channel_id, int(run.id))
    suggested = youtube or _suggested_slot(channel_id, topic)
    lines = [
        f"Run {run.id}: {getattr(run, 'title', '')}",
        f"YouTube: {_local(youtube, channel_id)}" if youtube else "YouTube: not scheduled yet",
        f"Suggested TikTok / Instagram time: {_local(suggested, channel_id)}",
        "",
        "In Buffer: add video.mp4, paste tiktok.txt for TikTok and instagram.txt for Instagram.",
        "Switch on each platform's AI-generated content label where Buffer's composer offers it;",
        "the captions carry the disclosure line either way.",
        f"Then: py -m scripts.ops crosspost done --run-id {run.id}",
    ]
    with open(os.path.join(folder, "slot.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return Packed(run_id=int(run.id), folder=folder, reel_ok=reel_ok)


def pack_new(channel_id: str, *, limit: int = _PACK_LIMIT) -> list[Packed]:
    """Pack the newest rendered runs not packed before (at most `limit`)."""
    data = _load(channel_id)
    done = data.setdefault("runs", {})
    packed: list[Packed] = []
    for run in _rendered_runs(channel_id):
        if len(packed) >= limit:
            break
        path = str(getattr(run, "mp4_path", "") or "")
        if str(run.id) in done or not path or not os.path.isfile(path):
            continue
        result = pack_run(channel_id, run)
        done[str(run.id)] = {
            "folder": result.folder,
            "packed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "title": str(getattr(run, "title", "") or ""),
            "reel_ok": result.reel_ok,
            "posted": "",
        }
        packed.append(result)
    if packed:
        _save(channel_id, data)
    return packed


def mark_posted(channel_id: str, run_id: int) -> bool:
    data = _load(channel_id)
    entry = (data.get("runs") or {}).get(str(run_id))
    if not isinstance(entry, dict):
        return False
    entry["posted"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _save(channel_id, data)
    return True


def waiting_lines(channel_id: str) -> list[str]:
    """Packed and not yet marked posted, oldest first."""
    runs = (_load(channel_id).get("runs") or {}).items()
    waiting = [(rid, e) for rid, e in runs if isinstance(e, dict) and not e.get("posted")]
    if not waiting:
        return [f"Crosspost - {channel_id}: nothing packed is waiting to be posted."]
    lines = [f"Crosspost - {channel_id}: {len(waiting)} packed, not marked posted"]
    for rid, entry in sorted(waiting, key=lambda item: str(item[1].get("packed") or "")):
        reel = "" if entry.get("reel_ok", True) else "  (TikTok only - too long for a Reel)"
        lines.append(f"  run {rid}: {entry.get('title', '')}{reel}")
        lines.append(f"    {entry.get('folder', '')}")
    return lines
