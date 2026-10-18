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

**Through the API (#1188, operator 2026-10-14).** With `BUFFER_API_KEY`, the R2 keys
(`video_host`) and the Buffer channel ids (`crosspost channels --apply`), a video goes to
TikTok and Instagram on its own once it is public on YouTube - the operator's watch-before-
public covers these platforms too. Only videos made public after it was switched on: the first
run records what was already public (`buffer.baseline`). Each post goes at the channel's
suggested slot - no spacing between posts (decision 63, the operator: "volume is a struggle right
now"); the AI label is on and the caption keeps the disclosure line.
`createPost` has no idempotency key, so a call is marked `sending` before it is made, and one
that got no answer is looked for in Buffer before it is ever sent again.

    py -m scripts.ops crosspost channels [--apply]   Buffer's channels; --apply keeps the ids
    py -m scripts.ops crosspost send [--apply]       what would be scheduled; --apply sends
    py -m scripts.ops crosspost status               each video on each platform
    py -m scripts.ops crosspost cancel --run-id N    delete its scheduled posts
    py -m scripts.ops crosspost selftest             put and delete 1 KB in the R2 bucket
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    """Decision 64 (the operator, 2026-10-17): Instagram takes Reels up to 3 minutes - run 157
    (90 s) was skipped at the old 90 s cap."""
    try:
        return float(os.getenv("INSTAGRAM_MAX_SECONDS", "180") or 180)
    except ValueError:
        return 180.0


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


_EVENING_HOUR = 22  # 10 PM in the channel's time zone


def _suggested_slot(channel_id: str, topic: str, *, now: datetime | None = None) -> datetime:
    """The next 10 PM in the channel's time zone - always within a day.

    Decision 64 (the operator, 2026-10-17): with no history of their own, TikTok and Instagram
    took YouTube's learned slot for the topic's sport, and run 157 (UFC) got Thursday 3:00 AM,
    five days after it went public. A platform with its own hours (`hour_choice`) keeps them.
    """
    from zoneinfo import ZoneInfo

    del topic
    try:
        from analytics.post_timing import _load_static_post_schedule

        zone: Any = ZoneInfo(_load_static_post_schedule(channel_id).timezone)
    except Exception:
        zone = timezone.utc
    local = ((now or datetime.now(timezone.utc)) + timedelta(minutes=15)).astimezone(zone)
    slot = local.replace(hour=_EVENING_HOUR, minute=0, second=0, microsecond=0)
    if slot < local:
        slot += timedelta(days=1)
    return slot.astimezone(timezone.utc)


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
    """The operator posted it by hand: the pack is marked posted, and the automatic round
    (#1188) leaves it on both platforms (#1201 - run 132 answered "never packed")."""
    data = _load(channel_id)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = (data.get("runs") or {}).get(str(run_id))
    if isinstance(entry, dict):
        entry["posted"] = now
    elif _content_run(run_id) is None:
        return False
    posts = data.setdefault("posts", {}).setdefault(str(run_id), {})
    for service in ("tiktok", "instagram"):
        state = posts.get(service)
        if not isinstance(state, dict) or state.get("state") not in ("scheduled", "sent"):
            posts[service] = {"state": "manual", "error": "posted by hand", "at": now}
    _save(channel_id, data)
    return True


def _stamp(value: Any) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def week_counts(channel_id: str, *, days: int = 7, now: datetime | None = None) -> tuple[int, int]:
    """#979: (packed, posted) in the last `days` days, from the stored stamps. A video sent
    through the API (#1189) counts as packed when it was scheduled and posted when it was sent."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    packed = posted = 0
    data = _load(channel_id)
    for entry in (data.get("runs") or {}).values():
        if not isinstance(entry, dict):
            continue
        when = _stamp(entry.get("packed"))
        packed += bool(when and when >= cutoff)
        when = _stamp(entry.get("posted"))
        posted += bool(when and when >= cutoff)
    for entry in (data.get("posts") or {}).values():
        if not isinstance(entry, dict):
            continue
        states: list[dict[str, Any]] = [
            s for s in (entry.get(p) for p in PLATFORMS) if isinstance(s, dict)
        ]
        scheduled = [_stamp(s.get("at")) for s in states if s.get("post_id")]
        sent = [_stamp(s.get("sent_at")) for s in states if s.get("state") == "sent"]
        packed += any(w and w >= cutoff for w in scheduled)
        posted += any(w and w >= cutoff for w in sent)
    return packed, posted


def week_line(channel_id: str, *, now: datetime | None = None) -> str:
    """One line for the weekly report and `ops status`; "" when nothing was packed or posted."""
    packed, posted = week_counts(channel_id, now=now)
    if not packed and not posted:
        return ""
    return (
        f"Buffer this week: {packed} packed, {posted} posted (TikTok + Instagram; "
        "mark each with ops crosspost done --run-id N)"
    )


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


# ---- through the Buffer API (#1187-#1190) --------------------------------------------------------

PLATFORMS = ("tiktok", "instagram")
_LABEL = {"tiktok": "TikTok", "instagram": "Instagram"}
_CHANNEL_ENV = {"tiktok": "BUFFER_TIKTOK_CHANNEL_ID", "instagram": "BUFFER_INSTAGRAM_CHANNEL_ID"}
_LIVE = ("scheduled", "sending", "retry")  # states that still need the hosted copy
_LEAD = timedelta(minutes=15)
# A create call with no answer: Buffer makes a post at once, so one not found this long after
# the call was never made, and may be sent.
_SENDING_GRACE = timedelta(minutes=10)


def auto_enabled() -> bool:
    return os.getenv("CROSSPOST_AUTO", "true").strip().lower() not in ("0", "false", "no", "off")


def buffer_channel_ids(channel_id: str) -> dict[str, str]:
    """{"tiktok": id, "instagram": id} - `BUFFER_TIKTOK_CHANNEL_ID` / `BUFFER_INSTAGRAM_CHANNEL_ID`
    when set, else what `crosspost channels --apply` stored."""
    stored = _load(channel_id).get("buffer") or {}
    out: dict[str, str] = {}
    for service in PLATFORMS:
        value = os.getenv(_CHANNEL_ENV[service], "").strip()
        value = value or str(stored.get(service) or "").strip()
        if value:
            out[service] = value
    return out


def save_channels(channel_id: str, organization_id: str, picked: dict[str, str]) -> None:
    data = _load(channel_id)
    block = data.setdefault("buffer", {})
    block["organization_id"] = organization_id
    block.update({k: v for k, v in picked.items() if k in PLATFORMS})
    _save(channel_id, data)


def choose_channels(rows: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    """One usable TikTok and one Instagram channel from Buffer's list, and what is wrong."""
    picked: dict[str, str] = {}
    notes: list[str] = []
    for service in PLATFORMS:
        label = _LABEL[service]
        found = [r for r in rows if str(r.get("service") or "").lower() == service]
        usable = [r for r in found if not r.get("isDisconnected") and not r.get("isLocked")]
        if not found:
            notes.append(f"no {label} channel in Buffer - connect one at publish.buffer.com")
            continue
        if not usable:
            notes.append(
                f"{label} ({found[0].get('name')}) is disconnected or locked in Buffer - reconnect it"
            )
            continue
        if len(usable) > 1:
            ids = ", ".join(f"{r.get('name')} {r.get('id')}" for r in usable)
            notes.append(f"{len(usable)} {label} channels ({ids}) - set {_CHANNEL_ENV[service]}")
            continue
        row = usable[0]
        picked[service] = str(row.get("id"))
        if row.get("isQueuePaused"):
            notes.append(f"{label}'s queue is paused in Buffer - scheduled posts will not go out")
        if service == "instagram" and str(row.get("type") or "").lower() in ("profile", "personal"):
            notes.append(
                "Instagram is a personal profile - Buffer posts Reels only from a Professional "
                "(Business or Creator) account"
            )
    return picked, notes


def channel_lines(rows: list[dict[str, Any]]) -> list[str]:
    out = []
    for row in rows:
        flags = [
            word
            for word, key in (
                ("disconnected", "isDisconnected"),
                ("locked", "isLocked"),
                ("queue paused", "isQueuePaused"),
            )
            if row.get(key)
        ]
        flag = f"  [{', '.join(flags)}]" if flags else ""
        out.append(
            f"  {row.get('service') or '':<10} {row.get('name') or ''} "
            f"({row.get('type') or ''}){flag}  id {row.get('id')}"
        )
    return out


def waits_line(missing: list[str]) -> str:
    """'waits on X' - and, when the bucket's public address is what is missing, how to set it
    (#1232: the line said only "wait on R2_PUBLIC_BASE_URL")."""
    line = "waits on " + ", ".join(missing)
    if "R2_PUBLIC_BASE_URL" in missing:
        line += (
            " - in Cloudflare: R2 > your bucket > Settings > Public Development URL > Enable, "
            "then: py -m scripts.ops crosspost public-url https://pub-....r2.dev"
        )
    return line


def setup_missing(channel_id: str) -> list[str]:
    """What still has to be set before a video can go out through Buffer."""
    from publishing import buffer_api, video_host

    out: list[str] = []
    if not buffer_api.configured():
        out.append("BUFFER_API_KEY")
    if not video_host.configured():
        out.extend(video_host.missing())
    if not buffer_channel_ids(channel_id):
        out.append("the Buffer channel ids (py -m scripts.ops crosspost channels --apply)")
    return out


def _public_runs(channel_id: str) -> list[tuple[int, str]]:
    """(run id, YouTube id) of each video public on YouTube, as the publish log says."""
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    out: dict[int, str] = {}
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id):
        run_id = getattr(row, "content_run_id", None)
        if not run_id or is_seeded(row):
            continue
        if str(getattr(row, "privacy_status", "") or "").strip().lower() != "public":
            continue
        out[int(run_id)] = str(getattr(row, "youtube_video_id", "") or "")
    return sorted(out.items())


def _content_run(run_id: int) -> Any:
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository().get(int(run_id))


def _thumbnail_ms(channel_id: str) -> int:
    """A frame one second past the channel intro, so the cover is not the intro card."""
    try:
        from config.channels import get_channel_profile

        offset = float(get_channel_profile(channel_id).intro_offset_seconds or 0.0)
    except Exception:
        offset = 0.0
    return int((offset + 1.0) * 1000)


def _due_of(state: dict[str, Any]) -> datetime | None:
    return _stamp(state.get("due_at"))


# A game preview posts at least this long before kickoff (the operator, 2026-10-17).
_BEFORE_GAME = timedelta(minutes=30)


def _kickoff_for(channel_id: str, run_id: int) -> datetime | None:
    """When the game a video previews starts - its draft's `event_at` (#1151) - or None."""
    try:
        from core.batch_review import draft_meta_for_run

        raw = str(draft_meta_for_run(channel_id, run_id).get("event_at") or "")
    except Exception as exc:
        logger.debug("game start for run %s unread: %s", run_id, exc)
        return None
    return _stamp(raw.replace("Z", "+00:00")) if raw else None


def _next_due(
    channel_id: str,
    topic: str,
    service: str,
    posts: dict[str, Any],
    now: datetime,
    *,
    kickoff: datetime | None = None,
) -> tuple[datetime | None, str]:
    """When to post, and why. A game preview goes before its game (the operator, 2026-10-17:
    run 155's Titans preview had been spaced to nine hours after kickoff); None when its game
    has started or starts too soon."""
    from publishing.platform_recommend import hour_choice

    hour, note = hour_choice(channel_id, service)
    if hour is None:
        # Wave 105: the note still said "uses YouTube's hour" after decision 64.
        samples = re.search(r"\(([^)]*)\)", note or "")
        note = f"{_LABEL[service]} posts at the 10 PM evening slot until it has hours of its own"
        if samples:
            note += f" ({samples.group(1)})"
        due = _suggested_slot(channel_id, topic, now=now)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due < now + _LEAD:
            due = now + _LEAD
    else:
        due = _at_utc_hour(hour, now + _LEAD)
    # Decision 63 (2026-10-17): no spacing between posts - the one-a-day rule pushed a game
    # preview past its kickoff, and there is not the volume to ration.
    del posts
    if kickoff is not None:
        latest = kickoff - _BEFORE_GAME
        if due > latest:
            earliest = now + _LEAD
            if earliest > latest:
                return None, "its game has started"
            return earliest, f"before its game ({_local(kickoff, channel_id)})"
    return due, note


def _at_utc_hour(hour: int, after: datetime) -> datetime:
    """The next UTC time at `hour:00` that is not before `after`."""
    moment = after.astimezone(timezone.utc) if after.tzinfo else after.replace(tzinfo=timezone.utc)
    candidate = moment.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if candidate < moment:
        candidate += timedelta(days=1)
    return candidate


def _adopt(org_id: str, buffer_channel: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """The post a `sending` mark made, when Buffer has it: same due time, same caption start."""
    from publishing import buffer_api

    want = _due_of(state)
    start = str(state.get("text_start") or "")
    for post in buffer_api.find_posts(org_id, buffer_channel):
        when = _stamp(str(post.get("dueAt") or "").replace("Z", "+00:00"))
        if want and when and abs(when - want) < timedelta(minutes=1):
            if str(post.get("text") or "").startswith(start):
                return post
    return None


def hand_post_matches(post_text: str, run_text: str) -> bool:
    """True when a Buffer post is about this video (#1200): most of the words that open the
    post are the video's own (its title, opening line or description).

    The operator's hand posts open with the video's first line ("Gaethje TKO'd Topuria at UFC
    Freedom 250 - and wrote the blueprint") as often as with its title.
    """
    from apis.topic_tokens import content_tokens

    want = set(content_tokens(post_text or "", min_len=3)[:25])
    if len(want) < 4:
        return False
    have = set(content_tokens(run_text or "", min_len=3))
    return len(want & have) >= 0.6 * len(want)


def _rendered_at(path: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
    except OSError:
        return None


def _hand_post(posts: list[dict[str, Any]], run_text: str, rendered: datetime | None):
    """The Buffer post that already carries this video, made no earlier than a day before it
    was rendered - an older post on the same subject is another video."""
    for post in posts:
        when = _stamp(str(post.get("sentAt") or post.get("dueAt") or "").replace("Z", "+00:00"))
        if rendered and when and when < rendered - timedelta(days=1):
            continue
        if hand_post_matches(str(post.get("text") or ""), run_text):
            return post
    return None


def _now_text(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


def switch_on(channel_id: str, *, now: datetime | None = None) -> list[str]:
    """Record the moment crossposting starts and the videos already public then (they are
    left alone - "new videos only"). [] when it was already on.

    Done as soon as Buffer is set up, even while R2 is not: a video made public in between then
    counts as new and goes once the bucket is ready.
    """
    data = _load(channel_id)
    block = data.setdefault("buffer", {})
    if block.get("since"):
        return []
    public = _public_runs(channel_id)
    block["since"] = _now_text(now or datetime.now(timezone.utc))
    block["baseline"] = sorted(run_id for run_id, _ in public)
    _save(channel_id, data)
    return [
        f"Crosspost - {channel_id}: switched on. {len(public)} video(s) already public stay as "
        "they are; each one made public from now goes to TikTok and Instagram."
    ]


def send_due(channel_id: str, *, apply: bool = True, now: datetime | None = None) -> list[str]:
    """Schedule on TikTok and Instagram each video made public on YouTube since this was
    switched on. `apply=False` says what it would do and writes nothing."""
    from publishing import buffer_api, video_host

    moment = now or datetime.now(timezone.utc)
    if not (_load(channel_id).get("buffer") or {}).get("since"):
        if not apply:
            return [
                f"Crosspost - {channel_id}: not switched on yet; videos public now stay as they are"
            ]
        return switch_on(channel_id, now=moment)
    data = _load(channel_id)
    block = data.setdefault("buffer", {})
    public = _public_runs(channel_id)
    baseline = {int(x) for x in block.get("baseline") or []}
    ids = buffer_channel_ids(channel_id)
    org_id = str(block.get("organization_id") or "")
    posts = data.setdefault("posts", {})
    lines: list[str] = []
    in_buffer: dict[str, list[dict[str, Any]]] = {}  # #1200: read once per channel a round

    def buffer_posts(service: str) -> list[dict[str, Any]]:
        if service not in in_buffer:
            try:
                in_buffer[service] = buffer_api.find_posts(org_id, ids[service]) if org_id else []
            except Exception as exc:
                logger.info("crosspost: %s posts unread: %s", service, exc)
                in_buffer[service] = []
        return in_buffer[service]

    for run_id, _video in public:
        if run_id in baseline:
            continue
        entry = posts.get(str(run_id)) or {}
        todo = [
            s for s in PLATFORMS
            if s in ids and (entry.get(s) or {}).get("state") in (None, "", "sending", "retry")
        ]  # fmt: skip
        if not todo:
            continue
        run = _content_run(run_id)
        path = str(getattr(run, "mp4_path", "") or "") if run is not None else ""
        if not path or not os.path.isfile(path):
            lines.append(f"  ! run {run_id}: the rendered mp4 is not on disk - nothing to post")
            continue
        title = str(getattr(run, "title", "") or "")
        run_text = " ".join(
            str(getattr(run, name, "") or "") for name in ("title", "script_preview", "description")
        )
        rendered = _rendered_at(path)
        topic = str(getattr(run, "input_topic", "") or getattr(run, "selected_topic", "") or "")
        kickoff = _kickoff_for(channel_id, run_id)
        seconds = _duration(path)
        limit = reel_max_seconds()
        if apply:
            entry = posts.setdefault(str(run_id), {})
            entry["title"] = title
        for service in todo:
            label = _LABEL[service]
            state = dict(entry.get(service) or {})
            if service == "instagram" and seconds is not None and seconds > limit:
                if apply:
                    entry[service] = {
                        "state": "skipped",
                        "error": f"{seconds:.0f}s, longer than a Reel ({limit:.0f}s)",
                        "at": _now_text(moment),
                    }
                    _save(channel_id, data)
                lines.append(
                    f"  run {run_id} {label}: skipped - {seconds:.0f}s is longer than a Reel"
                )
                continue
            from publishing.platform_captions import choose_caption

            arm, text = choose_caption(channel_id, run, service)
            if state.get("state") != "sending":
                hand = _hand_post(buffer_posts(service), run_text, rendered)
                if hand:  # #1200 (operator: skip that platform only)
                    if apply:
                        entry[service] = {
                            "state": "manual",
                            "post_id": str(hand.get("id") or ""),
                            "link": str(hand.get("externalLink") or ""),
                            "error": "posted by hand in Buffer",
                            "at": _now_text(moment),
                        }
                        _save(channel_id, data)
                    lines.append(f"  run {run_id} {label}: already posted by hand in Buffer - left")
                    continue
            if state.get("state") == "sending":
                try:
                    found = _adopt(org_id, ids[service], state) if org_id else None
                except buffer_api.BufferError as exc:
                    lines.append(f"  ! run {run_id} {label}: could not check Buffer ({exc.kind})")
                    continue
                except Exception as exc:
                    lines.append(
                        f"  ! run {run_id} {label}: Buffer did not answer ({type(exc).__name__})"
                    )
                    return lines
                if found:
                    if apply:
                        entry[service] = {
                            **state,
                            "state": "scheduled",
                            "post_id": str(found.get("id")),
                        }
                        _save(channel_id, data)
                    lines.append(f"  run {run_id} {label}: found in Buffer, scheduled")
                    continue
                marked = _stamp(state.get("at"))
                if marked and moment - marked < _SENDING_GRACE:
                    lines.append(f"  run {run_id} {label}: waiting to see whether Buffer made it")
                    continue
            due, note = _next_due(channel_id, topic, service, posts, moment, kickoff=kickoff)
            if due is None:
                if apply:
                    entry[service] = {"state": "skipped", "error": note, "at": _now_text(moment)}
                    _save(channel_id, data)
                lines.append(f"  run {run_id} {label}: skipped - {note}")
                continue
            if not apply:
                lines.append(
                    f"  would schedule run {run_id} on {label} for {_local(due, channel_id)} - {note}"
                )
                continue
            try:
                if not entry.get("object_key"):  # hosted once, at its public address
                    key = video_host.object_key(channel_id, run_id, path)
                    entry["url"] = video_host.host(path, key)
                    entry["object_key"] = key
            except Exception as exc:
                lines.append(
                    f"  ! run {run_id}: the video could not be hosted ({type(exc).__name__})"
                )
                _save(channel_id, data)
                return lines
            entry[service] = {
                "state": "sending",
                "due_at": due.isoformat(),
                "text_start": text[:60],
                "arm": arm,
                "at": _now_text(moment),
            }
            _save(channel_id, data)  # the mark goes down before the call
            try:
                post = buffer_api.create_video_post(
                    ids[service],
                    text=text,
                    video_url=str(entry["url"]),
                    due_at=due,
                    service=service,
                    thumbnail_ms=_thumbnail_ms(channel_id),
                )
            except buffer_api.BufferError as exc:
                if exc.kind == "input":
                    entry[service] = {
                        "state": "error",
                        "error": exc.message,
                        "at": _now_text(moment),
                    }
                    _save(channel_id, data)
                    lines.append(f"  ! run {run_id} {label}: Buffer refused it - {exc.message}")
                    continue
                entry[service] = {**entry[service], "state": "retry", "error": exc.message}
                _save(channel_id, data)
                if exc.kind == "auth":
                    lines.append(
                        "  ! Buffer key rejected - check BUFFER_API_KEY "
                        "(publish.buffer.com/settings/api); nothing more is sent this run"
                    )
                    return lines
                if exc.kind == "rate_limited":
                    lines.append("  ! Buffer's request limit - the rest waits for the next run")
                    return lines
                lines.append(f"  ! run {run_id} {label}: {exc.message} - tried again next run")
                continue
            except Exception as exc:
                lines.append(
                    f"  ! run {run_id} {label}: Buffer did not answer ({type(exc).__name__}) - it "
                    "is looked for in Buffer before it is sent again"
                )
                return lines
            entry[service] = {
                "state": "scheduled",
                "post_id": str(post.get("id") or ""),
                "due_at": due.isoformat(),
                "text_start": text[:60],
                "at": _now_text(moment),
            }
            _save(channel_id, data)
            lines.append(f"  run {run_id} {label}: scheduled for {_local(due, channel_id)}")
    return lines


def _remove_copy_when_done(entry: dict[str, Any]) -> bool:
    from publishing import video_host

    if not entry.get("object_key") or entry.get("object_removed"):
        return False
    if any((entry.get(s) or {}).get("state") in _LIVE for s in PLATFORMS):
        return False
    if video_host.remove(str(entry["object_key"])):
        entry["object_removed"] = _now_text(datetime.now(timezone.utc))
        return True
    return False


def sync_status(channel_id: str) -> list[str]:
    """Read each scheduled post back: sent (with its link), Buffer's error, or still due. A
    video no longer public on YouTube has its scheduled posts deleted."""
    from publishing import buffer_api

    data = _load(channel_id)
    posts = data.get("posts") or {}
    if not posts:
        return []
    public = {run_id for run_id, _ in _public_runs(channel_id)}
    lines: list[str] = []
    for rid, entry in posts.items():
        if not isinstance(entry, dict):
            continue
        for service in PLATFORMS:
            state = entry.get(service)
            if not isinstance(state, dict) or state.get("state") != "scheduled":
                continue
            label = _LABEL[service]
            post_id = str(state.get("post_id") or "")
            try:
                if int(rid) not in public:
                    buffer_api.delete_post(post_id)
                    state.update(state="cancelled", error="no longer public on YouTube")
                    lines.append(f"  run {rid} {label}: cancelled - no longer public on YouTube")
                    continue
                post = buffer_api.get_post(post_id)
            except buffer_api.BufferError as exc:
                if exc.kind == "auth":
                    _save(channel_id, data)
                    return [*lines, "  ! Buffer key rejected - check BUFFER_API_KEY"]
                logger.info("crosspost sync %s %s: %s", rid, service, exc.message)
                continue
            except Exception as exc:
                logger.info("crosspost sync %s %s: %s", rid, service, type(exc).__name__)
                continue
            status = str(post.get("status") or "")
            if status == "sent":
                state.update(
                    state="sent",
                    sent_at=str(post.get("sentAt") or ""),
                    link=str(post.get("externalLink") or ""),
                )
                lines.append(f"  run {rid} {label}: sent {state['link']}".rstrip())
            elif status == "error":
                message = str(
                    ((post.get("error") or {}).get("message")) or "Buffer reported an error"
                )
                state.update(state="error", error=message)
                lines.append(f"  ! run {rid} {label}: Buffer could not post it - {message}")
        _remove_copy_when_done(entry)
    _save(channel_id, data)
    return lines


def cancel(channel_id: str, run_id: int) -> list[str]:
    """Delete a video's scheduled Buffer posts."""
    from publishing import buffer_api

    data = _load(channel_id)
    entry = (data.get("posts") or {}).get(str(run_id))
    if not isinstance(entry, dict):
        return [f"Run {run_id} was never sent through Buffer."]
    lines = []
    for service in PLATFORMS:
        state = entry.get(service)
        if not isinstance(state, dict) or state.get("state") not in ("scheduled", "sending"):
            continue
        label = _LABEL[service]
        try:
            if state.get("post_id"):
                buffer_api.delete_post(str(state["post_id"]))
        except buffer_api.BufferError as exc:
            lines.append(f"  ! run {run_id} {label}: not cancelled - {exc.message}")
            continue
        state.update(state="cancelled", error="cancelled by the operator")
        lines.append(f"  run {run_id} {label}: cancelled")
    _remove_copy_when_done(entry)
    _save(channel_id, data)
    return lines or [f"Run {run_id} has nothing scheduled in Buffer."]


def _views_suffix(channel_id: str, run_id: Any, service: str) -> str:
    """Views from today's metrics store. Unmeasured is not printed as zero (#1195)."""
    from publishing.platform_metrics import get_row

    row = get_row(channel_id, str(run_id), service)
    if not row:
        return ""
    if not row.get("measured") or row.get("views") is None:
        return "  not measured yet"
    return f"  {int(row['views'])} views"


def waiting_line(channel_id: str, *, now: datetime | None = None) -> str:
    """Wave 105: what the round is waiting for - videos scheduled to go public on YouTube, the
    next one's time - or "" when there are none."""
    from storage.repositories.publish_log import get_publish_log_repository

    moment = now or datetime.now(timezone.utc)
    times: list[datetime] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        when = getattr(row, "published_at", None)
        if str(getattr(row, "privacy_status", "") or "").lower() != "private" or not when:
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if when > moment:
            times.append(when)
    if not times:
        return ""
    count = len(times)
    return (
        f"  {count} scheduled on YouTube - each goes to TikTok and Instagram when it goes public "
        f"(next: {_local(min(times), channel_id)})"
    )


def status_lines(channel_id: str, *, limit: int = 8) -> list[str]:
    """Each video sent through Buffer, newest first, and where it is on each platform."""
    posts = _load(channel_id).get("posts") or {}

    def sent_by_round(entry: dict[str, Any]) -> bool:  # a hand post is the operator's own
        return any(
            isinstance(entry.get(s), dict) and entry[s].get("state") != "manual" for s in PLATFORMS
        )

    rows = sorted(
        ((rid, e) for rid, e in posts.items() if isinstance(e, dict) and sent_by_round(e)),
        key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0,
        reverse=True,
    )
    if not rows:
        return []
    lines = [f"Through Buffer - {channel_id}: TikTok and Instagram"]
    for rid, entry in rows[:limit]:
        lines.append(f"  run {rid}  {str(entry.get('title') or '')[:70]}")
        for service in PLATFORMS:
            state = entry.get(service)
            if not isinstance(state, dict):
                continue
            label = _LABEL[service]
            kind = str(state.get("state") or "")
            if kind == "scheduled":
                due = _due_of(state)
                when = _local(due, channel_id) if due else "a slot"
                lines.append(f"      {label}: scheduled for {when}")
            elif kind == "sent":
                suffix = _views_suffix(channel_id, rid, service)
                lines.append(f"      {label}: sent {state.get('link') or ''}{suffix}".rstrip())
            else:
                detail = f" - {state.get('error')}" if state.get("error") else ""
                lines.append(f"      {label}: {kind}{detail}")
    from publishing.platform_recommend import learning_line

    for service in PLATFORMS:
        learned = learning_line(channel_id, service)
        if learned:
            lines.append(f"  {learned}")
    from publishing.platform_captions import caption_report

    for service in PLATFORMS:
        report = caption_report(channel_id, service)
        if report:
            lines.append(f"  {report}")
    return lines


def run_state_line(channel_id: str, run_id: int) -> str:
    """One line: where a run stands on TikTok and Instagram; '' when it was never sent."""
    entry = (_load(channel_id).get("posts") or {}).get(str(run_id))
    if not isinstance(entry, dict):
        return ""
    bits = []
    for service in PLATFORMS:
        state = entry.get(service)
        if isinstance(state, dict) and state.get("state"):
            kind = str(state["state"])
            link = f" {state['link']}" if kind == "sent" and state.get("link") else ""
            bits.append(f"{_LABEL[service]} {kind}{link}")
    return ("TikTok / Instagram: " + ", ".join(bits)) if bits else ""


def buffer_check(channel_id: str) -> list[str]:
    """#1214: the whole path once, publishing nothing - the newest rendered video put at its
    public address, a TikTok **draft** made from it (AI label on), read back, then the draft and
    the copy deleted. The one live attempt (2026-10-15) found Buffer cannot read a presigned
    link (#1207); this is how the operator sees the fix work before a real post."""
    from publishing import buffer_api, video_host

    missing = setup_missing(channel_id)
    if missing:
        return [f"Buffer check - {channel_id}: " + waits_line(missing)]
    run = next(
        (
            r
            for r in _rendered_runs(channel_id)
            if os.path.isfile(str(getattr(r, "mp4_path", "") or ""))
        ),
        None,
    )
    if run is None:
        return [f"Buffer check - {channel_id}: no rendered video on disk to try"]
    tiktok = buffer_channel_ids(channel_id).get("tiktok") or next(
        iter(buffer_channel_ids(channel_id).values())
    )
    key = video_host.object_key(channel_id, int(run.id), str(run.mp4_path))
    lines = [f"Buffer check - {channel_id}: run {run.id}, as a draft (nothing is published)"]
    post_id = ""
    try:
        url = video_host.host(str(run.mp4_path), key)
        lines.append(f"  hosted: {video_host.safe_url(url)}")
        post = buffer_api.create_video_post(
            tiktok,
            text="Content OS check - a draft, deleted right after.",
            video_url=url,
            due_at=datetime.now(timezone.utc) + timedelta(days=3),
            service="tiktok",
            thumbnail_ms=_thumbnail_ms(channel_id),
            draft=True,
        )
        post_id = str(post.get("id") or "")
        back = buffer_api.get_post(post_id)
        lines.append(f"  ok: Buffer made draft {post_id} and reads it back ({back.get('status')})")
    except buffer_api.BufferError as exc:
        lines.append(f"  ! Buffer refused it: {exc.message}")
    except Exception as exc:
        lines.append(f"  ! the check stopped: {type(exc).__name__}: {str(exc)[:160]}")
    finally:
        if post_id:
            try:
                buffer_api.delete_post(post_id)
                lines.append("  draft deleted")
            except Exception as exc:
                lines.append(
                    f"  ! the draft was not deleted ({type(exc).__name__}) - delete it in Buffer"
                )
        if video_host.remove(key):
            lines.append("  hosted copy removed")
    return lines


def step(channel_id: str) -> list[str]:
    """The automatic round (`ops morning`, overnight, go-public): read back, then send. []
    when switched off or Buffer is not set up at all."""
    from publishing import buffer_api

    if not auto_enabled() or not buffer_api.configured():
        return []
    missing = setup_missing(channel_id)
    if missing:
        started = switch_on(channel_id) if buffer_channel_ids(channel_id) else []
        return [
            *started,
            f"Crosspost - {channel_id}: TikTok and Instagram " + waits_line(missing),
        ]
    lines: list[str] = []
    try:
        from publishing.platform_metrics import refresh

        refresh(channel_id)
    except Exception as exc:
        logger.warning("platform metrics refresh failed: %s", type(exc).__name__)
    for part in (sync_status, send_due):
        try:
            lines.extend(part(channel_id))
        except Exception as exc:
            logger.warning("crosspost %s failed: %s", part.__name__, exc)
            lines.append(f"  ! crosspost {part.__name__} failed: {type(exc).__name__}")
    return lines
