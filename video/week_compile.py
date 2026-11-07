"""#138 (the operator, 2026-10-18: "Shorts compilation, $0"): the week's Shorts as one long video.

Long-form watch hours were 10 of the 4,000 the Partner Program needs, and every video is a
Short. Each week the Shorts that went public in the last seven days become one 16:9 video: each
Short centred on a blurred copy of itself, its channel intro trimmed so it plays once a video
rather than once a chapter, a chapter each in the description. No new script, voice or footage -
$0 and one ffmpeg pass a Short.

`ops week-compile` is a dry run by default; `--apply` renders to output/<channel>/week/ and
records a run; `--apply --schedule` also queues it public (the slot rule). Overnight does both on
the morning of the weekly long slot's day (`WEEK_COMPILE`, on by default; the suite pins it off).

#1743 (wave 146): on the 1st, last month's ten most-watched Shorts by organic views to date, whole,
counted down to #1 - `ops week-compile --month`, overnight with `MONTH_COMPILE`.

#1727 (wave 149): the Week in Review goes public at one weekly time, Sunday 7 PM in the channel's
zone (`spaced_queue.LONG_SLOT`) - compiled that morning, so a Short is in one week's video only.
#1990 (wave 149): its cover is a clean 16:9 band of the week's top Short with that Short's subject
on it - "GTA 6 This Week" - not "Week in Review Oct 26-Nov" over a blurred, captioned frame.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
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
MONTH_BEST = 10  # #1743 (B06.22): the month's most-watched Shorts, counted down
# #1990 (wave 149): the cover's frame is a 16:9 band of the Short itself, from 36% of its height -
# below the top-anchored captions (519 px of 1920 and two lines down, `safe_zone`) and above the
# bottom ones (450 px up from the foot). The blurred full frame carried a caption mid-word.
COVER_BAND_TOP = 0.36


@dataclass
class WeekPlan:
    channel_id: str
    week: str  # #1727: the weekly long slot's day it is made for, YYYY-MM-DD - one a week
    title: str
    description: str
    items: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0
    kind: str = "week"  # #1743: "month" - `week` then holds YYYY-MM


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
    disk - not a held one, not an earlier compilation, not one an earlier week's video holds
    (#1727: the move from Monday to Sunday would have put Nov 1's Shorts in two)."""
    moment = _now(now)
    since = moment - timedelta(days=7)
    held = compiled_runs(channel_id)
    shorts = _public_shorts(channel_id, lambda when: since < when <= moment)
    return [s for s in shorts if s["run_id"] not in held]


def compiled_runs(channel_id: str) -> set[int]:
    """#1727: the Shorts an earlier Week in Review already holds (its `compilation.runs`)."""
    from storage.repositories.content_runs import get_content_run_repository

    try:
        runs = get_content_run_repository().list_for_channel(channel_id)[:60]
    except Exception as exc:
        logger.debug("compiled runs unread: %s", exc)
        return set()
    out: set[int] = set()
    for run in runs:
        compilation = _features(run).get("compilation") or {}
        if not compilation.get("week"):
            continue
        for run_id in compilation.get("runs") or []:
            try:
                out.add(int(run_id))
            except (TypeError, ValueError):
                continue
    return out


def week_key(channel_id: str, moment: datetime) -> str:
    """#1727: the week a compilation made at `moment` is for - the date of the weekly long slot's
    day on or after the channel's day (Monday when the slot is off). Compiled on a Monday, the
    old key; compiled on Sunday Nov 8, "2026-11-08", not Nov 2's (run 230's), which would have
    read as already made."""
    from core.series.dated import channel_day
    from core.spaced_queue import long_slot

    slot = long_slot()
    day = channel_day(channel_id, moment)
    target = slot[0] if slot else 0
    return (day + timedelta(days=(target - day.weekday()) % 7)).isoformat()


