"""#1648 (B03.2, wave 152): three Shorts a day for two weeks against two - measured.

A `slots` row with `"all": true` in `config/series.json` is the trial: inside its dates every title
gets its extra hour (`series/dated.slot_hours`) and overnight renders its `renders`. Its line
compares the trial's days with the 14 before them: public Shorts a day, the channel's organic views
a day (every video's daily views less its paid ones, summed - `analytics.promotions`), and the
median Short's organic views in its first week (`success.target.views_7d`, the measured ones).
Printed by the weekly report and `ops scoreboard`; read on the 27th, a week after it ends.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.cadence")

BEFORE_DAYS = 14
_COUNT_WORDS = {3: "Three", 4: "Four", 5: "Five"}


def cadence_trials(channel_id: str) -> list[dict[str, Any]]:
    """The channel's `slots` rows for every title - the cadence trials."""
    from core.series.countdown import series_rows

    return [r for r in series_rows(channel_id) if r.get("kind") == "slots" and r.get("all")]


def _metrics(row: Any) -> dict[str, Any]:
    try:
        data = json.loads(getattr(row, "metrics_json", "") or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _when(row: Any) -> datetime | None:
    when = getattr(row, "published_at", None)
    if not isinstance(when, datetime):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _is_long(run_id: int) -> bool:
    """A long video or a compilation - not a Short. False when unread."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        run = get_content_run_repository().get(int(run_id))
        features = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
        return bool(isinstance(features, dict)
                    and (features.get("long_form") or features.get("compilation")))  # fmt: skip
    except Exception:
        return False


def window_stats(
    rows: list[Any], start: date, end: date, *, is_long: Callable[[int], bool]
) -> dict[str, Any]:
    """{days, shorts, organic_a_day, per_short, n} for `start..end` (inclusive)."""
    from analytics.promotions import _organic_by_day, _per_day
    from core.success.target import views_7d

    days = max(1, (end - start).days + 1)
    shorts = 0
    first_weeks: list[int] = []
    series: list[dict[date, int]] = []
    for row in rows:
        metrics = _metrics(row)
        series.append(_organic_by_day(metrics))
        when = _when(row)
        run_id = int(getattr(row, "content_run_id", 0) or 0)
        if when is None or not start <= when.date() <= end or is_long(run_id):
            continue
        if str(getattr(row, "privacy_status", "") or "").lower() != "public":
            continue
        shorts += 1
        week = views_7d(metrics, when)
        if week is not None:
            first_weeks.append(int(week))
    return {"days": days, "shorts": shorts, "organic_a_day": _per_day(series, start, end),
            "per_short": statistics.median(first_weeks) if first_weeks else None,
            "n": len(first_weeks)}  # fmt: skip


def _part(stats: dict[str, Any]) -> str:
    organic = stats["organic_a_day"]
    per = stats["per_short"]
    return (f"{stats['shorts'] / stats['days']:.1f} Shorts a day, "
            + (f"{organic:,.0f} organic views a day" if organic is not None else "no views a day yet")
            + (f", {per:,.0f} per Short in its first week (n={stats['n']})" if per is not None
               else ", no Short's first week measured yet"))  # fmt: skip


def cadence_lines(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
    trials: list[dict[str, Any]] | None = None,
    is_long: Callable[[int], bool] | None = None,
) -> list[str]:
    """One line per trial that has started: its days so far against the `BEFORE_DAYS` before."""
    from core.series.dated import BASE_HOURS

    day = today or date.today()
    try:
        found = trials if trials is not None else cadence_trials(channel_id)
        if not found:
            return []
        if rows is None:
            from storage.repositories.publish_log import get_publish_log_repository, is_seeded

            rows = [r for r in get_publish_log_repository().list_uploaded_for_channel(channel_id)
                    or [] if not is_seeded(r)]  # fmt: skip
        lines: list[str] = []
        for trial in found:
            start = date.fromisoformat(str(trial["from"])[:10])
            stop = date.fromisoformat(str(trial["to"])[:10])
            if day < start:
                continue
            end = min(stop, day)
            slots = len(set(BASE_HOURS) | {int(h) for h in trial.get("extra_hours") or []})
            name = f"{_COUNT_WORDS.get(slots, str(slots))} Shorts a day"
            during = window_stats(rows, start, end, is_long=is_long or _is_long)
            before = window_stats(rows, start - timedelta(days=BEFORE_DAYS),
                                  start - timedelta(days=1), is_long=is_long or _is_long)  # fmt: skip
            total = (stop - start).days + 1
            to = f"{stop.day}" if (stop.year, stop.month) == (start.year, start.month) else (
                f"{stop:%b} {stop.day}")  # fmt: skip
            lines.append(f"{name} (#1648, {start:%b} {start.day}-{to}; day "
                         f"{min(total, (end - start).days + 1)} of {total}): {_part(during)} - the "
                         f"{BEFORE_DAYS} days before: {_part(before)}")  # fmt: skip
        return lines
    except Exception as exc:
        logger.debug("cadence lines skipped: %s", exc)
        return []
