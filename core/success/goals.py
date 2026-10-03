"""A goal and a scoreboard: views (#934; operator, 2026-10-03: the goal is views).

The goal lives in `config/goals.json`, one entry per channel, edited by hand:

    {"tapin": {"metric": "views", "target": 100000, "since": "2026-10-01",
               "by": "2026-12-31", "uploads_per_week": 5}}

Views come from the channel's views by day: the metrics sync asks YouTube Analytics for
the whole channel (`youtube_metrics.fetch_channel_daily_views`) and keeps the series in
`data/channel_views_<channel>.json`, merged by day so it survives the moving window. Until
that has run, the videos' own views by day (#563) are summed - seeded rows never count,
their days are invented.

The scoreboard says what is true this week: views so far against the target, the weekly
pace the target needs against the last four weeks' pace, where that pace lands by the
deadline, uploads this week against the plan, and the week's best and weakest video.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

from config.paths import DATA_DIR, ROOT_DIR
from core.logging import get_logger

logger = get_logger("core.success.goals")

GOALS_FILE = os.path.join(ROOT_DIR, "config", "goals.json")
CHANNEL_VIEWS_TEMPLATE = os.path.join(DATA_DIR, "channel_views_{channel}.json")
FOCUS_FILE = os.path.join(DATA_DIR, "weekly_focus.json")
HISTORY_TEMPLATE = os.path.join(DATA_DIR, "review_history_{channel}.json")
PACE_DAYS = 28
SYNC_DAYS = 90


def _today() -> date:
    return date.today()


def _read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def load_goal(channel_id: str) -> dict[str, Any] | None:
    """The channel's goal with its dates parsed, or None when unset or unreadable."""
    data = _read_json(GOALS_FILE)
    goal = data.get(channel_id) if isinstance(data, dict) else None
    if not isinstance(goal, dict):
        return None
    try:
        target = int(goal.get("target") or 0)
    except (TypeError, ValueError):
        return None
    by, since = _day(goal.get("by")), _day(goal.get("since"))
    if target <= 0 or by is None:
        return None
    try:
        per_week = int(goal.get("uploads_per_week") or 0)
    except (TypeError, ValueError):
        per_week = 0
    return {
        "metric": str(goal.get("metric") or "views"),
        "target": target,
        "since": since,
        "by": by,
        "uploads_per_week": per_week,
    }


# ---- views by day ----------------------------------------------------------------------


def _views_path(channel_id: str) -> str:
    return CHANNEL_VIEWS_TEMPLATE.format(channel=channel_id)


def save_channel_views(channel_id: str, daily: list[list[Any]]) -> int:
    """Merge a channel views-by-day series into the store; returns the days kept."""
    from analytics.view_curve import merge_daily

    stored = _read_json(_views_path(channel_id))
    stored = stored if isinstance(stored, dict) else {}
    merged = merge_daily(stored.get("daily"), daily)
    stored.update({"channel_id": channel_id, "daily": merged})
    _write_json(_views_path(channel_id), stored)
    return len(merged)


def save_channel_uploads(channel_id: str, uploads: list[dict[str, str]]) -> None:
    """Keep the channel's own uploads list beside its views (#941)."""
    stored = _read_json(_views_path(channel_id))
    stored = stored if isinstance(stored, dict) else {}
    stored.update({"channel_id": channel_id, "uploads": list(uploads)})
    _write_json(_views_path(channel_id), stored)


def channel_uploads(channel_id: str) -> list[dict[str, str]]:
    stored = _read_json(_views_path(channel_id))
    uploads = stored.get("uploads") if isinstance(stored, dict) else None
    return list(uploads) if isinstance(uploads, list) else []


