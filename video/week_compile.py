"""#138 (the operator, 2026-10-18: "Shorts compilation, $0"): the week's Shorts as one long video.

Long-form watch hours were 10 of the 4,000 the Partner Program needs, and every video is a
Short. Each week the Shorts that went public in the last seven days become one 16:9 video: each
Short centred on a blurred copy of itself, its channel intro trimmed so it plays once a video
rather than once a chapter, a chapter each in the description. No new script, voice or footage -
$0 and one ffmpeg pass a Short.

`ops week-compile` is a dry run by default; `--apply` renders to output/<channel>/week/ and
records a run; `--apply --schedule` also queues it public at the next free slot (the slot rule).
Overnight does both on Monday mornings (`WEEK_COMPILE`, on by default; the suite pins it off).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("video.week_compile")

MIN_SHORTS = 5  # fewer is not worth a long video; YouTube's chapters need 3 of 10 s or more
_MAX_SHORT_SECONDS = 185.0  # a long video already on the channel is not a Short
_WIDTH, _HEIGHT = 1920, 1080
_SEGMENT_TIMEOUT = 600


@dataclass
class WeekPlan:
    channel_id: str
    week: str  # the Monday it is made, YYYY-MM-DD - one compilation a week
    title: str
    description: str
    items: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _run(run_id: int) -> Any:
    from storage.repositories.content_runs import get_content_run_repository

    try:
        return get_content_run_repository().get(int(run_id))
    except Exception as exc:
        logger.debug("week compile: run %s unread: %s", run_id, exc)
        return None


def _duration(path: str) -> float | None:
    from video.channel_intro import _probe_duration

    return _probe_duration(path)


def _intro_offset(channel_id: str) -> float:
    try:
        from config.channels import get_channel_profile

        return float(get_channel_profile(channel_id).intro_offset_seconds or 0.0)
    except Exception:
        return 0.0


def _features(run: Any) -> dict[str, Any]:
    try:
        data = json.loads(getattr(run, "features_json", "") or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def week_shorts(channel_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """The Shorts that went public in the seven days before `now`, oldest first, with a file on
    disk - not a held one, not an earlier compilation."""
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    moment = _now(now)
    since = moment - timedelta(days=7)
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        run_id = getattr(row, "content_run_id", None)
        when = getattr(row, "published_at", None)
        if not run_id or when is None or is_seeded(row):
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if str(getattr(row, "privacy_status", "") or "").lower() != "public":
            continue
        if not since < when <= moment or int(run_id) in seen:
            continue
        run = _run(int(run_id))
        path = str(getattr(run, "mp4_path", "") or "") if run is not None else ""
        if not path or not os.path.isfile(path) or _features(run).get("compilation"):
            continue
        seen.add(int(run_id))
        out.append({"run_id": int(run_id), "title": str(getattr(run, "title", "") or ""),
                    "path": path, "published_at": when})  # fmt: skip
    return sorted(out, key=lambda s: s["published_at"])


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600}:{whole % 3600 // 60:02d}:{whole % 60:02d}" if whole >= 3600 else (
        f"{whole // 60}:{whole % 60:02d}"
    )  # fmt: skip


def plan_week(channel_id: str, *, now: datetime | None = None) -> WeekPlan | None:
    """The week's compilation - its title, chapters and parts - or None under MIN_SHORTS."""
    moment = _now(now)
    offset = _intro_offset(channel_id)
    items: list[dict[str, Any]] = []
    for short in week_shorts(channel_id, now=moment):
        length = _duration(short["path"])
        if not length or length > _MAX_SHORT_SECONDS or length - offset < 10:
            continue
        items.append({**short, "seconds": float(length) - offset})
    if len(items) < MIN_SHORTS:
        return None
    try:
        from config.channels import get_channel_profile

        name = str(get_channel_profile(channel_id).name or channel_id)
    except Exception:
        name = channel_id
    first, last = items[0]["published_at"], items[-1]["published_at"]
    span = f"{first:%b %d} - {last:%b %d}".replace(" 0", " ")
    chapters, at = [], 0.0
    for item in items:
        chapters.append(f"{_clock(at)} {item['title']}")
        item["start"] = at
        at += item["seconds"]
    monday = (moment - timedelta(days=moment.weekday())).date().isoformat()
    description = f"Every {name} Short from {span}, in one place.\n\n" + "\n".join(chapters) + "\n"
    return WeekPlan(channel_id=channel_id, week=monday, title=f"{name} Week in Review: {span}",
                    description=description, items=items, seconds=at)  # fmt: skip