def _public_shorts(
    channel_id: str, inside: Callable[[datetime], bool], *, lifetime: bool = False
) -> list[dict[str, Any]]:
    """The public Shorts whose publish time is `inside`, oldest first, with a file on disk.
    ``lifetime`` (#1743): rank by organic views to date, not the synced window's."""
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

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
        if not inside(when) or int(run_id) in seen:
            continue
        run = _run(int(run_id))
        path = str(getattr(run, "mp4_path", "") or "") if run is not None else ""
        if not path or not os.path.isfile(path) or not _new_short(_features(run)):
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
                    "views": _organic_views(getattr(row, "metrics_json", None),
                                            lifetime=lifetime)})  # fmt: skip
    return sorted(out, key=lambda s: s["published_at"])


def _new_short(features: dict[str, Any]) -> bool:
    """A Short the week made new - not a compilation, and not a cut of an older Short (#1652's
    re-hook, #1057's re-cut, #1651's Week in Review Short): those were in an earlier week's."""
    return not any(features.get(k) for k in ("compilation", "rehook_of", "recut_of",
                                             "week_review_cut"))  # fmt: skip


def _organic_views(metrics_json: Any, *, lifetime: bool = False) -> int:
    """The window's views less the paid ones - ads say nothing about what people look for -
    or the lifetime count when the window has not synced. ``lifetime`` (#1743): the lifetime
    views less every paid view on record (#1977) when the lifetime count is known."""
    from core.ypp_readiness import _organic_views as window_organic

    try:
        metrics = json.loads(metrics_json or "{}") or {}
        if lifetime:
            from analytics.youtube_metrics import organic_lifetime

            known = organic_lifetime(metrics)
            if known is not None:
                return known
        if metrics.get("views") is not None:
            return int(window_organic(metrics))
        return int(metrics.get("lifetime_views") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def subject_name(title: str, names: list[str]) -> str:
    """#1316: the name a Short is about - the researched name that comes first in its title,
    a team by its last word ("Kansas City Chiefs" -> "Chiefs") when only that is in it, with a
    number that follows it ("GTA 6"); the title's first name when research named none of it."""
    from apis.topic_tokens import phrase_with_number, title_phrases

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
    if not phrases:
        return ""
    return phrase_with_number(re.sub(r"(?:'s|')$", "", phrases[0]), title)  # #1982


def compilation_title(
    name: str, items: list[dict[str, Any]], span: str, *, limit: int = 100, label: str = ""
) -> str:
    """#1316: "Pereira, Mahomes & GTA 6 - TapIn Week in Review (Oct 19-25)" - the most-viewed
    Shorts' names, within YouTube's 100 characters; the dates alone when none is named.
    ``label`` (#1743) replaces "Week in Review (span)" - "Best of October 2026"."""
    label = label or f"Week in Review ({span})"
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
        title = f"{named} - {name} {label}"
        if len(title) <= limit:
            return title
        chosen.pop()
    return f"{name} {label}"[:limit]


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


def week_special(channel_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """#1866 (B11.20, wave 145): a `week_special` row of `config/series.json` due on this
    Monday - that week's Week in Review is its subject's alone, under its own title."""
    try:
        from core.series.countdown import series_rows
        from core.series.dated import channel_day

        today = channel_day(channel_id, _now(now)).isoformat()
        for row in series_rows(channel_id):
            if row.get("kind") == "week_special" and str(row.get("on") or "")[:10] == today:
                return row
    except Exception as exc:
        logger.debug("week special unread: %s", exc)
    return None


def special_items(items: list[dict[str, Any]], row: dict[str, Any] | None) -> list[dict[str, Any]]:
    """#1866: the Shorts naming the special's subject, or `items` when under MIN_SHORTS do - a
    thin launch week still gets its regular Week in Review."""
    if not row:
        return items
    from apis.topic_tokens import names_any

    names = [str(n) for n in row.get("names") or [row.get("subject") or ""] if str(n).strip()]
    kept = [i for i in items if names_any(str(i.get("title") or ""), names)]
    return kept if len(kept) >= MIN_SHORTS else items


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
    special = week_special(channel_id, now=moment)
    every = len(items)
    items = special_items(items, special)
    if special and len(items) == every and every:
        special = None  # too few named it: the regular Week in Review
    if len(items) < MIN_SHORTS:
        return None
    name = _channel_name(channel_id)
    first, last = items[0]["published_at"], items[-1]["published_at"]
    items = plan_clips(items)  # #1592: the rundown, then the top 3 counted down
    chapters, at = [], 0.0
    for item in items:
        label = f"Deep dive #{item['deep']}: {item['title']}" if item.get("deep") else item["title"]
        chapters.append(f"{_clock(at)} {label}")
        item["start"] = at
        at += item["seconds"]
    week = week_key(channel_id, moment)  # #1727
    deep_count = sum(1 for item in items if item.get("deep"))
    about = str(special.get("subject") or name) if special else name
    description = (
        f"Every {about} story from {short_span(first, last)}, then the week's top {deep_count} "
        "in full.\n\n" + "\n".join(chapters) + "\n"
    )
    description = _with_disclosure(channel_id, description)
    title = compilation_title(name, items, short_span(first, last))
    if special and special.get("title"):  # #1866: its own title, with the dates
        title = f"{special['title']} ({short_span(first, last)})"[:100]
    return WeekPlan(channel_id=channel_id, week=week, title=title,
                    description=description, items=items, seconds=at)  # fmt: skip


def _channel_name(channel_id: str) -> str:
    try:
        from config.channels import get_channel_profile

        return str(get_channel_profile(channel_id).name or channel_id)
    except Exception:
        return channel_id


def _with_disclosure(channel_id: str, description: str) -> str:
    """#1522 (live 2026-10-19): the first compilation was scheduled public without the AI
    disclosure every other upload carries - this description is built here, not by the SEO path."""
    try:
        from core.description_extras import ai_disclosure_line

        disclosure = ai_disclosure_line(channel_id)
    except Exception as exc:
        logger.debug("week compile disclosure unread: %s", exc)
        disclosure = ""
    return description + (f"\n{disclosure}\n" if disclosure else "")


def last_month(channel_id: str, *, now: datetime | None = None) -> tuple[datetime, datetime]:
    """#1743: the calendar month before `now`'s, in the channel's zone - [start, end)."""
    try:
        from core.spaced_queue import _channel_tz

        zone: Any = _channel_tz(channel_id)
    except Exception:
        zone = timezone.utc
    end = _now(now).astimezone(zone).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (end - timedelta(days=1)).replace(day=1), end


def plan_month(channel_id: str, *, now: datetime | None = None) -> WeekPlan | None:
    """#1743 (B06.22, wave 146): last month's `MONTH_BEST` most-watched public Shorts by organic
    views to date (#1977 - a promoted Short's ads say nothing of what people look for), counted
    down from the tenth: the rest as their openings, the top 3 whole (`plan_clips`, decision 81's
    5-8 minutes - October's ten whole ran 11:53); None under MIN_SHORTS. $0 - the Shorts are on
    disk."""
    start, end = last_month(channel_id, now=now)
    offset = _intro_offset(channel_id)
    items: list[dict[str, Any]] = []
    for short in _public_shorts(channel_id, lambda when: start <= when < end, lifetime=True):
        length = _duration(short["path"])
        cut = float(short.get("offset", offset))
        if not length or length > _MAX_SHORT_SECONDS or length - cut < 10:
            continue
        items.append({**short, "offset": cut, "seconds": float(length) - cut})
    if len(items) < MIN_SHORTS:
        return None
    ranked = sorted(items, key=lambda i: (-int(i.get("views") or 0), i["published_at"]))
    top = [{**item, "rank": rank} for rank, item in enumerate(ranked[:MONTH_BEST], 1)]
    items = plan_clips(top[::-1])  # the tenth first; the top 3 whole, #1 last
    name = _channel_name(channel_id)
    month = f"{start:%B %Y}"
    chapters, at = [], 0.0
    for item in items:
        chapters.append(f"{_clock(at)} #{item['rank']}: {item['title']}")
        item["start"] = at
        at += item["seconds"]
    deep_count = sum(1 for item in items if item.get("deep"))
    description = _with_disclosure(
        channel_id,
        f"The {len(items)} most-watched {name} Shorts of {month}, counted down - the top "
        f"{deep_count} in full.\n\n" + "\n".join(chapters) + "\n",
    )  # fmt: skip
    title = compilation_title(name, items, "", label=f"Best of {month}")
    return WeekPlan(channel_id=channel_id, week=f"{start:%Y-%m}", title=title,
                    description=description, items=items, seconds=at, kind="month")  # fmt: skip


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


def _out_path(channel_id: str, week: str, *, kind: str = "week") -> str:
    from config.paths import ROOT_DIR

    return os.path.join(ROOT_DIR, "output", channel_id, "week", f"{kind}_{week}.mp4")


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


def week_done(channel_id: str, week: str, *, kind: str = "week") -> bool:
    """A compilation for this week (or, with `kind="month"`, this YYYY-MM) is already a run."""
    from storage.repositories.content_runs import get_content_run_repository

    try:
        runs = get_content_run_repository().list_for_channel(channel_id)[:40]
    except Exception:
        return False
    return any((_features(r).get("compilation") or {}).get(kind) == week for r in runs)


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


def cover_item(plan: WeekPlan, rank: int = 1) -> dict[str, Any] | None:
    """The Short a cover shows: deep dive #`rank` (#1592), else the `rank`-th most watched."""
    deep = sorted((i for i in plan.items if i.get("deep")), key=lambda i: int(i["deep"]))
    ordered = deep or sorted(plan.items, key=lambda i: -int(i.get("views") or 0))
    return ordered[min(max(rank, 1), len(ordered)) - 1] if ordered else None


def cover_words(plan: WeekPlan, item: dict[str, Any]) -> str:
    """#1990: what the cover says - the Short's subject and "This Week" ("GTA 6 This Week"), so
    the cover names what the title names first. Run 230's said "Week in Review Oct 26-Nov": the
    headline keeps five words and the date lost its end. A month keeps "Best of October"."""
    if plan.kind == "month":  # #1743
        return f"Best of {datetime.strptime(plan.week, '%Y-%m'):%B}"
    subject = subject_name(str(item.get("title") or ""), list(item.get("names") or []))
    return f"{subject} This Week" if subject else "Week in Review"


def cover_frame_argv(src: str, dst: str, *, at: float) -> list[str]:
    """#1990: one frame of the Short itself at `at` s, a full-width 16:9 band from
    `COVER_BAND_TOP` of its height (clear of its captions), at 1280x720. A landscape source is
    its whole frame."""
    band = f"crop=iw:'min(ih,iw*9/16)':0:'min(ih-oh,ih*{COVER_BAND_TOP})',scale=1280:720"
    return ["ffmpeg", "-nostdin", "-y", "-ss", str(round(at, 1)), "-i", src, "-frames:v", "1",
            "-vf", band, dst]  # fmt: skip


def _grab(argv: list[str]) -> None:
    subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL, timeout=120, check=False)


# #1990: where in the Short a cover's band is taken, in turn - live, runs 202 and 230's top GTA 6
# Shorts showed one tower shot 40% in (the gameplay library's clip), so the two covers matched.
_COVER_AT = (0.4, 0.25, 0.6, 0.75)


def _fresh_band(item: dict[str, Any], frame: str) -> int | None:
    """The first band of the Short no earlier cover shares (decision 85's rule, `cover_frames`)
    written to `frame`, and its hash - the band 40% in when every one is taken. None when the
    Short's file gives no frame."""
    from PIL import Image

    from assets.cover_frames import dhash, frame_score, near, used_covers

    def band(share: float) -> tuple[int, float] | None:
        at = float(item.get("offset") or 0.0) + share * float(item.get("seconds") or 0.0)
        _grab(cover_frame_argv(str(item["path"]), frame, at=at))
        if not os.path.isfile(frame):
            return None
        with Image.open(frame) as image:
            return dhash(image), frame_score(image)["score"]

    taken = [int(str(r["hash"]), 16) for r in used_covers()]
    for share in _COVER_AT:
        found = band(share)
        if found is None:
            return None
        # the Shorts' floors too: not dark, not blurred (live, run 230's 25% band was dusk)
        if found[1] > 0 and not any(near(found[0], h) for h in taken):
            return found[0]
    found = band(_COVER_AT[0])  # every band is taken or dark: the one 40% in, as before
    return found[0] if found else None


def make_thumbnail(plan: WeekPlan, video_path: str, *, rank: int = 1, dest: str = "") -> str:
    """Wave 112: the compilation's own thumbnail; #1990: a band of its `rank`-th Short with that
    Short's subject on it (`compose_thumbnail`, its contrast rules), saved to `dest` (beside the
    video when "") and recorded as taken. A frame of the compilation itself when the Short's file
    cannot be read. "" when none."""
    item = cover_item(plan, rank)
    if item is None:
        return ""
    from assets.cover_frames import LONG_SUFFIX  # #1992: the frames-only upload sends it

    thumb = dest or f"{os.path.splitext(video_path)[0]}{LONG_SUFFIX}"
    frame = f"{os.path.splitext(thumb)[0]}_frame.png"
    if os.path.isfile(frame):
        os.remove(frame)
    picture = None
    if item.get("path") and os.path.isfile(str(item["path"])):
        picture = _fresh_band(item, frame)
    if not os.path.isfile(frame):  # wave 112's frame: 40% into the Short's chapter
        at = float(item.get("start") or 0.0) + 0.4 * float(item.get("seconds") or 0.0)
        _grab(["ffmpeg", "-nostdin", "-y", "-ss", str(round(at, 1)), "-i", video_path,
               "-frames:v", "1", "-vf", "scale=1280:720", frame])  # fmt: skip
    if not os.path.isfile(frame):
        return ""
    words = cover_words(plan, item)
    try:
        from PIL import Image

        from assets.thumbnail_compose import compose_thumbnail

        compose_thumbnail(
            Image.open(frame).convert("RGB"),
            words,
            thumb,
            channel_id=plan.channel_id,
        )
    except Exception as exc:
        logger.warning("week compile thumbnail skipped: %s", exc)
        return ""
    if not os.path.isfile(thumb):
        return ""
    if picture is not None:  # the next compilation's cover will not repeat this picture
        from assets.cover_frames import record_cover

        record_cover(picture, thumb)
    return thumb


def compilation_cover(channel_id: str, run_id: int, dest: str) -> str:
    """#1990: a stored compilation's next cover, for `packaging.swap_low_ctr_covers` - its most
    watched Short's subject cover when it went out with wave 112's (runs 172, 202 and 230), else
    its second Short's. "" when none can be cut."""
    run = _run(run_id)
    compilation = _features(run).get("compilation") or {}
    wanted: set[int] = set()
    for value in compilation.get("runs") or []:
        try:
            wanted.add(int(value))
        except (TypeError, ValueError):
            continue
    if run is None or not wanted:
        return ""
    kind = "month" if compilation.get("month") else "week"
    shorts = _public_shorts(channel_id, lambda _when: True, lifetime=kind == "month")
    items = [s for s in shorts if s["run_id"] in wanted]
    for item in items:
        length = float(_duration(item["path"]) or 0.0)
        item["seconds"] = max(0.0, length - float(item.get("offset") or 0.0))
    plan = WeekPlan(channel_id=channel_id, week=str(compilation.get(kind) or ""),
                    title=str(getattr(run, "title", "") or ""), description="", items=items,
                    kind=kind)  # fmt: skip
    rank = 2 if compilation.get("cover") == "subject" else 1
    return make_thumbnail(plan, str(getattr(run, "mp4_path", "") or ""), rank=rank, dest=dest)


def _record(plan: WeekPlan, path: str, *, thumbnail: str = "") -> int:
    from core.run_recorder import record_content_run

    features: dict[str, Any] = {
        "compilation": {
            plan.kind: plan.week,  # #1743: "month": YYYY-MM
            "runs": [i["run_id"] for i in plan.items],
            "seconds": round(plan.seconds, 1),
        }
    }
    if thumbnail:  # the upload takes it through thumbnail_pick.ensure_thumbnail_ready
        features["thumbnail_pick"] = {"path": thumbnail, "arm": "compilation"}
        features["compilation"]["cover"] = "subject"  # #1990: a swap shows the second Short

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
        tags_json=json.dumps(
            ["best of the month" if plan.kind == "month" else "week in review", "compilation"]
        ),
        mp4_path=path,
        features=features,
    )