def sync_channel_views(channel_id: str, *, today: date | None = None) -> int:
    """Ask YouTube Analytics for the channel's last `SYNC_DAYS` days; the days kept, or 0."""
    from analytics.youtube_metrics import fetch_channel_daily_views

    end = today or _today()
    start = end - timedelta(days=SYNC_DAYS)
    try:
        daily = fetch_channel_daily_views(
            channel_id=channel_id, start=start.isoformat(), end=end.isoformat()
        )
    except Exception as exc:
        logger.debug("channel views by day skipped for %s: %s", channel_id, exc)
        return 0
    # #941: the channel's own uploads, so "uploads this week" counts the ones made elsewhere.
    from analytics.youtube_metrics import fetch_channel_uploads

    try:
        uploads = fetch_channel_uploads(channel_id=channel_id)
    except Exception as exc:
        logger.debug("channel uploads skipped for %s: %s", channel_id, exc)
        uploads = None
    if uploads is not None:
        save_channel_uploads(channel_id, uploads)
    if not daily:
        return 0
    return save_channel_views(channel_id, daily)


def channel_daily_views(channel_id: str) -> tuple[dict[date, int], str]:
    """({day: views}, source) - "channel" (the synced series), "videos" (summed), or ""."""
    stored = _read_json(_views_path(channel_id))
    series = stored.get("daily") if isinstance(stored, dict) else None
    out: dict[date, int] = {}
    for item in series or []:
        try:
            day, views = _day(item[0]), int(float(item[1]))
        except (TypeError, ValueError, IndexError):
            continue
        if day is not None:
            out[day] = views
    if out:
        return out, "channel"
    from core.success.videos import channel_videos

    for video in channel_videos(channel_id, include_seeded=False):
        for item in video.daily_views:
            try:
                day, views = _day(item[0]), int(float(item[1]))
            except (TypeError, ValueError, IndexError):
                continue
            if day is not None:
                out[day] = out.get(day, 0) + views
    return out, ("videos" if out else "")


# ---- this week's focus (#936 sets it) -------------------------------------------------


def focus(channel_id: str) -> str:
    data = _read_json(FOCUS_FILE)
    entry = data.get(channel_id) if isinstance(data, dict) else None
    return str(entry.get("text") or "") if isinstance(entry, dict) else ""


def set_focus(channel_id: str, text: str) -> None:
    data = _read_json(FOCUS_FILE)
    data = data if isinstance(data, dict) else {}
    data[channel_id] = {"text": text.strip(), "set": _today().isoformat()}
    _write_json(FOCUS_FILE, data)


# ---- the scoreboard ---------------------------------------------------------------------


def _series(daily: Any) -> dict[date, int]:
    """{day: views} from a {date: views} dict or [[YYYY-MM-DD, views], ...]."""
    series: dict[date, int] = {}
    items = daily.items() if isinstance(daily, dict) else (tuple(i[:2]) for i in daily or [])
    for day, views in items:
        parsed = day if isinstance(day, date) else _day(day)
        if parsed is not None:
            series[parsed] = int(views)
    return series


def weekly_totals(daily: Any, today: date | str, weeks: int = 8) -> list[list[Any]]:
    """[[YYYY-Www, views], ...] for the last `weeks` ISO weeks that ended before this one
    and that the series covers from their Monday (#943). The current week is left out (it
    is not over), and so is a week the series starts part-way through."""
    end = _day(today) or _today()
    this_monday = end - timedelta(days=end.weekday())
    series = _series(daily)
    if not series:
        return []
    # A week the series starts part-way through would read as a drop (wave 55 live check).
    first = min(series)
    first_monday = first if first.weekday() == 0 else first + timedelta(days=7 - first.weekday())
    totals: dict[tuple[int, int], int] = {}
    for day, views in series.items():
        if first_monday <= day < this_monday:
            year, week, _ = day.isocalendar()
            totals[(year, week)] = totals.get((year, week), 0) + views
    keys = sorted(totals)[-weeks:]
    return [[f"{y}-W{w:02d}", totals[(y, w)]] for y, w in keys]


# ---- the review history (#943; `ops review-week` writes one row per ISO week) -----------


def _history_path(channel_id: str) -> str:
    return HISTORY_TEMPLATE.format(channel=channel_id)


