"""
Optimal YouTube post times — channel + domain schedules, analytics-ready.

Static slots live in channels.json. When enough timed publish outcomes exist,
learn_slots_from_analytics() derives better weekday/hour slots from engagement.
Set USE_LEARNED_POST_SLOTS=auto (default) to prefer learned slots when available.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apis.topic_scorer import infer_domain
from config.channels import get_channel_profile, resolve_channel_id
from core.recommender_confidence import confidence_note

# Python weekday: Monday=0 … Sunday=6
DEFAULT_TAPIN_SLOTS = (
    (3, 18, 0),  # Thu 6pm
    (4, 17, 0),  # Fri 5pm
    (5, 11, 0),  # Sat 11am
    (5, 19, 0),  # Sat 7pm
    (6, 12, 0),  # Sun noon
    (6, 18, 0),  # Sun 6pm
)

DEFAULT_DOMAIN_SLOTS = {
    "gaming": DEFAULT_TAPIN_SLOTS,
    "ufc": (
        (3, 17, 0),  # Thu — fight-week hype
        (4, 18, 0),  # Fri
        (5, 18, 0),  # Sat
    ),
    "nba": (
        (2, 19, 0),  # Wed evening games
        (5, 11, 30),  # Sat late morning
        (6, 19, 0),  # Sun primetime
    ),
    "nfl": (
        (6, 10, 0),  # Sun morning
        (0, 19, 0),  # Mon evening recap
    ),
    "finance": (
        (0, 8, 30),  # Mon pre-market
        (2, 8, 30),  # Wed pre-market
        (4, 8, 30),  # Fri pre-market
        (6, 18, 0),  # Sun "week ahead"
    ),
}


@dataclass(frozen=True)
class PostSlot:
    weekday: int
    hour: int
    minute: int = 0


@dataclass
class PostScheduleConfig:
    timezone: str = "America/New_York"
    slots: tuple[PostSlot, ...] = ()
    domain_slots: dict[str, tuple[PostSlot, ...]] = None

    def __post_init__(self):
        if self.domain_slots is None:
            self.domain_slots = {}


def _parse_slot(raw) -> PostSlot | None:
    if not isinstance(raw, dict):
        return None
    try:
        return PostSlot(
            weekday=int(raw["weekday"]),
            hour=int(raw["hour"]),
            minute=int(raw.get("minute", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_slots_list(raw) -> tuple[PostSlot, ...]:
    if not isinstance(raw, list):
        return ()
    out = []
    for item in raw:
        slot = _parse_slot(item)
        if slot and 0 <= slot.weekday <= 6:
            out.append(slot)
    return tuple(out)


def _engagement_from_metrics(metrics_json: str) -> float | None:
    try:
        metrics = json.loads(metrics_json or "{}")
    except json.JSONDecodeError:
        return None
    if "engaged_rate" in metrics:
        return float(metrics["engaged_rate"])
    if metrics.get("alignment_score") is not None:
        return float(metrics["alignment_score"]) / 100.0
    return None


def _domain_from_metrics(metrics_json: str, fallback: str, channel_id: str) -> str:
    try:
        metrics = json.loads(metrics_json or "{}")
    except json.JSONDecodeError:
        metrics = {}
    domain = str(metrics.get("domain") or "").strip().lower()
    if domain:
        return domain
    title = str(metrics.get("title") or fallback or "")
    return infer_domain(title, channel_id)


def _collect_timed_samples(channel_id: str) -> list[tuple[str, datetime, float]]:
    from storage.repositories.publish_log import get_publish_log_repository

    samples: list[tuple[str, datetime, float]] = []
    for row in get_publish_log_repository().list_timed_outcomes(channel_id):
        when = row.published_at
        if not when:
            continue
        engagement = _engagement_from_metrics(row.metrics_json)
        if engagement is None or engagement <= 0:
            continue
        domain = _domain_from_metrics(row.metrics_json, row.detail, channel_id)
        samples.append((domain, when, engagement))
    return samples


def _load_static_post_schedule(channel_id: str | None = None) -> PostScheduleConfig:
    """Load schedule from channels.json or built-in TapIn defaults."""
    from config.channels import _load_channels_file

    channel_id = resolve_channel_id(channel_id)
    raw = _load_channels_file()
    channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
    cfg = channels.get(channel_id, {}) if isinstance(channels, dict) else {}
    block = cfg.get("post_schedule") or {}

    tz = str(block.get("timezone", "America/New_York"))
    default_slots = _parse_slots_list(block.get("default_slots"))
    domain_slots: dict[str, tuple[PostSlot, ...]] = {}

    raw_domain = block.get("domain_slots") or {}
    if isinstance(raw_domain, dict):
        for domain, slots in raw_domain.items():
            parsed = _parse_slots_list(slots)
            if parsed:
                domain_slots[str(domain)] = parsed

    if not default_slots and channel_id == "tapin":
        default_slots = tuple(PostSlot(w, h, m) for w, h, m in DEFAULT_TAPIN_SLOTS)
        if not domain_slots:
            domain_slots = {
                d: tuple(PostSlot(w, h, m) for w, h, m in slots)
                for d, slots in DEFAULT_DOMAIN_SLOTS.items()
            }

    if not default_slots:
        profile = get_channel_profile(channel_id)
        domain = profile.domain or "neutral"
        fallback = DEFAULT_DOMAIN_SLOTS.get(
            domain,
            ((4, 18, 0), (5, 12, 0), (6, 18, 0)),
        )
        default_slots = tuple(PostSlot(w, h, m) for w, h, m in fallback)

    return PostScheduleConfig(
        timezone=tz,
        slots=default_slots,
        domain_slots=domain_slots,
    )


def _use_learned_post_slots() -> bool:
    mode = os.getenv("USE_LEARNED_POST_SLOTS", "auto").strip().lower()
    return mode in ("1", "true", "yes", "auto")


def get_post_schedule(channel_id: str | None = None) -> PostScheduleConfig:
    """Static channel config, optionally overridden by analytics-learned slots."""
    channel_id = resolve_channel_id(channel_id)
    if _use_learned_post_slots():
        learned = learn_slots_from_analytics(channel_id)
        if learned:
            return learned
    return _load_static_post_schedule(channel_id)


def slots_for_topic(
    channel_id: str,
    topic: str = "",
) -> tuple[PostSlot, ...]:
    schedule = get_post_schedule(channel_id)
    domain = infer_domain(topic, channel_id)
    if domain in schedule.domain_slots:
        return schedule.domain_slots[domain]
    return schedule.slots


def _slot_candidates(
    channel_id: str,
    topic: str,
    *,
    after_local: datetime,
    days: int = 21,
) -> list[datetime]:
    schedule = get_post_schedule(channel_id)
    slots = slots_for_topic(channel_id, topic)
    if not slots:
        return []

    try:
        tz = ZoneInfo(schedule.timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")

    candidates: list[datetime] = []
    for day_offset in range(days):
        day = after_local.date() + timedelta(days=day_offset)
        for slot in slots:
            try:
                local_dt = datetime(
                    day.year,
                    day.month,
                    day.day,
                    slot.hour,
                    slot.minute,
                    tzinfo=tz,
                )
            except ValueError:
                continue
            if local_dt.weekday() != slot.weekday:
                continue
            if local_dt >= after_local:
                candidates.append(local_dt.astimezone(timezone.utc))
    return sorted(set(candidates))


def next_optimal_post_time(
    channel_id: str,
    topic: str = "",
    *,
    after: datetime | None = None,
    min_lead_minutes: int = 30,
) -> datetime:
    """
    Next open optimal slot (UTC). Skips times already reserved by the upload queue.
    """
    from analytics.upload_queue import get_reserved_publish_times

    channel_id = resolve_channel_id(channel_id)
    schedule = get_post_schedule(channel_id)

    after_utc = after or datetime.now(timezone.utc)
    if after_utc.tzinfo is None:
        after_utc = after_utc.replace(tzinfo=timezone.utc)

    reserved = get_reserved_publish_times(channel_id)
    if reserved:
        latest = max(reserved)
        after_utc = max(after_utc, latest + timedelta(minutes=1))

    try:
        tz = ZoneInfo(schedule.timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")

    earliest_local = (after_utc + timedelta(minutes=min_lead_minutes)).astimezone(tz)
    candidates = _slot_candidates(channel_id, topic, after_local=earliest_local)

    if not candidates:
        return after_utc + timedelta(hours=24)

    return candidates[0]


def format_scheduled_local(when_utc: datetime, channel_id: str) -> str:
    schedule = get_post_schedule(channel_id)
    try:
        tz = ZoneInfo(schedule.timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")
    if when_utc.tzinfo is None:
        when_utc = when_utc.replace(tzinfo=timezone.utc)
    local = when_utc.astimezone(tz)
    return local.strftime("%a %I:%M %p %Z").replace(" 0", " ")


# Explicit date + time (full date required — a year-less date can't be dated safely).
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %I:%M%p",
    "%Y-%m-%d %I%p",
)
# Bare clock time (no date) — combined with today/tomorrow by the caller.
_CLOCK_FORMATS = (
    "%H:%M",
    "%I:%M%p",
    "%I%p",
)


def _try_strptime(text: str, formats: tuple[str, ...]) -> datetime | None:
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_local_time_input(
    raw: str,
    channel_id: str | None = None,
    *,
    after: datetime | None = None,
) -> datetime | None:
    """Parse an operator time string into a UTC datetime, read in the channel's tz.

    Accepts a bare clock time (``9:30pm``, ``9:30 pm``, ``21:30``, ``9pm``) — rolled
    to the next future occurrence — an optional ``today``/``tomorrow`` prefix
    (``tomorrow 6pm``), or a full date + time (``2026-07-25 18:00``,
    ``2026-07-25 6:00pm``). Returns None when nothing parses so the caller can
    re-prompt or fall back. Never raises.
    """
    text = (raw or "").strip().lower()
    if not text:
        return None

    schedule = get_post_schedule(channel_id)
    try:
        tz = ZoneInfo(schedule.timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")

    after_utc = after or datetime.now(timezone.utc)
    if after_utc.tzinfo is None:
        after_utc = after_utc.replace(tzinfo=timezone.utc)
    now_local = after_utc.astimezone(tz)

    day_offset: int | None = None
    for word, offset in (("tomorrow", 1), ("today", 0)):
        if text.startswith(word):
            day_offset = offset
            text = text[len(word) :].strip()
            break
    if text.startswith("at "):
        text = text[3:].strip()

    # Explicit date + time wins when a date is present (ignore any day-word prefix).
    try:
        explicit = datetime.fromisoformat(text)
    except ValueError:
        explicit = _try_strptime(text, _DATETIME_FORMATS)
    if explicit is not None:
        local = explicit.replace(tzinfo=tz) if explicit.tzinfo is None else explicit.astimezone(tz)
        return local.astimezone(timezone.utc)

    # Bare clock time (try with and without an internal space, e.g. "9:30 pm").
    clock = _try_strptime(text, _CLOCK_FORMATS) or _try_strptime(
        text.replace(" ", ""), _CLOCK_FORMATS
    )
    if clock is None:
        return None

    base = now_local.date() + timedelta(days=day_offset or 0)
    local = datetime(base.year, base.month, base.day, clock.hour, clock.minute, tzinfo=tz)
    # An unqualified clock time already past today rolls to tomorrow.
    if day_offset is None and local <= now_local:
        local = local + timedelta(days=1)
    return local.astimezone(timezone.utc)


def _bucket_key(when_utc: datetime, tz: ZoneInfo) -> tuple[int, int, int]:
    if when_utc.tzinfo is None:
        when_utc = when_utc.replace(tzinfo=timezone.utc)
    local = when_utc.astimezone(tz)
    return local.weekday(), local.hour, 0


def _top_slots(
    scores: dict[tuple[int, int, int], float],
    *,
    limit: int,
) -> tuple[PostSlot, ...]:
    ranked = sorted(scores.items(), key=lambda item: -item[1])[:limit]
    return tuple(PostSlot(w, h, m) for (w, h, m), _ in ranked)


def _bucket_averages(
    sums: dict[tuple[int, int, int], float],
    counts: dict[tuple[int, int, int], int],
    min_bucket_samples: int,
) -> dict[tuple[int, int, int], float]:
    """Average engagement per (weekday, hour) bucket, keeping only buckets with at least
    ``min_bucket_samples`` posts. Falls back to all buckets when the floor would leave
    nothing (thin data) so a schedule can still be learned."""
    avg = {k: sums[k] / counts[k] for k in sums if counts[k] >= min_bucket_samples}
    if not avg:
        avg = {k: sums[k] / counts[k] for k in sums}
    return avg


@dataclass
class RecommendedTime:
    when_utc: datetime
    local_str: str
    source: str  # "analytics" | "static"
    avg_engaged_rate: float  # 0.0 when no history for the slot
    supporting_samples: int
    rationale: str


def _slot_engagement(
    channel_id: str,
    topic: str,
    when_utc: datetime,
) -> tuple[float, int]:
    """
    Average engagement + sample count for the (weekday, hour) bucket that
    `when_utc` falls in, drawn from the same timed publish history that
    learn_slots_from_analytics() uses. Prefers same-domain samples, then
    falls back to all domains in that slot.
    """
    samples = _collect_timed_samples(channel_id)
    if not samples:
        return 0.0, 0

    static = _load_static_post_schedule(channel_id)
    try:
        tz = ZoneInfo(static.timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")

    target = _bucket_key(when_utc, tz)
    domain = infer_domain(topic, channel_id) if topic else None

    same_domain = [
        eng
        for d, when, eng in samples
        if _bucket_key(when, tz) == target and (domain is None or d == domain)
    ]
    if same_domain:
        return sum(same_domain) / len(same_domain), len(same_domain)

    any_domain = [eng for _d, when, eng in samples if _bucket_key(when, tz) == target]
    if any_domain:
        return sum(any_domain) / len(any_domain), len(any_domain)
    return 0.0, 0


def get_recommended_time(
    channel_id: str,
    topic: str = "",
    *,
    after: datetime | None = None,
) -> RecommendedTime:
    """
    Recommend the next post time using the same history mechanics as best-bet:
    when enough timed engagement samples exist, slots are learned from analytics
    and the chosen slot is annotated with its historical engagement. Otherwise it
    falls back to the static channel/domain schedule.
    """
    channel_id = resolve_channel_id(channel_id)
    learned = learn_slots_from_analytics(channel_id) if _use_learned_post_slots() else None

    when_utc = next_optimal_post_time(channel_id, topic, after=after)
    local_str = format_scheduled_local(when_utc, channel_id)
    domain = infer_domain(topic, channel_id) if topic else "neutral"

    if learned:
        rate, n = _slot_engagement(channel_id, topic, when_utc)
        if n > 0:
            rationale = (
                f"learned from {n} past {domain} post(s) in this slot — "
                f"{rate:.1%} avg engagement"
                f"{confidence_note(n)}"
            )
        else:
            rationale = "learned from your post history (best-engagement weekday/hours)"
        return RecommendedTime(when_utc, local_str, "analytics", rate, n, rationale)

    n_samples = len(_collect_timed_samples(channel_id))
    if n_samples:
        need = max(0, 8 - n_samples)
        rationale = (
            f"default {domain} schedule — {need} more timed post(s) "
            f"until slots learn from analytics"
        )
    else:
        rationale = f"default {domain} schedule (no engagement analytics yet)"
    return RecommendedTime(when_utc, local_str, "static", 0.0, 0, rationale)


def display_recommended_time(rec: RecommendedTime) -> None:
    """Print the recommended post time, mirroring display_best_bet()."""
    tag = "analytics" if rec.source == "analytics" else "default schedule"
    print(f"\n  Recommended post time ({tag}): {rec.local_str}")
    print(f"  Reason : {rec.rationale}")


def learn_slots_from_analytics(
    channel_id: str,
    *,
    min_samples: int = 8,
    max_default_slots: int = 6,
    max_domain_slots: int = 3,
    min_domain_samples: int = 3,
    min_bucket_samples: int = 2,
) -> PostScheduleConfig | None:
    """
    Derive best weekday/hour slots from publish_log rows with published_at + engagement.

    Slots are ranked by **average** engaged-rate per (weekday, hour) bucket, not summed
    engagement — otherwise whichever day already gets the most posts wins on volume alone,
    so a schedule that leans weekend keeps re-learning the weekend. Buckets with fewer than
    ``min_bucket_samples`` posts are set aside so one lucky post can't top the list, unless
    the floor would leave nothing (thin data) — then all buckets count.
    Returns None until enough timed outcome data exists.
    """
    channel_id = resolve_channel_id(channel_id)
    samples = _collect_timed_samples(channel_id)
    if len(samples) < min_samples:
        return None

    static = _load_static_post_schedule(channel_id)
    try:
        tz = ZoneInfo(static.timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")

    overall_sum: dict[tuple[int, int, int], float] = defaultdict(float)
    overall_n: dict[tuple[int, int, int], int] = defaultdict(int)
    dom_sum: dict[str, dict[tuple[int, int, int], float]] = defaultdict(lambda: defaultdict(float))
    dom_n: dict[str, dict[tuple[int, int, int], int]] = defaultdict(lambda: defaultdict(int))

    for domain, when, engagement in samples:
        key = _bucket_key(when, tz)
        overall_sum[key] += engagement
        overall_n[key] += 1
        dom_sum[domain][key] += engagement
        dom_n[domain][key] += 1

    overall_avg = _bucket_averages(overall_sum, overall_n, min_bucket_samples)
    default_slots = _top_slots(overall_avg, limit=max_default_slots)
    if not default_slots:
        return None

    domain_slots: dict[str, tuple[PostSlot, ...]] = {}
    for domain, sums in dom_sum.items():
        counts = dom_n[domain]
        if sum(counts.values()) < min_domain_samples:
            continue
        picked = _top_slots(
            _bucket_averages(sums, counts, min_bucket_samples), limit=max_domain_slots
        )
        if picked:
            domain_slots[domain] = picked

    return PostScheduleConfig(
        timezone=static.timezone,
        slots=default_slots,
        domain_slots=domain_slots,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Recommend next post time")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--topic", default="", help="Topic for domain-aware slots")
    args = parser.parse_args()

    display_recommended_time(get_recommended_time(args.channel, args.topic))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
