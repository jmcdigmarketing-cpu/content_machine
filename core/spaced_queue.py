"""Queue several rendered runs across the next open post slots (#757).

An all-angles run makes one long video plus up to five chapter Shorts - six uploads
against a 5-per-7-day cadence cap. `next_optimal_post_time` already skips times the queue
has reserved, so asking it repeatedly (each call `after` the previous slot) spreads them;
the cap decides how many go at all. Anything past it stays on disk with its reason
printed, never silently dropped.

Operator call 2026-09-16: a planned slot goes public at its time (uploaded private with
`publishAt`). A run forced past the grounding gate - or a Short cut from one - is held
unlisted however it was asked for (#754).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from analytics.post_timing import planned_post_time
from core.cadence import cadence_status
from core.logging import get_logger
from publishing.repurpose import enqueue_repurpose_jobs

logger = get_logger("core.spaced_queue")


@dataclass
class SpacedSlot:
    run_id: int
    title: str
    publish_at: datetime | None = None
    skipped: str = ""
    privacy: str = ""  # what it was queued as; "" until queued


def _channel_tz(channel_id: str) -> ZoneInfo:
    try:
        from analytics.post_timing import get_post_schedule

        return ZoneInfo(get_post_schedule(channel_id).timezone)
    except Exception as exc:
        logger.debug("channel timezone skipped: %s", exc)
        return ZoneInfo("America/New_York")


def _end_of_local_day(when: datetime, tz: ZoneInfo) -> datetime:
    """The last moment of `when`'s day in the channel's own timezone, in UTC."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    local = when.astimezone(tz)
    midnight = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=tz)
    return midnight.astimezone(timezone.utc) - timedelta(seconds=1)


def plan_spaced_uploads(
    items: list[tuple[int, str]],
    *,
    channel_id: str,
    topic: str = "",
    reserve: int = 0,
    one_per_day: bool = False,
    not_on: datetime | None = None,
) -> list[SpacedSlot]:
    """One open slot per run, in order, until the cadence window is full.

    `reserve` holds slots for uploads this session already queued (the long video).
    `one_per_day` (#1055): the Shorts cut from one video go out on different days - a day
    with two open slots (Saturday 11am and 7pm) took two of them. `not_on` leaves that
    day (the long video's) alone as well.
    """
    status = cadence_status(channel_id)
    # Decision 65: without a cap every run gets a slot.
    capped_room = max(0, status.cap - status.total - max(0, reserve))
    room = capped_room if status.capped else len(items)
    out: list[SpacedSlot] = []
    after: datetime | None = None
    tz = _channel_tz(channel_id) if one_per_day else None
    if tz is not None and not_on is not None:
        after = _end_of_local_day(not_on, tz)
    for index, (run_id, title) in enumerate(items):
        if index >= room:
            out.append(
                SpacedSlot(
                    run_id=int(run_id),
                    title=str(title),
                    skipped=f"cadence cap {status.cap}/{status.window_days}d reached",
                )
            )
            continue
        when = planned_post_time(channel_id, topic, run_id=int(run_id), after=after)
        after = _end_of_local_day(when, tz) if tz is not None else when
        out.append(SpacedSlot(run_id=int(run_id), title=str(title), publish_at=when))
    return out


def _override_held(features_json: str) -> bool:
    """True when this run, or the long video it was cut from, rendered past the gate."""
    try:
        features = json.loads(features_json or "{}")
    except (TypeError, ValueError):
        features = {}
    if not isinstance(features, dict):
        return False
    if features.get("grounding_override"):
        return True
    parent = features.get("parent_run_id")
    if not parent:
        return False
    # #1013: one rule for the parent - go-public's - so a claim confirmed with
    # `verify-claim` releases a Short cut from the run here too.
    from publishing.go_public import override_held

    try:
        return override_held(int(parent))
    except (TypeError, ValueError):
        return False


def slot_privacy(requested: str | None, *, features_json: str = "") -> str:
    """Public at the slot by default; never public for a grounding override."""
    privacy = (requested or "public").strip().lower() or "public"
    if privacy == "public" and _override_held(features_json):
        return "unlisted"
    return privacy


