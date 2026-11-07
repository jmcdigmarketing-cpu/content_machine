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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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
    # #1298: the free noon/10 PM slots, the ones other uploads hold left out - the
    # `planned_post_time` this used knew neither, and gave two Shorts 7 PM and a Friday.
    # While a post_time experiment runs (#912), each run's arm decides its hour instead.
    experiment = _post_time_running(channel_id)
    pool = [] if experiment else free_slots(channel_id, 2 * len(items) + 6, now=_now())
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
        if experiment:
            when = planned_post_time(channel_id, topic, run_id=int(run_id), after=after)
        else:
            free = next((slot for slot in pool if after is None or slot > after), None)
            if free is None:
                out.append(SpacedSlot(run_id=int(run_id), title=str(title), skipped="no free slot"))
                continue
            pool.remove(free)
            when = free
        after = _end_of_local_day(when, tz) if tz is not None else when
        out.append(SpacedSlot(run_id=int(run_id), title=str(title), publish_at=when))
    return out


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _post_time_running(channel_id: str) -> bool:
    try:
        from config.channels import resolve_channel_id
        from core.experiments import active_experiment

        return bool(active_experiment(resolve_channel_id(channel_id), "post_time"))
    except Exception as exc:
        logger.debug("post_time experiment unread: %s", exc)
        return False


# #1295 (2026-10-18): the Chargers preview had no slot before kickoff - noon was run 153's and
# 6 PM was after the game. A game preview with none goes public as it uploads: a `publishAt`
# this far ahead (the worker runs every 15 minutes), so the unlisted review hold does not apply.
_ASAP_LEAD = timedelta(minutes=45)
_BESIDE = timedelta(minutes=10)  # #1980: a dated draft whose day has no free slot
_ASAP_GAP = timedelta(minutes=30)


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
    hours_on: Callable[[date], tuple[int, ...]] | None = None,
) -> list[datetime]:
    """`count` public slots at noon and 10 PM in the channel's zone, the first one at least
    `lead` away - an upload has to finish before its slot. ``hours_on`` (#1868) gives a day's
    hours instead - launch week's extra GTA 6 hour."""
    tz = _channel_tz(channel_id)
    earliest = ((now or datetime.now(timezone.utc)) + lead).astimezone(tz)
    out: list[datetime] = []
    day = earliest.date()
    while len(out) < count:
        for hour in sorted(hours_on(day) if hours_on else hours):
            slot = datetime.combine(day, time(hour, 0), tzinfo=tz)
            if slot >= earliest and len(out) < count:
                out.append(slot.astimezone(timezone.utc))
        day += timedelta(days=1)
    return out


_EVENING = (18,)  # #1285: the extra slot a news video gets to stay inside its window

# #1727 (B06.6, wave 149): a long video that is not news - the Week in Review, a season explainer
# (#1724) - goes public at one weekly time, so a viewer learns when the next one comes. The three
# Weeks in Review went out Tuesday noon, Tuesday noon and Monday noon, at whatever slot was free.
# LONG_SLOT is "weekday@hour" in the channel's zone (Monday 0): "6@19" is Sunday 7 PM; "off" puts
# them back on the next free slot. Overnight compiles the week on the slot's own morning.
LONG_SLOT_DEFAULT = "6@19"
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_LONG_SLOT_WEEKS = 5


def long_slot() -> tuple[int, int] | None:
    """(weekday, hour) of the weekly long slot, or None when LONG_SLOT is off."""
    import os

    raw = (os.getenv("LONG_SLOT") or LONG_SLOT_DEFAULT).strip().lower()
    if raw in ("off", "false", "no", "none"):
        return None
    try:
        day, hour = (int(part) for part in raw.split("@"))
    except ValueError:
        day, hour = (int(part) for part in LONG_SLOT_DEFAULT.split("@"))
    if not (0 <= day <= 6 and 0 <= hour <= 23):
        day, hour = (int(part) for part in LONG_SLOT_DEFAULT.split("@"))
    return day, hour