def segment_argv(src: str, dst: str, *, offset: float) -> list[str]:
    """One Short as a 1920x1080 part: centred on a blurred, filled copy of itself, from `offset`
    (past the channel intro), 30 fps, the same codecs every part so they join without re-encoding."""
    graph = (
        f"[0:v]scale={_WIDTH}:{_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={_WIDTH}:{_HEIGHT},boxblur=20:5[bg];"
        f"[0:v]scale=-2:{_HEIGHT}[fg];"
        "[bg][fg]overlay=(W-w)/2:0,fps=30,format=yuv420p[v]"
    )
    return [
        "ffmpeg", "-nostdin", "-y", "-ss", str(offset), "-i", src,
        "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", dst,
    ]  # fmt: skip


def concat_argv(list_file: str, dst: str) -> list[str]:
    return ["ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy", "-movflags", "+faststart", dst]  # fmt: skip


def _out_path(channel_id: str, week: str) -> str:
    from config.paths import ROOT_DIR

    return os.path.join(ROOT_DIR, "output", channel_id, "week", f"week_{week}.mp4")


def week_done(channel_id: str, week: str) -> bool:
    """A compilation for this week is already a run."""
    from storage.repositories.content_runs import get_content_run_repository

    try:
        runs = get_content_run_repository().list_for_channel(channel_id)[:40]
    except Exception:
        return False
    return any((_features(r).get("compilation") or {}).get("week") == week for r in runs)


def _render(plan: WeekPlan, dst: str) -> str:
    """ "" when the file was written, else why not."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    offset = _intro_offset(plan.channel_id)
    with tempfile.TemporaryDirectory(prefix="cm_week_") as tmp:
        parts = []
        for index, item in enumerate(plan.items):
            part = os.path.join(tmp, f"part{index:02d}.mp4")
            done = subprocess.run(segment_argv(item["path"], part, offset=offset),
                                  capture_output=True, stdin=subprocess.DEVNULL,
                                  timeout=_SEGMENT_TIMEOUT, check=False)  # fmt: skip
            if done.returncode != 0 or not os.path.isfile(part):
                return f"run {item['run_id']} did not encode (ffmpeg exit {done.returncode})"
            parts.append(part)
        listing = os.path.join(tmp, "parts.txt")
        with open(listing, "w", encoding="utf-8") as handle:
            for part in parts:
                handle.write(f"file '{part.replace(os.sep, '/')}'\n")
        done = subprocess.run(concat_argv(listing, dst), capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=_SEGMENT_TIMEOUT, check=False)  # fmt: skip
        if done.returncode != 0 or not os.path.isfile(dst):
            return f"the parts did not join (ffmpeg exit {done.returncode})"
    return ""


def _record(plan: WeekPlan, path: str) -> int:
    from core.run_recorder import record_content_run

    return record_content_run(
        channel_id=plan.channel_id,
        input_topic=plan.title,
        selected_topic=plan.title,
        status="rendered",
        composite_score=0.0,
        signals={},
        variants=[],
        title=plan.title,
        description=plan.description,
        tags_json=json.dumps(["week in review", "compilation"]),
        mp4_path=path,
        features={
            "compilation": {
                "week": plan.week,
                "runs": [i["run_id"] for i in plan.items],
                "seconds": round(plan.seconds, 1),
            }
        },
    )


def compile_week(
    channel_id: str, *, apply: bool = False, queue: bool = False, now: datetime | None = None
) -> list[str]:
    """What the week's compilation is - and with `apply` it rendered and recorded, with `queue`
    also queued public at the next free slot. Lines for the operator."""
    plan = plan_week(channel_id, now=now)
    if plan is None:
        count = len(week_shorts(channel_id, now=now))
        return [f"  Week compilation: {count} public Short(s) this week - it needs {MIN_SHORTS}."]
    if week_done(channel_id, plan.week):
        return [f"  Week compilation: the week of {plan.week} is already made."]
    lines = [f"  Week compilation: {plan.title} - {len(plan.items)} Shorts, {_clock(plan.seconds)}"]
    lines += [f"    {line}" for line in plan.description.strip().splitlines()[2:]]
    if not apply:
        return [*lines, "  Dry run - --apply renders it ($0, one ffmpeg pass a Short)."]
    dst = _out_path(channel_id, plan.week)
    why = _render(plan, dst)
    if why:
        return [*lines, f"  Not made: {why}."]
    run_id = _record(plan, dst)
    lines.append(f"  Rendered: {dst} (run {run_id})")
    if not queue:
        return [
            *lines,
            f"  Queue it: py -m scripts.ops week-compile --channel {channel_id} --apply --schedule",
        ]
    from core.spaced_queue import SpacedSlot, queue_spaced_uploads, slot_for_run

    when, slot_why = slot_for_run(channel_id, run_id, title=plan.title)
    if when is None:
        return [*lines, f"  Not queued: {slot_why}."]
    queued = queue_spaced_uploads(
        [SpacedSlot(run_id=run_id, title=plan.title, publish_at=when)], channel_id=channel_id
    )
    if not queued:
        return [*lines, "  Not queued (see the log)."]
    from analytics.post_timing import format_scheduled_local

    return [*lines, f"  Queued: public {format_scheduled_local(when, channel_id)}"]
