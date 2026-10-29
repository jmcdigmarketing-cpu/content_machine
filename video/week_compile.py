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
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("video.week_compile")

MIN_SHORTS = 5  # fewer is not worth a long video; YouTube's chapters need 3 of 10 s or more
_MAX_SHORT_SECONDS = 185.0  # a long video already on the channel is not a Short
# #1592 (decision 81, the operator: "cover all topics ... as well as a deeper dive on the top 3.
# maybe 5-8 mins long not 11"): the week's other Shorts as their openings, then the top 3 whole.
DEEP_DIVES = 3
TARGET_MIN_S, TARGET_MAX_S = 300.0, 480.0
CLIP_MIN_S, CLIP_MAX_S = 12.0, 25.0
_CHAPTER_MIN_S = 10.0  # YouTube's shortest chapter
_CUT_TAIL_S = 0.3  # past the last word's end, so it is not clipped
_SENTENCE_END = (".", "!", "?")
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
        from video.hook_copy import hook_offset, run_opening

        # #1592: the voice's word timings, for a rundown clip that ends at a sentence
        audio = str(getattr(run, "mp3_path", "") or "")
        words = audio + ".words.json" if audio and os.path.isfile(audio + ".words.json") else ""
        # #1419 (wave 113): the run's own intro - a Short rendered without it lost 2.15 s of hook
        out.append({"run_id": int(run_id), "title": str(getattr(run, "title", "") or ""),
                    "words": words,
                    "path": path, "published_at": when,
                    "offset": hook_offset(run_opening(run), channel_id,
                                          default=_intro_offset(channel_id)),
                    # #1316 (wave 120): what the compilation's title names, and in which order
                    "names": list((_features(run).get("entity_research") or {}).get("names") or []),
                    "views": _organic_views(getattr(row, "metrics_json", None))})  # fmt: skip
    return sorted(out, key=lambda s: s["published_at"])


def _organic_views(metrics_json: Any) -> int:
    """The window's views less the paid ones - ads say nothing about what people look for -
    or the lifetime count when the window has not synced."""
    from core.ypp_readiness import _organic_views as window_organic

    try:
        metrics = json.loads(metrics_json or "{}") or {}
        if metrics.get("views") is not None:
            return int(window_organic(metrics))
        return int(metrics.get("lifetime_views") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def subject_name(title: str, names: list[str]) -> str:
    """#1316: the name a Short is about - the researched name that comes first in its title,
    a team by its last word ("Kansas City Chiefs" -> "Chiefs") when only that is in it, with a
    number that follows it ("GTA 6"); the title's first name when research named none of it."""
    from apis.topic_tokens import title_phrases

    found: list[tuple[int, int, str]] = []
    for raw in names:
        name = re.sub(r"(?:'s|')$", "", str(raw).strip())
        if not name:
            continue
        for form in (name, name.split()[-1]):
            if form != name and len(form) < 4 and not any(c.isdigit() for c in form):
                continue
            hit = re.search(rf"(?<!\w){re.escape(form)}(?!\w)", title, flags=re.I)
            if hit:
                number = re.match(r"\s+(\d+)\b", title[hit.end() :])
                found.append(
                    (hit.start(), -len(form), form + (f" {number.group(1)}" if number else ""))
                )
                break
    if found:
        return min(found)[2]
    phrases = title_phrases(title, max_words=2)
    return re.sub(r"(?:'s|')$", "", phrases[0]) if phrases else ""


def compilation_title(
    name: str, items: list[dict[str, Any]], span: str, *, limit: int = 100
) -> str:
    """#1316: "Pereira, Mahomes & GTA 6 - TapIn Week in Review (Oct 19-25)" - the most-viewed
    Shorts' names, within YouTube's 100 characters; the dates alone when none is named."""
    ordered = sorted(enumerate(items), key=lambda pair: (-int(pair[1].get("views") or 0), pair[0]))
    chosen: list[str] = []
    for _i, item in ordered:
        subject = subject_name(str(item.get("title") or ""), list(item.get("names") or []))
        low = subject.lower()
        if subject and not any(low in c.lower() or c.lower() in low for c in chosen):
            chosen.append(subject)
        if len(chosen) == 3:
            break
    while chosen:
        named = ", ".join(chosen[:-1]) + f" & {chosen[-1]}" if len(chosen) > 1 else chosen[0]
        title = f"{named} - {name} Week in Review ({span})"
        if len(title) <= limit:
            return title
        chosen.pop()
    return f"{name} Week in Review ({span})"[:limit]


def short_span(began: datetime, ended: datetime) -> str:
    """ "Oct 15-18", or "Oct 28-Nov 3" across a month."""
    if began.month == ended.month:
        return f"{began:%b} {began.day}-{ended.day}"
    return f"{began:%b} {began.day}-{ended:%b} {ended.day}"


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600}:{whole % 3600 // 60:02d}:{whole % 60:02d}" if whole >= 3600 else (
        f"{whole // 60}:{whole % 60:02d}"
    )  # fmt: skip