def review_history(channel_id: str) -> list[dict[str, Any]]:
    rows = _read_json(_history_path(channel_id))
    rows = (
        [r for r in rows if isinstance(r, dict) and r.get("week")] if isinstance(rows, list) else []
    )
    return sorted(rows, key=lambda r: str(r["week"]))


def record_week(channel_id: str, row: dict[str, Any]) -> None:
    """Add this week's row; a second review in the same week replaces it."""
    rows = [r for r in review_history(channel_id) if r.get("week") != row.get("week")]
    rows.append(dict(row))
    _write_json(_history_path(channel_id), sorted(rows, key=lambda r: str(r["week"])))


def on_pace_streak(rows: list[dict[str, Any]]) -> int:
    """Consecutive most recent reviews that were on track."""
    streak = 0
    for row in reversed(rows):
        if not row.get("on_track"):
            break
        streak += 1
    return streak


def pace_per_week(daily: Any, today: date | str) -> dict[str, Any]:
    """{"per_week", "days"}: views a week over the last `PACE_DAYS` the series covers.

    The channel's rate now, whatever the goal's start - a goal set this week has two days
    of its own to read - and over the days the series actually covers, so a week-old
    series is not divided by four weeks (both found in wave 54's live check).
    """
    end = _day(today) or _today()
    series = _series(daily)
    covered = [d for d in series if d < end]
    start = max(end - timedelta(days=PACE_DAYS), min(covered, default=end))
    days = (end - start).days
    views = sum(v for d, v in series.items() if start <= d < end)
    return {"per_week": views * 7 / days if days > 0 else None, "days": days}


def scoreboard(channel_id: str, *, today: date | None = None) -> dict[str, Any] | None:
    """Every number the scoreboard prints, or None when no goal is set."""
    goal = load_goal(channel_id)
    if goal is None:
        return None
    today = today or _today()
    since: date = goal["since"] or date.min
    daily, source = channel_daily_views(channel_id)
    so_far = sum(v for d, v in daily.items() if since <= d <= today)
    days_left = (goal["by"] - today).days
    remaining = max(0, goal["target"] - so_far)
    need = remaining * 7 / days_left if days_left > 0 else None
    measured = pace_per_week(daily, today)
    pace, window_days = measured["per_week"], measured["days"]
    projected = so_far + round(pace * days_left / 7) if pace is not None and days_left > 0 else None

    from core.success.videos import channel_videos

    week_start = today - timedelta(days=7)
    week = [
        v
        for v in channel_videos(channel_id, include_seeded=False)
        if v.published_at is not None and week_start < v.published_at.date() <= today
    ]
    ranked = sorted(week, key=lambda v: v.views, reverse=True)
    uploads_week, outside = len(week), 0
    listed = channel_uploads(channel_id)
    if listed:
        known = {v.video_id for v in channel_videos(channel_id, include_seeded=False)}
        in_week = [
            u
            for u in listed
            if (d := _day(u.get("published_at"))) is not None and week_start < d <= today
        ]
        uploads_week = len(in_week)
        outside = sum(1 for u in in_week if u.get("video_id") not in known)
    return {
        "channel_id": channel_id,
        "goal": goal,
        "so_far": so_far,
        "source": source,
        "days_left": days_left,
        "need_per_week": need,
        "pace_per_week": pace,
        "pace_days": window_days,
        "on_track": pace is not None and need is not None and pace >= need,
        "projected": projected,
        "uploads_week": uploads_week,
        "uploads_outside": outside,
        "weeks": weekly_totals(daily, today),
        "streak": on_pace_streak(review_history(channel_id)),
        "best": ranked[0] if ranked else None,
        "weakest": ranked[-1] if len(ranked) > 1 else None,
        "focus": focus(channel_id),
    }


_SOURCES = {
    "channel": "channel views by day",
    "videos": "your videos' views by day (the channel series syncs with ops sync-metrics)",
}


def _window(days: int) -> str:
    return f"last {days // 7} weeks" if days >= PACE_DAYS else f"last {days} days"