# Wave 105 (the operator, 2026-10-17: "Two a day, noon + 10 PM"): the stranded renders.
_TWICE_DAILY = (12, 22)
_FIRST_LEAD = timedelta(minutes=90)


def twice_daily_slots(
    channel_id: str,
    count: int,
    *,
    now: datetime | None = None,
    hours: tuple[int, ...] = _TWICE_DAILY,
    lead: timedelta = _FIRST_LEAD,
) -> list[datetime]:
    """`count` public slots at noon and 10 PM in the channel's zone, the first one at least
    `lead` away - an upload has to finish before its slot."""
    tz = _channel_tz(channel_id)
    earliest = ((now or datetime.now(timezone.utc)) + lead).astimezone(tz)
    out: list[datetime] = []
    day = earliest.date()
    while len(out) < count:
        for hour in sorted(hours):
            slot = datetime.combine(day, time(hour, 0), tzinfo=tz)
            if slot >= earliest and len(out) < count:
                out.append(slot.astimezone(timezone.utc))
        day += timedelta(days=1)
    return out


_EVENING = (18,)  # #1285: the extra slot a news video gets to stay inside its window


def _taken_slots(channel_id: str) -> set[datetime]:
    """Publish times other uploads already hold: pending upload jobs' `youtube_publish_at` and
    the scheduled rows of the publish log (#1285: a second run would have landed on run 153's
    Sunday noon). Fail-open."""
    taken: set[datetime] = set()
    try:
        from storage.repositories.jobs import get_job_repository

        for job in get_job_repository().list_active_jobs() or []:
            if str(getattr(job, "status", "")) != "pending" or job.job_type != "upload":
                continue
            if str(getattr(job, "channel_id", "") or "") != channel_id:
                continue
            payload = json.loads(getattr(job, "payload_json", "") or "{}")
            when = _when(payload.get("youtube_publish_at"))
            if when is not None:
                taken.add(when.astimezone(timezone.utc))
    except Exception as exc:
        logger.debug("taken slots: jobs unread: %s", exc)
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        for row in get_publish_log_repository().list_future_scheduled(channel_id) or []:
            when = _when(getattr(row, "published_at", None))
            if when is not None:
                taken.add(when.astimezone(timezone.utc))
    except Exception as exc:
        logger.debug("taken slots: publish log unread: %s", exc)
    return taken


def free_slots(
    channel_id: str,
    count: int,
    *,
    now: datetime | None = None,
    hours: tuple[int, ...] = _TWICE_DAILY,
    taken: set[datetime] | None = None,
) -> list[datetime]:
    """`twice_daily_slots` without the ones other uploads already hold."""
    held = _taken_slots(channel_id) if taken is None else set(taken)
    candidates = twice_daily_slots(channel_id, count + len(held), now=now, hours=hours)
    return [slot for slot in candidates if slot not in held][:count]


def _window_days(run_id: int, channel_id: str) -> float:
    from core.stale_renders import _news_window
    from storage.repositories.content_runs import get_content_run_repository

    run = get_content_run_repository().get(int(run_id))
    return float(_news_window(run, channel_id)) if run is not None else 7.0


def _age_days(run_id: int) -> float:
    from core.stale_renders import render_age_days
    from storage.repositories.content_runs import get_content_run_repository

    run = get_content_run_repository().get(int(run_id))
    age = render_age_days(run) if run is not None else None
    return float(age) if age is not None else 0.0