def compile_week(
    channel_id: str, *, apply: bool = False, queue: bool = False, now: datetime | None = None
) -> list[str]:
    """What the week's compilation is - and with `apply` it rendered and recorded, with `queue`
    also queued public at the weekly long slot (#1727). Lines for the operator."""
    week = week_key(channel_id, _now(now))
    if week_done(channel_id, week):  # first: a made week's Shorts are held, so none would show
        return [f"  Week compilation: the week of {week} is already made."]
    plan = plan_week(channel_id, now=now)
    if plan is None:
        count = len(week_shorts(channel_id, now=now))
        return [f"  Week compilation: {count} public Short(s) this week - it needs {MIN_SHORTS}."]
    lines = [f"  Week compilation: {plan.title} - {len(plan.items)} Shorts, {_clock(plan.seconds)}"]
    return _make(plan, lines, apply=apply, queue=queue, flags="")


def compile_month(
    channel_id: str, *, apply: bool = False, queue: bool = False, now: datetime | None = None
) -> list[str]:
    """#1743: last month's best Shorts as `compile_week` does a week's - lines for the operator."""
    plan = plan_month(channel_id, now=now)
    if plan is None:
        start, end = last_month(channel_id, now=now)
        count = len(_public_shorts(channel_id, lambda when: start <= when < end))
        return [
            f"  Month compilation: {count} public Short(s) in {start:%B} - it needs {MIN_SHORTS}."
        ]
    if week_done(channel_id, plan.week, kind="month"):
        return [f"  Month compilation: {plan.week} is already made."]
    lines = [
        f"  Month compilation: {plan.title} - {len(plan.items)} Shorts, {_clock(plan.seconds)}"
    ]
    return _make(plan, lines, apply=apply, queue=queue, flags=" --month")


def _make(plan: WeekPlan, lines: list[str], *, apply: bool, queue: bool, flags: str) -> list[str]:
    """The chapters, then - with `apply` - the render, its thumbnail and run, and with `queue`
    its public slot."""
    channel_id = plan.channel_id
    lines = [*lines, *(f"    {line}" for line in plan.description.strip().splitlines()[2:])]
    if not apply:
        return [*lines, "  Dry run - --apply renders it ($0, one ffmpeg pass a Short)."]
    dst = _out_path(channel_id, plan.week, kind=plan.kind)
    why = _render(plan, dst)
    if why:
        return [*lines, f"  Not made: {why}."]
    thumb = make_thumbnail(plan, dst)
    run_id = _record(plan, dst, thumbnail=thumb)
    lines.append(f"  Rendered: {dst} (run {run_id})" + (f", thumbnail {thumb}" if thumb else ""))
    if not queue:
        return [
            *lines,
            f"  Queue it: py -m scripts.ops week-compile{flags} --channel {channel_id} --apply "
            "--schedule",
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