def long_slot_words() -> str:
    """ "every Sunday" - what a script's follow line can promise ("every week" with the slot off).
    The day, not the hour: 7 PM is the channel's zone, not the viewer's."""
    slot = long_slot()
    return f"every {_WEEKDAYS[slot[0]]}" if slot else "every week"


def next_long_slot(channel_id: str, *, now: datetime | None = None) -> datetime | None:
    """The next free weekly long slot at least `_FIRST_LEAD` away, within five weeks, or None."""
    slot = long_slot()
    if slot is None:
        return None
    weekday, hour = slot
    moment = now or datetime.now(timezone.utc)
    tz = _channel_tz(channel_id)
    held = _taken_slots(channel_id)
    day = moment.astimezone(tz).date()
    day += timedelta(days=(weekday - day.weekday()) % 7)
    for _week in range(_LONG_SLOT_WEEKS):
        when = datetime.combine(day, time(hour, 0), tzinfo=tz).astimezone(timezone.utc)
        if when >= moment + _FIRST_LEAD and when not in held:
            return when
        day += timedelta(days=7)
    return None


def takes_long_slot(channel_id: str, run_id: int) -> bool:
    """#1727: a Week in Review, or a season explainer's draft (#1724) - not news."""
    from storage.repositories.content_runs import get_content_run_repository

    try:
        run = get_content_run_repository().get(int(run_id))
        features = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
        if isinstance(features, dict) and (features.get("compilation") or {}).get("week"):
            return True
        from core.batch_review import draft_meta_for_run

        return (draft_meta_for_run(channel_id, run_id) or {}).get("series") == "season"
    except Exception as exc:
        logger.debug("long slot unread for run %s: %s", run_id, exc)
        return False


def job_reserves_slot(content_run_id: object) -> bool:
    """#1558 (2026-10-23): a pending upload holds its publish time only when it can go public
    there. A run rendered past the grounding gate cannot - the uploader strips its publish time
    (`youtube_publisher.hold_flagged_schedule`) - yet run 186's job held Sat noon, the slot run
    184's UFC 333 preview needed before the card. Fail-open: an unread hold reserves."""
    if not content_run_id:
        return True
    try:
        from publishing.go_public import override_held

        return not override_held(int(content_run_id))  # type: ignore[call-overload]
    except Exception as exc:
        logger.debug("hold unread for run %s: %s", content_run_id, exc)
        return True


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
            if when is not None and job_reserves_slot(getattr(job, "content_run_id", None)):
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


# #1662 (B03.16, wave 154): never more than four Shorts a day, never two within three hours.
# Measured 11-06: in 30 days two went out within three hours 13 times, and one day had six.
MAX_A_DAY = 4
MIN_GAP = timedelta(hours=3)


def _recent_public(channel_id: str, moment: datetime) -> set[datetime]:
    """The public times of the last day's uploads - what a new slot is spaced from."""
    out: set[datetime] = set()
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
            when = _when(getattr(row, "published_at", None))
            if when is not None and moment - timedelta(days=1) <= when <= moment:
                out.add(when.astimezone(timezone.utc))
    except Exception as exc:
        logger.debug("recent public times unread: %s", exc)
    return out


def crowded(when: datetime, times: set[datetime] | list[datetime], channel_id: str) -> str:
    """#1662: why `when` is too close to the channel's other public times, or ""."""
    tz = _channel_tz(channel_id)
    day = when.astimezone(tz).date()
    others = [t for t in times if t != when]
    if sum(1 for t in others if t.astimezone(tz).date() == day) >= MAX_A_DAY:
        return f"{MAX_A_DAY} Shorts that day"
    if any(abs(t - when) < MIN_GAP for t in others):
        return "within 3 hours of another"
    return ""