def scoreboard_lines(channel_id: str, *, today: date | None = None) -> list[str]:
    board = scoreboard(channel_id, today=today)
    if board is None:
        return [
            f"Scoreboard - {channel_id}: no goal set. Add one to config/goals.json, e.g. "
            '{"' + channel_id + '": {"metric": "views", "target": 100000, '
            '"since": "2026-10-01", "by": "2026-12-31", "uploads_per_week": 5}}'
        ]
    goal = board["goal"]
    since = f" (counting from {goal['since'].isoformat()})" if goal["since"] else ""
    lines = [
        f"Scoreboard - {channel_id}: {goal['target']:,} {goal['metric']} by "
        f"{goal['by'].isoformat()}{since}"
    ]
    if not board["source"]:
        lines.append(
            "  so far: no views by day yet - set YOUTUBE_ANALYTICS_SYNC=true and run "
            "py -m scripts.ops sync-metrics"
        )
    else:
        share = board["so_far"] / goal["target"]
        left = (
            f"{board['days_left']} days left" if board["days_left"] > 0 else "the deadline passed"
        )
        lines.append(
            f"  so far: {board['so_far']:,} views ({share:.0%}) · {left} · "
            f"source: {_SOURCES[board['source']]}"
        )
        need, pace = board["need_per_week"], board["pace_per_week"]
        if need is not None and pace is not None:
            verdict = "on track" if board["on_track"] else "behind"
            lines.append(
                f"  pace: need {round(need):,}/week, getting {round(pace):,}/week "
                f"({_window(board['pace_days'])}) -> {verdict}"
            )
        if board["projected"] is not None:
            lines.append(
                f"  at this pace: ~{board['projected']:,} by {goal['by'].isoformat()} "
                f"({board['projected'] / goal['target']:.0%} of the goal)"
            )
    weeks = board["weeks"]
    if weeks:
        line = "  weeks: " + " · ".join(f"{w.split('-')[1]} {v:,}" for w, v in weeks)
        if len(weeks) >= 2 and weeks[-2][1]:
            change = weeks[-1][1] / weeks[-2][1] - 1
            line += (
                f" ({weeks[-1][0].split('-')[1]} vs {weeks[-2][0].split('-')[1]}: {change:+.0%})"
            )
        lines.append(line)
    if board["streak"]:
        plural = "s" if board["streak"] != 1 else ""
        lines.append(f"  on pace {board['streak']} review{plural} running")
    plan = f" of {goal['uploads_per_week']}" if goal["uploads_per_week"] else ""
    elsewhere = (
        f" ({board['uploads_outside']} made outside Content OS)" if board["uploads_outside"] else ""
    )
    lines.append(f"  uploads, last 7 days: {board['uploads_week']}{plan}{elsewhere}")
    best, weakest = board["best"], board["weakest"]
    if best is not None:
        line = f'  best: "{best.title}" {best.views:,} views'
        if weakest is not None:
            line += f' · weakest: "{weakest.title}" {weakest.views:,} views'
        lines.append(line)
    if board["focus"]:
        lines.append(f"  focus this week: {board['focus']}")
    return lines


def banner_line(channel_id: str, *, today: date | None = None) -> str:
    """One line for the startup banner, or "" when no goal is set."""
    try:
        board = scoreboard(channel_id, today=today)
    except Exception as exc:
        logger.debug("scoreboard banner skipped: %s", exc)
        return ""
    if board is None:
        return ""
    goal = board["goal"]
    parts = [f"Goal: {board['so_far']:,} / {goal['target']:,} {goal['metric']}"]
    need, pace = board["need_per_week"], board["pace_per_week"]
    if need is not None and pace is not None:
        verdict = "on track" if board["on_track"] else "behind"
        parts.append(f"{verdict}: need {round(need):,}/wk, getting {round(pace):,}/wk")
    if board["focus"]:
        parts.append(f"focus: {board['focus']}")
    return " · ".join(parts)
