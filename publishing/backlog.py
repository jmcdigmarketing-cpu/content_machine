"""`ops backlog`: fresh best bets into two weeks of scheduled videos (#949).

The operator wants to be away from the PC while videos keep publishing (2026-10-03). A video
uploaded private with `publishAt` goes public on YouTube's side, so only drafting, rendering
and uploading need the PC. Two things stopped a backlog: `core/spaced_queue` filled only the
next 7-day cadence window, and every draft waited for a yes in `ops batch-review`.

The operator's calls:

- **Slots** - `plan_backlog_slots` walks the post-time slots forward for `weeks` (2) and
  takes each one that keeps every rolling 7 days at or under the cadence cap, counting what
  is already published, scheduled or queued.
- **Topics** - fresh best bets. News (trending / calendar / news-shaped, `batch_review.
  freshness_window_days`) takes the first slots and is dropped when its slot would be more
  than `BACKLOG_NEWS_DAYS` (3) days out; evergreen topics fill the rest.
- **Approval** - a draft that clears every gate (`backlog_gate`: grade, unsupported claims,
  authenticity, hook, freshness) is rendered and queued on its own; anything else waits for
  `ops batch-review`. The operator vetoes with `ops backlog pull --run-id N`.

The worker uploads (about 6 a day on the default YouTube quota - the rest wait a day), and
each video goes public at its slot whether the PC is on or not.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("publishing.backlog")

_WINDOW = timedelta(days=7)
_NEWS_SOURCES = frozenset({"trending", "calendar"})
_GRADES = "ABCDF"


def news_days() -> int:
    try:
        return max(0, int(os.getenv("BACKLOG_NEWS_DAYS", "") or 3))
    except ValueError:
        return 3


def min_grade() -> str:
    raw = (os.getenv("BACKLOG_MIN_GRADE") or "B").strip().upper()[:1]
    return raw if raw in _GRADES else "B"


def _utc(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


# ---- slots ---------------------------------------------------------------------------------


def fits_cap(times: list[datetime], slot: datetime, cap: int) -> bool:
    """True when adding `slot` keeps every 7-day window that contains it at or under `cap`.

    The busiest window always starts on one of the videos, so checking the windows that
    start on each one (and contain the slot) is enough.
    """
    slot = _utc(slot)
    every = sorted([_utc(t) for t in times] + [slot])
    for start in every:
        if start <= slot < start + _WINDOW:
            if sum(1 for t in every if start <= t < start + _WINDOW) > cap:
                return False
    return True


def _taken_times(channel_id: str, now: datetime) -> list[datetime]:
    """Published in the last 7 days, scheduled on YouTube, and queued for upload."""
    times: list[datetime] = []
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        repo = get_publish_log_repository()
        for row in repo.list_uploaded_for_channel(channel_id):
            if row.published_at and _utc(row.published_at) > now - _WINDOW:
                times.append(_utc(row.published_at))
        for row in repo.list_future_scheduled(channel_id):
            if row.published_at:
                times.append(_utc(row.published_at))
    except Exception as exc:
        logger.debug("backlog: publish log unreadable: %s", exc)
    try:
        from storage.repositories.jobs import _parse_publish_from_payload, get_job_repository

        for job in get_job_repository().list_upload_jobs(channel_id):
            if getattr(job, "status", "") == "pending":
                when = _parse_publish_from_payload(getattr(job, "payload_json", "") or "{}")
                if when is not None:
                    times.append(_utc(when))
    except Exception as exc:
        logger.debug("backlog: upload queue unreadable: %s", exc)
    return sorted(set(times))


def plan_backlog_slots(
    channel_id: str, *, weeks: int = 2, now: datetime | None = None
) -> list[datetime]:
    """The post-time slots of the next `weeks` that fit under the cadence cap."""
    from analytics import post_timing
    from core.cadence import max_videos_per_week

    now = _utc(now or datetime.now(timezone.utc))
    cap = max_videos_per_week()
    taken = _taken_times(channel_id, now)
    horizon = now + timedelta(days=7 * max(1, weeks))
    out: list[datetime] = []
    after = now
    for _ in range(24 * 7 * max(1, weeks)):
        slot = _utc(post_timing.planned_post_time(channel_id, run_id=None, after=after))
        if slot > horizon or slot <= after:
            break
        if fits_cap(taken, slot, cap):
            taken.append(slot)
            out.append(slot)
        after = slot
    return out


# ---- topics --------------------------------------------------------------------------------


@dataclass
class BacklogItem:
    slot: datetime
    topic: str
    kind: str  # "news" | "evergreen"
    pick: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacklogDrop:
    topic: str
    reason: str


@dataclass
class TopicPlan:
    items: list[BacklogItem]
    dropped: list[BacklogDrop]


def topic_kind(option: Any, channel_id: str) -> str:
    """ "news" when the topic goes stale in days, else "evergreen"."""
    if str(getattr(option, "source", "") or "") in _NEWS_SOURCES:
        return "news"
    from core.batch_review import freshness_window_days

    meta = {"topic": str(getattr(option, "topic", "") or ""), "channel_id": channel_id}
    return "news" if freshness_window_days(meta) <= 2 else "evergreen"


def pick_backlog_topics(
    channel_id: str, slots: list[datetime], *, now: datetime | None = None
) -> TopicPlan:
    """Fresh best bets onto the slots: news first while it is still news, then evergreen."""
    from core import best_bet

    now = _utc(now or datetime.now(timezone.utc))
    options = best_bet.get_best_bets(channel_id, n=len(slots) + 3)
    news = [o for o in options if topic_kind(o, channel_id) == "news"]
    evergreen = [o for o in options if o not in news]
    limit = news_days()
    items: list[BacklogItem] = []
    for slot in slots:
        fresh = (_utc(slot).date() - now.date()).days <= limit
        if news and fresh:
            option, kind = news.pop(0), "news"
        elif evergreen:
            option, kind = evergreen.pop(0), "evergreen"
        else:
            continue
        pick = best_bet.pick_record(options, options.index(option) + 1, by="backlog")
        items.append(BacklogItem(slot=slot, topic=option.topic, kind=kind, pick=pick))
    first = (_utc(slots[0]).date() - now.date()).days if slots else 0
    why = (
        f"news - the first open slot is {first} days out, more than {limit}"
        if first > limit
        else f"news - no open slot left within {limit} days"
    )
    dropped = [BacklogDrop(o.topic, why) for o in news]
    return TopicPlan(items=items, dropped=dropped)


# ---- the gate ------------------------------------------------------------------------------


def backlog_gate(draft: Any) -> list[str]:
    """Why a draft may not render on its own; [] when it clears every gate."""
    from core import video_grade
    from core.batch_review import draft_age_days, freshness_window_days
    from core.claim_types import blocking_unsupported

    meta = draft.meta
    reasons: list[str] = []
    try:
        grade = video_grade.grade_run(int(draft.run_id))
    except Exception as exc:
        logger.debug("backlog: grade for run %s unavailable: %s", draft.run_id, exc)
        grade = None
    floor = min_grade()
    letter = str(getattr(grade, "letter", "") or "").upper()[:1]
    if not letter:
        reasons.append("no grade")
    elif letter not in _GRADES or _GRADES.index(letter) > _GRADES.index(floor):
        reasons.append(f"grade {letter} (needs {floor} or better)")
    blocking = blocking_unsupported(meta.get("claim_verification"))
    if blocking:
        reasons.append(f"{len(blocking)} unsupported claim(s)")
    if str(meta.get("authenticity_verdict") or "") == "block":
        reasons.append("authenticity block")
    if str(meta.get("hook_verdict") or "") == "weak":
        reasons.append("weak hook")
    age = draft_age_days(meta)
    if age is not None and age > freshness_window_days(meta):
        reasons.append(f"stale ({age:.0f} days old)")
    return reasons


# ---- the run -------------------------------------------------------------------------------


def upload_days(count: int) -> int:
    """Days with the PC on that `count` uploads take on the YouTube quota."""
    from apis.youtube_quota import UNITS_VIDEO_INSERT, daily_limit

    per_day = max(1, daily_limit() // UNITS_VIDEO_INSERT)
    return math.ceil(max(0, count) / per_day)


def projected_cost(channel_id: str, topics: list[str]) -> float | None:
    """Voice, LLM, signals and thumbnail for each topic at its recommended length."""
    try:
        from assets.flux_thumbnail import expected_provider
        from core.batch_generation import _length_choice
        from core.cost_meter import estimate_run_cost
        from core.script_length import get_length_preset

        total = 0.0
        for topic in topics:
            choice = _length_choice(channel_id, topic)
            words = get_length_preset(choice).target_words
            total += float(
                estimate_run_cost(
                    script="word " * words,
                    rendered=True,
                    length_choice=choice,
                    thumbnail_provider=expected_provider(),
                )["total"]
            )
        return total
    except Exception as exc:
        logger.debug("backlog: cost projection skipped: %s", exc)
        return None


@dataclass
class BacklogSummary:
    planned: int = 0
    queued: list[int] = field(default_factory=list)
    waiting: list[int] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _local(when: datetime | None, channel_id: str) -> str:
    if when is None:
        return "no slot"
    try:
        from analytics.post_timing import format_scheduled_local

        return str(format_scheduled_local(when, channel_id))
    except Exception:
        return when.isoformat()


def _pick_thumbnail(run_id: int, channel_id: str) -> None:
    """A dual-thumbnail render waits for a human pick; the backlog takes the experiment's
    next arm (least assigned first), so no upload waits."""
    try:
        from core.experiments import next_arm
        from core.thumbnail_pick import pick_thumbnail

        chosen = next_arm(channel_id, kind="thumbnail")
        arm = chosen[1] if chosen else ("text_on" if run_id % 2 else "face_forward")
        pick_thumbnail(run_id, None, arm=arm, channel_id=channel_id)
    except Exception as exc:
        logger.warning("backlog: thumbnail pick for run %s failed: %s", run_id, exc)


def run_backlog(
    channel_id: str,
    *,
    weeks: int = 2,
    dry_run: bool = False,
    yes: bool = False,
    ask: Callable[[str], str] | None = None,
    print_fn: Callable[..., Any] = print,
    now: datetime | None = None,
) -> BacklogSummary:
    from core import batch_generation, batch_review, spaced_queue, thumbnail_pick
    from core.spaced_queue import SpacedSlot

    summary = BacklogSummary()
    slots = plan_backlog_slots(channel_id, weeks=weeks, now=now)
    if not slots:
        print_fn(
            f"Backlog - {channel_id}: no open slot in the next {weeks} week(s) under the cadence cap."
        )
        return summary
    plan = pick_backlog_topics(channel_id, slots, now=now)
    summary.planned = len(plan.items)
    print_fn(
        f"Backlog - {channel_id}: {len(plan.items)} video(s) for {len(slots)} open slot(s) "
        f"over {weeks} week(s)"
    )
    for item in plan.items:
        print_fn(f"  {_local(item.slot, channel_id)}  {item.kind:<9} {item.topic}")
    if len(plan.items) < len(slots):
        print_fn(f"  {len(slots) - len(plan.items)} slot(s) left empty - not enough topics")
    for drop in plan.dropped:
        print_fn(f"  dropped: {drop.topic} ({drop.reason})")
    cost = projected_cost(channel_id, [i.topic for i in plan.items])
    days = upload_days(len(plan.items))
    shown = f"~${cost:.2f}" if cost is not None else "unknown"
    print_fn(
        f"  projected: {shown} for {len(plan.items)} video(s); uploading takes {days} PC-day(s) "
        "on the YouTube quota"
    )
    if dry_run or not plan.items:
        print_fn("  Dry run - nothing drafted." if dry_run else "  Nothing to draft.")
        return summary
    if not yes:
        if ask is None:
            from core.ask import ask_text

            ask = ask_text
        answer = ask(f"Draft, render and schedule {len(plan.items)} video(s)? [y/N]: ")
        if answer.strip().lower() not in ("y", "yes"):
            print_fn("  Nothing done.")
            return summary

    picks = {i.topic: i.pick for i in plan.items if i.pick}
    outcomes = batch_generation.run_batch(channel_id, [i.topic for i in plan.items], picks=picks)
    by_topic = {o.topic: o for o in outcomes}
    drafts = {d.run_id: d for d in batch_review.pending_drafts(channel_id)}
    to_queue: list[SpacedSlot] = []
    for item in plan.items:
        outcome = by_topic.get(item.topic)
        if outcome is None or not outcome.ok or not outcome.run_id:
            why = getattr(outcome, "error", "") or "no draft"
            summary.failed.append(item.topic)
            print_fn(f"  ! {item.topic}: not drafted ({why})")
            continue
        draft = drafts.get(int(outcome.run_id))
        if draft is None:
            summary.failed.append(item.topic)
            print_fn(f"  ! {item.topic}: draft {outcome.run_id} not found")
            continue
        reasons = backlog_gate(draft)
        if reasons:
            summary.waiting.append(draft.run_id)
            print_fn(
                f"  - waits for review: {draft.title} (run {draft.run_id}: {'; '.join(reasons)})"
            )
            continue
        batch_review._write_review(draft, decision="accepted", by="backlog")
        try:
            batch_review._render(draft, False)
        except Exception as exc:
            summary.failed.append(item.topic)
            print_fn(f"  ! {draft.title}: not rendered ({exc}); `ops batch-review` renders it")
            continue
        if thumbnail_pick.dual_thumbnail_enabled(channel_id):
            _pick_thumbnail(draft.run_id, channel_id)
        batch_review._write_review(
            draft, decision="rendered", by="backlog", publish_at=item.slot.isoformat()
        )
        to_queue.append(SpacedSlot(run_id=draft.run_id, title=draft.title, publish_at=item.slot))
    summary.queued = (
        spaced_queue.queue_spaced_uploads(to_queue, channel_id=channel_id) if to_queue else []
    )
    for slot in to_queue:
        state = (
            "queued" if slot.run_id in summary.queued else "rendered, not queued (no video file)"
        )
        print_fn(
            f"  [{slot.run_id}] {state} for {_local(slot.publish_at, channel_id)}: {slot.title}"
        )
    print_fn(
        f"  Queued {len(summary.queued)}. Upload them: py -m scripts.ops worker "
        f"(about {upload_days(len(summary.queued))} PC-day(s)); YouTube publishes each at its slot."
    )
    if summary.waiting:
        print_fn(
            f"  {len(summary.waiting)} wait for you: py -m scripts.ops batch-review --channel {channel_id}"
        )
    print_fn("  Veto one before it goes out: py -m scripts.ops backlog pull --run-id <run>")
    return summary


# ---- what is scheduled, and the veto -------------------------------------------------------


def scheduled_lines(channel_id: str) -> list[str]:
    """`ops backlog list`: what is queued to upload and what YouTube will publish."""
    lines = [f"Backlog - {channel_id}: scheduled"]
    rows: list[tuple[datetime, str]] = []
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        for row in get_publish_log_repository().list_future_scheduled(channel_id):
            if row.published_at:
                rows.append(
                    (
                        _utc(row.published_at),
                        f"on YouTube {row.youtube_video_id} (run {row.content_run_id}): {row.detail or ''}",
                    )
                )
    except Exception as exc:
        logger.debug("backlog list: publish log unreadable: %s", exc)
    try:
        from storage.repositories.jobs import _parse_publish_from_payload, get_job_repository

        for job in get_job_repository().list_upload_jobs(channel_id):
            if getattr(job, "status", "") != "pending":
                continue
            when = _parse_publish_from_payload(getattr(job, "payload_json", "") or "{}")
            if when is not None:
                rows.append(
                    (_utc(when), f"waiting to upload (run {job.content_run_id}, job {job.id})")
                )
    except Exception as exc:
        logger.debug("backlog list: upload queue unreadable: %s", exc)
    if not rows:
        return [
            *lines,
            "  nothing scheduled (py -m scripts.ops backlog --dry-run plans the next two weeks)",
        ]
    for when, text in sorted(rows):
        lines.append(f"  {_local(when, channel_id)}  {text}")
    return lines


def pull(channel_id: str, run_id: int) -> str:
    """The operator's veto: stop a queued upload, or take a scheduled video back to private."""
    notes: list[str] = []
    try:
        from storage.repositories.jobs import JOB_FAILED, get_job_repository

        repo = get_job_repository()
        for job in repo.list_upload_jobs(channel_id):
            if getattr(job, "content_run_id", None) == int(run_id) and job.status == "pending":
                repo.update(
                    job.id,
                    {
                        "status": JOB_FAILED,
                        "last_error": "pulled by the operator (ops backlog pull)",
                    },
                )
                notes.append(
                    f"run {run_id}: queued upload (job {job.id}) cancelled - it will not upload"
                )
    except Exception as exc:
        notes.append(f"run {run_id}: upload queue unreadable ({exc})")
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        log = get_publish_log_repository()
        rows = [
            r for r in log.list_future_scheduled(channel_id)
            if r.content_run_id == int(run_id) and r.youtube_video_id
        ]  # fmt: skip
    except Exception as exc:
        rows = []
        notes.append(f"run {run_id}: publish log unreadable ({exc})")
    for row in rows:
        video = str(row.youtube_video_id)
        if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
            notes.append(
                f"run {run_id} is on YouTube as {video}, scheduled: not changed - "
                "YOUTUBE_UPLOAD_ENABLED is not true (or set it private in YouTube Studio)"
            )
            continue
        from publishing.snippet_update import manage_scope_problem

        problem = manage_scope_problem(channel_id)
        if problem:
            notes.append(f"run {run_id} ({video}): not changed - {problem}")
            continue
        try:
            from youtube.oauth import get_youtube_service

            body = {
                "id": video,
                "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
            }
            get_youtube_service(channel_id).videos().update(part="status", body=body).execute()
            log.update(row.id, {"status": "pulled", "privacy_status": "private"})
            notes.append(f"run {run_id} ({video}): now private and no longer scheduled")
        except Exception as exc:
            notes.append(f"run {run_id} ({video}): not changed - {exc}")
    return "\n".join(notes) or f"Nothing queued or scheduled for run {run_id}."