def day_full(channel_id: str, now: datetime | None = None) -> str:
    """#1662: "4 Shorts that day" once today's public and scheduled ones reach `MAX_A_DAY`."""
    moment = now or datetime.now(timezone.utc)
    tz = _channel_tz(channel_id)
    today = moment.astimezone(tz).date()
    times = _taken_slots(channel_id) | _recent_public(channel_id, moment)
    if sum(1 for t in times if t.astimezone(tz).date() == today) >= MAX_A_DAY:
        return f"{MAX_A_DAY} Shorts that day"
    return ""


def free_slots(
    channel_id: str,
    count: int,
    *,
    now: datetime | None = None,
    hours: tuple[int, ...] = _TWICE_DAILY,
    taken: set[datetime] | None = None,
    hours_on: Callable[[date], tuple[int, ...]] | None = None,
) -> list[datetime]:
    """`twice_daily_slots` without the ones other uploads already hold."""
    held = _taken_slots(channel_id) if taken is None else set(taken)
    candidates = twice_daily_slots(
        channel_id, count + len(held), now=now, hours=hours, hours_on=hours_on
    )
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


def _run_title(run_id: int) -> str:
    from storage.repositories.content_runs import get_content_run_repository

    try:
        run = get_content_run_repository().get(int(run_id))
    except Exception as exc:
        logger.debug("run %s title unread: %s", run_id, exc)
        return ""
    return str(getattr(run, "title", "") or "")