def _when(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        moment = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def shelf_schedule(
    channel_id: str, *, run_ids: list[int] | None = None, now: datetime | None = None
) -> list[SpacedSlot]:
    """Public slots for the rendered, never-uploaded videos on the shelf (wave 105).

    A game first (its draft's `event_at`), then news - the one whose window ends soonest
    first - then the rest, two a day (`twice_daily_slots`). A game that has started, a news
    video already past its window, or a game with no slot before it is listed with why.
    """
    from core.batch_review import draft_meta_for_run
    from core.stale_renders import shelf_rows

    moment = now or datetime.now(timezone.utc)
    wanted = {int(r) for r in run_ids} if run_ids else None
    ranked: list[tuple[tuple[int, float], SpacedSlot, datetime | None, datetime | None]] = []
    left: list[SpacedSlot] = []
    for row in shelf_rows(channel_id):
        if row.get("state") != "rendered, never uploaded":
            continue
        run_id = int(row.get("run_id") or 0)
        if not run_id or (wanted is not None and run_id not in wanted):
            continue
        slot = SpacedSlot(run_id=run_id, title=str(row.get("title") or ""))
        event = _when((draft_meta_for_run(channel_id, run_id) or {}).get("event_at"))
        window, age = _window_days(run_id, channel_id), _age_days(run_id)
        if event is not None and event <= moment:
            slot.skipped = "its game has started"
            left.append(slot)
            continue
        if event is None and age > window:
            slot.skipped = f"past its {window:.0f}-day window ({age:.1f} days old)"
            left.append(slot)
            continue
        deadline: datetime | None = None
        if event is not None:
            key, deadline = (0, event.timestamp()), event
        elif window < 7:
            key, deadline = (1, window - age), moment + timedelta(days=window - age)
        else:
            key = (2, float(run_id))
        ranked.append((key, slot, event, deadline))
    ranked.sort(key=lambda item: item[0])
    taken = _taken_slots(channel_id)
    main = free_slots(channel_id, len(ranked), now=moment, taken=taken)
    evening = free_slots(channel_id, len(ranked), now=moment, hours=_EVENING, taken=taken)
    out: list[SpacedSlot] = []
    for _key, slot, event, deadline in ranked:
        when = main[0] if main else None
        if when is not None and (deadline is None or when < deadline):
            slot.publish_at = main.pop(0)
        else:
            # #1285: a 6 PM slot inside the window, without using up a noon/10 PM place.
            extra = next((e for e in evening if deadline is not None and e < deadline), None)
            if extra is not None:
                evening.remove(extra)
                slot.publish_at = extra
            else:
                slot.skipped = "no slot before its game" if event else "would be past its window"
        out.append(slot)
    return out + left


def queue_spaced_uploads(
    slots: list[SpacedSlot],
    *,
    channel_id: str,
    privacy_status: str | None = None,
) -> list[int]:
    """Enqueue the planned slots. Skipped ones are left alone. Never raises.

    `privacy_status=None` means public at the slot, downgraded per run by `slot_privacy`.
    """
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    queued: list[int] = []
    for slot in slots:
        if slot.publish_at is None:
            continue
        try:
            record = repo.get(int(slot.run_id))
        except Exception as exc:
            logger.warning("spaced queue: run %s unreadable: %s", slot.run_id, exc)
            continue
        path = str(getattr(record, "mp4_path", "") or "") if record is not None else ""
        if not path:
            logger.warning("spaced queue: run %s has no mp4", slot.run_id)
            continue
        try:
            tags = json.loads(getattr(record, "tags_json", "") or "[]")
        except (TypeError, ValueError):
            tags = []
        try:
            privacy = slot_privacy(
                privacy_status, features_json=str(getattr(record, "features_json", "") or "")
            )
        except Exception as exc:
            logger.debug("spaced queue: privacy check for run %s failed: %s", slot.run_id, exc)
            privacy = "unlisted"
        try:
            result = enqueue_repurpose_jobs(
                channel_id=channel_id,
                content_run_id=int(slot.run_id),
                file_path=path,
                title=str(getattr(record, "title", "") or slot.title),
                description=str(getattr(record, "description", "") or ""),
                tags=tags,
                privacy_status=privacy,
                youtube_publish_at=slot.publish_at,
            )
        except Exception as exc:
            logger.warning("spaced queue: run %s not enqueued: %s", slot.run_id, exc)
            continue
        if getattr(result, "jobs", None):
            slot.privacy = privacy
            queued.append(int(slot.run_id))
    return queued
