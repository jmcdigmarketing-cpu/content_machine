"""#1666 (B03.20, wave 156): overnight's draft step also at 1 PM, for the evening's news.

Overnight drafts at 5 AM, so a story that breaks in the morning waits until the next night - a day
old when it goes out. Once a day, in the first worker pass from `MIDDAY_HOUR` until `LAST_HOUR` in
the channel's zone, this drafts up to `MIDDAY_DRAFTS` of the morning's news the way overnight
does (`collect_topics(news_only=True)` - its gate and lead order, no series or dated extras; one
process per draft, `draft_each`), holds each by the fast lane's checks (the unattended block
reasons, the second read), renders it in its own process and uploads it private with tonight's
slot as its publish time (decision 107) - so YouTube makes it public at 6 or 10 PM with the PC
asleep. Nothing is drafted when tonight has no free slot, or past overnight's cap of 8 waiting.

It runs inside the worker pass - no new scheduled task, no wake timers (the operator,
2026-11-06): a PC asleep from 1 to 5 PM makes nothing that day. Never on battery, under the
fast lane's YouTube units, while overnight beats, or while overnight is paused. One try a day,
recorded in `data/midday_<channel>.json`. `MIDDAY=false` turns it off (the suite does).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("jobs.midday")

MIDDAY_HOUR = 13
LAST_HOUR = 17  # from 5 PM a draft and its render would miss the 6 PM slot's lead
MIDDAY_DRAFTS = 2


def enabled() -> bool:
    return os.getenv("MIDDAY", "true").strip().lower() not in ("0", "false", "no", "off")


def store_path(channel_id: str) -> str:
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, f"midday_{channel_id}.json")


def load_store(channel_id: str) -> dict[str, Any]:
    try:
        with open(store_path(channel_id), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_store(channel_id: str, data: dict[str, Any]) -> None:
    path = store_path(channel_id)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
        os.replace(tmp, path)
    except OSError as exc:
        logger.debug("midday store not written: %s", exc)


def _local(channel_id: str, moment: datetime) -> datetime:
    from core.spaced_queue import _channel_tz

    return moment.astimezone(_channel_tz(channel_id))


def blocked(channel_id: str, *, now: datetime, store: dict[str, Any]) -> str:
    """Why the 1 PM step does not run this pass, or ""."""
    if not enabled():
        return "off (MIDDAY)"
    local = _local(channel_id, now)
    if not MIDDAY_HOUR <= local.hour < LAST_HOUR:
        return f"outside {MIDDAY_HOUR}:00-{LAST_HOUR}:00"
    if store.get("day") == local.date().isoformat():
        return "ran today"
    from jobs import fast_lane

    if fast_lane.units_left() < fast_lane.MIN_UNITS:
        return f"under {fast_lane.MIN_UNITS:,} YouTube units left"
    if fast_lane.on_battery():
        return "on battery"
    if fast_lane.overnight_running(now):
        return "overnight is running"
    from jobs.game_guard import game_running

    game = game_running()  # #2025: the operator's games come first
    if game:
        return f"a game is running ({game})"
    try:
        from core.overnight_pause import is_paused

        if is_paused():
            return "overnight is paused"
    except Exception as exc:
        logger.debug("pause unread: %s", exc)
    return ""


def tonight_slots(channel_id: str, now: datetime) -> list[datetime]:
    """Today's free public slots still ahead (an upload's lead away), none crowded (#1662)."""
    from core.series.dated import slot_hours
    from core.spaced_queue import _recent_public, _taken_slots, crowded, free_slots

    taken = _taken_slots(channel_id)
    times = set(taken) | _recent_public(channel_id, now)
    today = _local(channel_id, now).date()
    slots = free_slots(channel_id, 3, now=now, taken=taken,
                       hours_on=lambda day: slot_hours(channel_id, "", day))  # fmt: skip
    return [s for s in slots
            if _local(channel_id, s).date() == today and not crowded(s, times, channel_id)]  # fmt: skip


def _collect(channel_id: str, count: int, picks: dict[str, dict]) -> list[str]:
    from core.batch_generation import collect_topics

    return collect_topics(channel_id, None, None, count, picks=picks, news_only=True)


def _slot(channel_id: str, run_id: int) -> tuple[datetime | None, str]:
    from core.spaced_queue import slot_for_run

    return slot_for_run(channel_id, run_id)


def _render(channel_id: str, run_id: int) -> tuple[str, int]:
    """The fast lane's checks and render; uploaded private with tonight's slot (decision 107)."""
    from core.batch_review import _queue_scheduled
    from jobs.fast_lane import _render_and_queue

    return _render_and_queue(channel_id, run_id, by="midday", queue=_queue_scheduled)


def run_midday(
    channel_id: str,
    *,
    now: datetime | None = None,
    slots: Callable[[str, datetime], list[datetime]] | None = None,
    waiting: Callable[[str], int] | None = None,
    collect: Callable[[str, int, dict[str, dict]], list[str]] | None = None,
    draft: Callable[..., list[Any]] | None = None,
    render: Callable[[str, int], tuple[str, int]] | None = None,
    slot: Callable[[str, int], tuple[datetime | None, str]] | None = None,
) -> list[str]:
    """One try a day: the lines of what it drafted and queued, [] when it did not run."""
    if not enabled():  # off: not even the store is read
        return []
    moment = now or datetime.now(timezone.utc)
    store = load_store(channel_id)
    why = blocked(channel_id, now=moment, store=store)
    if why:
        logger.debug("midday: %s", why)
        return []
    from core.run_mode import hold_unattended

    held = hold_unattended("the 1 PM step")  # #2030: before the drafts spend anything
    if held:
        logger.warning("%s", held)
        return []
    store["day"] = _local(channel_id, moment).date().isoformat()
    save_store(channel_id, store)  # one try a day - a crash below is not retried every pass
    return _midday_lines(channel_id, moment, slots=slots, waiting=waiting, collect=collect,
                         draft=draft, render=render, slot=slot)  # fmt: skip


def _waiting(channel_id: str) -> int:
    from core.batch_review import pending_drafts

    return len(pending_drafts(channel_id))


def _midday_lines(channel_id: str, moment: datetime, **seams: Any) -> list[str]:
    from analytics.post_timing import format_scheduled_local
    from core.overnight import draft_count, draft_each

    head = "Midday (#1666)"
    try:
        open_slots = (seams.get("slots") or tonight_slots)(channel_id, moment)
    except Exception as exc:
        logger.warning("midday slots unread: %s", exc)
        return [f"{head}: tonight's slots unread - nothing drafted"]
    if not open_slots:
        return [f"{head}: tonight's slots are taken - nothing drafted"]
    waiting = (seams.get("waiting") or _waiting)(channel_id)
    want, _line = draft_count(waiting, min(MIDDAY_DRAFTS, len(open_slots)))
    if want <= 0:
        return [f"{head}: {waiting} drafts wait for a decision - nothing drafted"]
    picks: dict[str, dict] = {}
    topics = (seams.get("collect") or _collect)(channel_id, want, picks)[:want]
    if not topics:
        return [f"{head}: no story passed the topic gate - nothing drafted"]
    when = ", ".join(format_scheduled_local(s, channel_id) for s in open_slots)
    lines = [f"{head}: drafting {len(topics)} for tonight ({when})"]
    for outcome in (seams.get("draft") or draft_each)(channel_id, topics, picks=picks or None):
        run_id = int(getattr(outcome, "run_id", 0) or 0)
        topic = str(getattr(outcome, "topic", "") or "")[:60]
        if not getattr(outcome, "ok", False) or not run_id:
            lines.append(f"  {topic}: not drafted - {getattr(outcome, 'error', '') or 'no run'}")
            continue
        # #1810 / #2018: the slot is read the way the queue step reads it (`slot_for_run`, the
        # title, deadline and planned time) before a voice is paid - `tonight_slots` counted
        # free slots for any title, and a draft with none went up unlisted
        slot, no_slot = (seams.get("slot") or _slot)(channel_id, run_id)
        if slot is None:
            lines.append(f"  run {run_id} drafted, not voiced - no slot ({no_slot})")
            continue
        try:
            held, job = (seams.get("render") or _render)(channel_id, run_id)
        except Exception as exc:
            logger.warning("midday run %s not rendered: %s", run_id, exc)
            held, job = f"render failed - {str(exc)[:120]}", 0
        lines.append(f"  run {run_id} {held}" if held
                     else f"  run {run_id} rendered, queued for tonight's slot (job {job})")  # fmt: skip
    return lines