def _when(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        moment = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def preview_event(
    channel_id: str, run_id: int, title: str, *, rendered: datetime
) -> datetime | None:
    """The start of the event a video previews: its draft's `event_at`, else (#1286) the event
    its title names - when the video was made before that event, so it is a preview."""
    from core.batch_review import draft_meta_for_run

    event = _when((draft_meta_for_run(channel_id, run_id) or {}).get("event_at"))
    if event is not None:
        return event
    try:
        from core.seasonal_calendar import event_for

        _name, start = event_for(title)
    except Exception as exc:
        logger.debug("named event unread for run %s: %s", run_id, exc)
        return None
    named = _when(start) if start else None
    return named if named is not None and rendered < named else None


def _planned_time(channel_id: str, run_id: int) -> datetime | None:
    """#1870: the time a draft's entry says it goes public (`publish_at`), or None."""
    try:
        from core.batch_review import draft_meta_for_run

        return _when((draft_meta_for_run(channel_id, run_id) or {}).get("publish_at"))
    except Exception as exc:
        logger.debug("planned time unread for run %s: %s", run_id, exc)
        return None


def slot_for_run(
    channel_id: str, run_id: int, *, title: str = "", now: datetime | None = None
) -> tuple[datetime | None, str]:
    """#1270: the public slot for one video - the next free noon/10 PM, before its game, inside
    its news window (6 PM when needed) - or (None, why). #1727: a Week in Review or a season
    explainer takes the weekly long slot - no news window, and "49ers" in run 202's title is not
    a game to beat."""
    moment = now or datetime.now(timezone.utc)
    if takes_long_slot(channel_id, run_id):
        weekly = next_long_slot(channel_id, now=moment)
        if weekly is not None:
            return weekly, ""
    if not title:  # the event a title names is the only guard a draft without event_at has
        title = _run_title(run_id)
    window, age = _window_days(run_id, channel_id), _age_days(run_id)
    event = preview_event(channel_id, run_id, title, rendered=moment - timedelta(days=age))
    if event is not None and event <= moment:
        return None, "its game has started"
    deadline = event
    if event is None and window < 7:
        if age > window:
            return None, f"past its {window:.0f}-day window"
        deadline = moment + timedelta(days=window - age)
    taken = _taken_slots(channel_id)
    planned = _planned_time(channel_id, run_id)  # #1870: launch day at the unlock
    if (planned is not None and planned >= moment + _FIRST_LEAD and planned not in taken
            and (deadline is None or planned < deadline)):  # fmt: skip
        return planned, ""
    # #1980 (wave 145, live 11-03): a dated draft never goes out before its own day. Queued the
    # evening before with every slot to its day's end taken, run 232 ("15 days to launch") fell
    # through to "45 minutes from now" and went public on Nov 3.
    floor, in_its_day = moment, True
    if planned is not None:
        tz = _channel_tz(channel_id)
        day_start = datetime.combine(planned.astimezone(tz).date(), time.min, tzinfo=tz).astimezone(
            timezone.utc
        )
        floor = max(moment, day_start - _FIRST_LEAD)  # the slots add the lead back
        in_its_day = moment >= day_start
    from core.series.dated import slot_hours

    # #1662: a slot within three hours of another public time, or on a day of four, is passed
    times = set(taken) | _recent_public(channel_id, moment)
    main = [s for s in free_slots(channel_id, 6, now=floor, taken=taken,
                                  hours_on=lambda day: slot_hours(channel_id, title, day))
            if not crowded(s, times, channel_id)]  # fmt: skip
    if main and (deadline is None or main[0] < deadline):
        return main[0], ""
    evening = free_slots(channel_id, 3, now=floor, hours=_EVENING, taken=taken)
    extra = next((e for e in evening if deadline is not None and e < deadline
                  and not crowded(e, times, channel_id)), None)  # fmt: skip
    if extra is not None:
        return extra, ""
    if (planned is not None and not in_its_day and planned >= moment + _FIRST_LEAD
            and (deadline is None or planned < deadline)):  # fmt: skip
        return planned + _BESIDE, ""  # its own day, beside the video that holds its slot
    if in_its_day and event is not None and moment + _ASAP_LEAD < event:
        return moment + _ASAP_LEAD, ""
    return None, "no slot before its game" if event else "no slot inside its window"


def shelf_schedule(
    channel_id: str, *, run_ids: list[int] | None = None, now: datetime | None = None
) -> list[SpacedSlot]:
    """Public slots for the rendered, never-uploaded videos on the shelf (wave 105).

    A game first (its draft's `event_at`), then news - the one whose window ends soonest
    first - then the rest, two a day (`twice_daily_slots`). A game that has started, a news
    video already past its window, or a game with no slot before it is listed with why.
    """
    from core.stale_renders import shelf_rows

    moment = now or datetime.now(timezone.utc)
    wanted = {int(r) for r in run_ids} if run_ids else None
    ranked: list[tuple[tuple[int, float], SpacedSlot, datetime | None, datetime | None]] = []
    left: list[SpacedSlot] = []
    for row in shelf_rows(channel_id):
        if row.get("state") != "rendered, never uploaded" and not row.get("event_started"):
            continue  # a started game stays listed, so requeue_upload --queue sees it skipped
        run_id = int(row.get("run_id") or 0)
        if not run_id or (wanted is not None and run_id not in wanted):
            continue
        slot = SpacedSlot(run_id=run_id, title=str(row.get("title") or ""))
        window, age = _window_days(run_id, channel_id), _age_days(run_id)
        event = preview_event(channel_id, run_id, slot.title, rendered=moment - timedelta(days=age))
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
    asap = moment + _ASAP_LEAD
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
            elif event is not None and asap < event:
                slot.publish_at, asap = asap, asap + _ASAP_GAP  # #1295: as it uploads
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
                # #1558: a run the grounding hold downgraded is never public at a slot - queue
                # it with no time, so it reserves nothing
                youtube_publish_at=None
                if privacy != ((privacy_status or "public").strip().lower() or "public")
                else slot.publish_at,
            )
        except Exception as exc:
            logger.warning("spaced queue: run %s not enqueued: %s", slot.run_id, exc)
            continue
        if getattr(result, "jobs", None):
            slot.privacy = privacy
            queued.append(int(slot.run_id))
    return queued