def sentence_cut(words_path: str, target: float, whole: float) -> float:
    """#1592: where a rundown clip ends - the end of the sentence nearest `target` seconds into
    the voice (a `.words.json` word ending in . ! or ?), plus a short tail; at least a chapter's
    10 s and at most the Short. No sidecar, or no sentence end in reach: the target itself."""
    goal = min(float(target), float(whole))
    ends: list[float] = []
    if words_path:
        try:
            with open(words_path, encoding="utf-8") as handle:
                words = json.load(handle)
        except (OSError, ValueError) as exc:
            logger.debug("week compile: words unread %s: %s", words_path, exc)
            words = []
        for word in words if isinstance(words, list) else []:
            text = str((word or {}).get("word") or "").rstrip("\"')]”’")
            try:
                end = float(word.get("end")) + _CUT_TAIL_S
            except (TypeError, ValueError):
                continue
            if text.endswith(_SENTENCE_END) and _CHAPTER_MIN_S <= end <= whole:
                ends.append(end)
    cut = min(ends, key=lambda e: (abs(e - goal), e)) if ends else goal
    return round(max(_CHAPTER_MIN_S, min(cut, float(whole))), 2)


def plan_clips(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """#1592 (decision 81): the rundown - every Short but the week's top 3 by organic views, in
    publish order, each its opening cut at a sentence - then the top 3 whole, counted down #3,
    #2, #1. Clips are (480 s - the deep dives) shared out, 12-25 s each; under 300 s they grow
    (to the whole Short at most); still over 480 s at 12 s, the least-watched rundown items go.
    Each item gets `seconds` (what it plays), `clip` (the cut, None for whole) and `deep`."""
    ranked = sorted(range(len(items)), key=lambda i: (-int(items[i].get("views") or 0), i))
    top = ranked[:DEEP_DIVES]
    deep = [{**items[i], "deep": rank, "clip": None} for rank, i in enumerate(top, 1)]
    rundown = [{**items[i], "deep": 0} for i in range(len(items)) if i not in top]
    deep_s = sum(float(d["seconds"]) for d in deep)
    while rundown and deep_s + len(rundown) * CLIP_MIN_S > TARGET_MAX_S:
        rundown.remove(min(rundown, key=lambda r: int(r.get("views") or 0)))
    if rundown:
        target = min(CLIP_MAX_S, max(CLIP_MIN_S, (TARGET_MAX_S - deep_s) / len(rundown)))
        if deep_s + target * len(rundown) < TARGET_MIN_S:
            target = (TARGET_MIN_S - deep_s) / len(rundown)
        for item in rundown:
            whole = float(item["seconds"])
            cut = sentence_cut(str(item.get("words") or ""), target, whole)
            item["clip"] = None if cut >= whole else cut
            item["seconds"] = cut
    return [*rundown, *sorted(deep, key=lambda d: -d["deep"])]


def plan_week(channel_id: str, *, now: datetime | None = None) -> WeekPlan | None:
    """The week's compilation - its title, chapters and parts - or None under MIN_SHORTS."""
    moment = _now(now)
    offset = _intro_offset(channel_id)
    items: list[dict[str, Any]] = []
    for short in week_shorts(channel_id, now=moment):
        length = _duration(short["path"])
        cut = float(short.get("offset", offset))
        if not length or length > _MAX_SHORT_SECONDS or length - cut < 10:
            continue
        items.append({**short, "offset": cut, "seconds": float(length) - cut})
    if len(items) < MIN_SHORTS:
        return None
    try:
        from config.channels import get_channel_profile

        name = str(get_channel_profile(channel_id).name or channel_id)
    except Exception:
        name = channel_id
    first, last = items[0]["published_at"], items[-1]["published_at"]
    items = plan_clips(items)  # #1592: the rundown, then the top 3 counted down
    chapters, at = [], 0.0
    for item in items:
        label = f"Deep dive #{item['deep']}: {item['title']}" if item.get("deep") else item["title"]
        chapters.append(f"{_clock(at)} {label}")
        item["start"] = at
        at += item["seconds"]
    monday = (moment - timedelta(days=moment.weekday())).date().isoformat()
    deep_count = sum(1 for item in items if item.get("deep"))
    description = (
        f"Every {name} story from {short_span(first, last)}, then the week's top {deep_count} "
        "in full.\n\n" + "\n".join(chapters) + "\n"
    )
    # #1522 (live 2026-10-19): the first compilation was scheduled public without the AI
    # disclosure every other upload carries - this description is built here, not by the SEO path.
    try:
        from core.description_extras import ai_disclosure_line

        disclosure = ai_disclosure_line(channel_id)
    except Exception as exc:
        logger.debug("week compile disclosure unread: %s", exc)
        disclosure = ""
    if disclosure:
        description += f"\n{disclosure}\n"
    title = compilation_title(name, items, short_span(first, last))
    return WeekPlan(channel_id=channel_id, week=monday, title=title,
                    description=description, items=items, seconds=at)  # fmt: skip


def segment_argv(src: str, dst: str, *, offset: float, duration: float | None = None) -> list[str]:
    """One Short as a 1920x1080 part: centred on a blurred, filled copy of itself, from `offset`
    (past the channel intro), 30 fps, the same codecs every part so they join without re-encoding.
    ``duration`` (#1592): a rundown clip's length; None plays the Short to its end."""
    graph = (
        f"[0:v]scale={_WIDTH}:{_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={_WIDTH}:{_HEIGHT},boxblur=20:5[bg];"
        f"[0:v]scale=-2:{_HEIGHT}[fg];"
        "[bg][fg]overlay=(W-w)/2:0,fps=30,format=yuv420p[v]"
    )
    length = ["-t", str(duration)] if duration else []
    return [
        "ffmpeg", "-nostdin", "-y", "-ss", str(offset), "-i", src, *length,
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


def latest_public_compilation(channel_id: str) -> str:
    """#1317: the YouTube id of the newest compilation that is public, or "" - a Short links it
    ("Full week: ..."), so a Shorts viewer can reach the long video."""
    try:
        from storage.repositories.content_runs import get_content_run_repository
        from storage.repositories.publish_log import get_publish_log_repository

        runs = get_content_run_repository()
        best = None
        for row in get_publish_log_repository().list_uploaded_for_channel(channel_id):
            if (
                str(getattr(row, "privacy_status", "") or "") != "public"
                or not row.youtube_video_id
            ):
                continue
            if not _features(runs.get(int(row.content_run_id or 0))).get("compilation"):
                continue
            when = getattr(row, "published_at", None)
            if best is None or (when and best[0] and when > best[0]):
                best = (when, str(row.youtube_video_id))
    except Exception as exc:
        logger.debug("latest compilation unread: %s", exc)
        return ""
    return best[1] if best else ""


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
            cut = float(item.get("offset", offset))
            done = subprocess.run(segment_argv(item["path"], part, offset=cut,
                                               duration=item.get("clip")),
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


def make_thumbnail(plan: WeekPlan, video_path: str) -> str:
    """Wave 112: the compilation's own thumbnail - a frame 40% into its first chapter with "Week
    in Review" and the dates painted on (`compose_thumbnail`, its contrast rules). "" when none."""
    if not plan.items:
        return ""
    # #1592: the week's most-watched Short (deep dive #1), the subject the title names first
    first = next((i for i in plan.items if i.get("deep") == 1), plan.items[0])
    at = round(float(first.get("start") or 0.0) + 0.4 * float(first.get("seconds") or 0.0), 1)
    stem = os.path.splitext(video_path)[0]
    frame, thumb = f"{stem}_frame.png", f"{stem}_thumb.png"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-ss", str(at), "-i", video_path, "-frames:v", "1",
         "-vf", "scale=1280:720", frame],
        capture_output=True, stdin=subprocess.DEVNULL, timeout=120, check=False,
    )  # fmt: skip
    if not os.path.isfile(frame):
        return ""
    # "Oct 15-18": the headline keeps five words, and "Oct 15 - Oct 18" lost its end to that.
    dates = [i["published_at"] for i in plan.items if isinstance(i.get("published_at"), datetime)]
    span = short_span(min(dates), max(dates)) if dates else ""  # #1592: items are not in date order
    try:
        from PIL import Image

        from assets.thumbnail_compose import compose_thumbnail

        compose_thumbnail(
            Image.open(frame).convert("RGB"),
            f"Week in Review {span}".strip(),
            thumb,
            channel_id=plan.channel_id,
        )
    except Exception as exc:
        logger.warning("week compile thumbnail skipped: %s", exc)
        return ""
    return thumb if os.path.isfile(thumb) else ""


def _record(plan: WeekPlan, path: str, *, thumbnail: str = "") -> int:
    from core.run_recorder import record_content_run

    features: dict[str, Any] = {
        "compilation": {
            "week": plan.week,
            "runs": [i["run_id"] for i in plan.items],
            "seconds": round(plan.seconds, 1),
        }
    }
    if thumbnail:  # the upload takes it through thumbnail_pick.ensure_thumbnail_ready
        features["thumbnail_pick"] = {"path": thumbnail, "arm": "compilation"}

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
        features=features,
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
    thumb = make_thumbnail(plan, dst)
    run_id = _record(plan, dst, thumbnail=thumb)
    lines.append(f"  Rendered: {dst} (run {run_id})" + (f", thumbnail {thumb}" if thumb else ""))
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
