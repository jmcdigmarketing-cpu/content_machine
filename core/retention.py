"""Retention-curve modelling — where viewers drop off, and what to do about it.

`analytics/youtube_metrics` now stores a per-video audience-retention curve
(`retention_curve`: [[elapsed_ratio, watch_ratio], …]) alongside the headline
metrics. This aggregates those curves across the channel into an average curve and
a **drop-off point** — the position where most of the audience is gone — which
feeds the script prompt's pacing pivot (front-load the payoff before the cliff).

Strictly confidence-gated: a model from 2 videos is noise, so everything returns
"nothing yet" until at least `RETENTION_MIN_VIDEOS` curves exist. Read-only and
best-effort — any storage/parse error yields an empty model, never an exception.
"""

from __future__ import annotations

import json
import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.retention")

# Position bins (0%, 5%, … 100%) the per-video curves are resampled onto.
_BINS = [round(i / 20, 2) for i in range(21)]


def _min_videos() -> int:
    try:
        return max(3, int(os.getenv("RETENTION_MIN_VIDEOS", "3")))
    except ValueError:
        return 3


def _retained_floor() -> float:
    try:
        return float(os.getenv("RETENTION_DROPOFF_FLOOR", "0.5"))
    except ValueError:
        return 0.5


def _curves(channel_id: str) -> list[list[tuple[float, float]]]:
    """Parsed, sorted per-video retention curves from publish_log metrics."""
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("retention curve load failed: %s", exc)
        return []
    curves: list[list[tuple[float, float]]] = []
    for log in logs:
        try:
            raw = (json.loads(log.metrics_json or "{}") or {}).get("retention_curve")
        except (ValueError, TypeError):
            continue
        if not isinstance(raw, list) or len(raw) < 3:
            continue
        pts: list[tuple[float, float]] = []
        for item in raw:
            try:
                pts.append((float(item[0]), float(item[1])))
            except (ValueError, IndexError, TypeError):
                continue
        if len(pts) >= 3:
            curves.append(sorted(pts))
    return curves


def _resample(curve: list[tuple[float, float]]) -> list[float]:
    """Watch-ratio sampled at each position bin (nearest-point, simple + robust)."""
    out: list[float] = []
    for b in _BINS:
        nearest = min(curve, key=lambda p: abs(p[0] - b))
        out.append(nearest[1])
    return out


def average_curve(
    channel_id: str, *, min_videos: int | None = None
) -> list[tuple[float, float]] | None:
    """Channel-average retention curve [(position, watch_ratio), …], or None."""
    min_n = min_videos if min_videos is not None else _min_videos()
    curves = _curves(channel_id)
    if len(curves) < min_n:
        return None
    sampled = [_resample(c) for c in curves]
    avg = [sum(col) / len(col) for col in zip(*sampled, strict=False)]
    return list(zip(_BINS, avg, strict=False))


def drop_off_ratio(channel_id: str, *, min_videos: int | None = None) -> float | None:
    """First position (0–1) where average retention falls below the floor, or None."""
    avg = average_curve(channel_id, min_videos=min_videos)
    if not avg:
        return None
    floor = _retained_floor()
    for pos, ratio in avg:
        if pos > 0 and ratio < floor:
            return pos
    return None


def pacing_hint(channel_id: str | None) -> str:
    """Data-driven pacing instruction for the script prompt, or '' when no data."""
    if not channel_id:
        return ""
    try:
        pos = drop_off_ratio(channel_id)
    except Exception:
        return ""
    if pos is None:
        return ""
    pct = round(pos * 100)
    floor = round(_retained_floor() * 100)
    return (
        f"RETENTION DATA: on this channel the average viewer has dropped below "
        f"{floor}% retention by roughly {pct}% of the way in. Front-load the payoff "
        f"and land your strongest hook/pivot BEFORE the {pct}% mark — do not save the "
        "best beat for the end."
    )


def cliff_line(channel_id: str | None) -> str:
    """Wave 112: where the channel loses half its viewers, for growth - or ""."""
    if not channel_id:
        return ""
    try:
        pos = drop_off_ratio(channel_id)
    except Exception:
        return ""
    if pos is None:
        return ""
    return (
        f"Retention: half the viewers are gone by {round(pos * 100)}% of a video - the first "
        "sentence after the intro carries the stake and the call."
    )


def display_retention(channel_id: str, *, print_fn=print) -> None:
    avg = average_curve(channel_id)
    if not avg:
        print_fn(
            f"\n  Retention: (need ≥{_min_videos()} videos with retention curves — "
            "syncs as analytics accrue)"
        )
        return
    pos = drop_off_ratio(channel_id)
    print_fn("\n  📉 Audience retention (channel average):")
    for p, r in avg[::4]:  # every 20%
        bar = "█" * round(r * 20)
        print_fn(f"    {int(p * 100):3d}%  {bar:<20} {r:.0%}")
    if pos is not None:
        print_fn(
            f"\n    ↳ Drop-off below {int(_retained_floor() * 100)}% by ~{int(pos * 100)}% "
            "in — front-load the payoff."
        )
    try:  # #1426 (wave 120): the first seconds, video by video
        firsts = first_seconds_lines(channel_id)
    except Exception as exc:
        logger.debug("first-seconds lines skipped: %s", exc)
        firsts = []
    if firsts:
        print_fn("\n  The first 3 seconds (newest first):")
        for line in firsts:
            print_fn(f"    {line}")


# --- #565: diff two videos' curves ----------------------------------------------------
_DIFF_POINTS = [round(i / 10, 1) for i in range(11)]


def _parse_curve(raw) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            pts.append((float(item[0]), float(item[1])))
        except (ValueError, IndexError, TypeError):
            continue
    return sorted(pts) if len(pts) >= 3 else []


def _curved_runs(channel_id: str) -> dict[int, tuple[list[tuple[float, float]], float | None]]:
    """run_id -> (curve, engaged rate) for measured videos that kept a curve."""
    from core.engagement import engaged_rate
    from storage.repositories.publish_log import get_publish_log_repository

    out: dict[int, tuple[list[tuple[float, float]], float | None]] = {}
    for log in get_publish_log_repository().list_timed_outcomes(channel_id) or []:
        if not log.content_run_id:
            continue
        try:
            raw = (json.loads(log.metrics_json or "{}") or {}).get("retention_curve")
        except (ValueError, TypeError):
            continue
        curve = _parse_curve(raw)
        if curve:
            out[int(log.content_run_id)] = (curve, engaged_rate(log.metrics_json))
    return out


def _at(curve: list[tuple[float, float]], point: float) -> float:
    return min(curve, key=lambda p: abs(p[0] - point))[1]


def _describe(run_id: int) -> tuple[str, str]:
    """(title, franchise) for a run."""
    from core.negative_facts import franchise_for
    from storage.repositories.content_runs import get_content_run_repository

    run = get_content_run_repository().get(int(run_id))
    title = str(getattr(run, "title", "") or getattr(run, "selected_topic", "") or "")
    topic = str(getattr(run, "selected_topic", "") or title)
    return title, franchise_for(topic)


def retention_diff_lines(
    channel_id: str, run_a: int | None = None, run_b: int | None = None
) -> list[str]:
    """Two videos' retention side by side and where the gap opened (#565).

    With no runs named: the franchise with the most measured curves, its best engaged
    video against its worst.
    """
    curves = _curved_runs(channel_id)
    if run_a is None or run_b is None:
        by_franchise: dict[str, list[int]] = {}
        for run_id in curves:
            by_franchise.setdefault(_describe(run_id)[1], []).append(run_id)
        pool = max(by_franchise.values(), key=len, default=[])
        if len(pool) < 2:
            return ["Retention diff: no franchise has two videos with a retention curve yet"]
        ranked = sorted(pool, key=lambda r: curves[r][1] or 0.0, reverse=True)
        run_a, run_b = ranked[0], ranked[-1]
    missing = [r for r in (run_a, run_b) if r not in curves]
    if missing:
        return [f"Retention diff: run {missing[0]} has no retention curve (sync its metrics first)"]
    (curve_a, rate_a), (curve_b, rate_b) = curves[run_a], curves[run_b]
    title_a, franchise_a = _describe(run_a)
    title_b, franchise_b = _describe(run_b)

    def _rate(rate: float | None) -> str:
        return f"{rate:.0%}" if rate is not None else "n/a"

    lines = [
        f"Retention diff (#565) - {franchise_a}"
        + ("" if franchise_a == franchise_b else f" vs {franchise_b} (different franchises)"),
        f"  A: run {run_a} {title_a[:50]} ({_rate(rate_a)} engaged)",
        f"  B: run {run_b} {title_b[:50]} ({_rate(rate_b)} engaged)",
    ]
    gaps = []
    for point in _DIFF_POINTS:
        a, b = _at(curve_a, point), _at(curve_b, point)
        gaps.append(a - b)
        lines.append(f"    {point:4.0%}: {a:.2f} vs {b:.2f}  ({(b - a) * 100:+.0f}pp)")
    steps = [gaps[i + 1] - gaps[i] for i in range(len(gaps) - 1)]
    widest = max(range(len(steps)), key=lambda i: (round(abs(steps[i]), 3), -i))
    if abs(steps[widest]) >= 0.01:
        loser = "B" if steps[widest] > 0 else "A"
        lines.append(
            f"  the gap opens most between {_DIFF_POINTS[widest]:.0%} and "
            f"{_DIFF_POINTS[widest + 1]:.0%}: {loser} loses {abs(steps[widest]) * 100:.0f}pp "
            "more of its audience there - read that stretch of its script"
        )
    else:
        lines.append("  the two curves track each other - no stretch stands out")
    return lines


def drop_off_position(curve: list[tuple[float, float]], floor: float | None = None) -> float | None:
    """#1494 (wave 119): the first position (0-1) where a video's curve falls under the floor
    (half the viewers by default), or None when it never does."""
    limit = _retained_floor() if floor is None else floor
    for position, ratio in sorted(curve):
        if ratio < limit:
            return position
    return None


def drop_off_text(position: float, seconds: float | None) -> str:
    """ "half gone at 0:21 of 0:42", or the share of the video without its length."""
    if not seconds:
        return f"half gone at {round(position * 100)}%"
    at = round(position * seconds)
    total = round(seconds)
    return f"half gone at {at // 60}:{at % 60:02d} of {total // 60}:{total % 60:02d}"


def week_drop_off_lines(channel_id: str, *, days: int = 7, limit: int = 8) -> list[str]:
    """#1494: each of the week's measured videos and where it lost half its viewers - the weekly
    review had the channel's average cliff only. The length is the render's (ffprobe)."""
    from datetime import datetime, timedelta, timezone

    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[str] = []
    for log in get_publish_log_repository().list_timed_outcomes(channel_id) or []:
        when = getattr(log, "published_at", None)
        if not log.content_run_id or not isinstance(when, datetime):
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if when < cutoff:
            continue
        try:
            curve = _parse_curve(
                (json.loads(log.metrics_json or "{}") or {}).get("retention_curve")
            )
        except (ValueError, TypeError):
            continue
        position = drop_off_position(curve) if curve else None
        if position is None:
            continue
        run = get_content_run_repository().get(int(log.content_run_id))
        seconds = _render_seconds(run)
        title = str(getattr(run, "title", "") or "")[:45]
        out.append(f"run {log.content_run_id} {title}: {drop_off_text(position, seconds)}")
    return out[:limit]


def _render_seconds(run) -> float | None:
    """The render's length: ffprobe on its file, else the length technical QC measured."""
    try:
        from core.chapter_shorts import _probe_duration

        path = str(getattr(run, "mp4_path", "") or "")
        if path and os.path.isfile(path):
            return _probe_duration(path)
    except Exception as exc:
        logger.debug("render length unread for run %s: %s", getattr(run, "id", "?"), exc)
    try:
        features = json.loads(getattr(run, "features_json", "") or "{}") or {}
        return float((features.get("technical_qc") or {}).get("video_duration") or 0) or None
    except (TypeError, ValueError, AttributeError):
        return None


def first_seconds_text(
    curve: list[tuple[float, float]],
    seconds: float | None,
    *,
    at: float = 3.0,
    stayed: float | None = None,
) -> str:
    """#1426: the share still watching `at` seconds in - a Short is kept or swiped there.

    #1538: YouTube's ratio counts a replayed opening again, so it reads over 100% on most
    Shorts; `stayed` (engaged views over views, synced as `stayed_share`) is the share who
    did not swipe, and it is shown beside it when the sync stored one.
    """
    if not curve or not seconds or seconds <= at:
        return ""
    share = round(_at(curve, at / seconds) * 100)
    if share > 100:
        text = f"{share}% at {at:g} s (the opening was replayed)"
    else:
        text = f"{share}% still watching at {at:g} s"
    if isinstance(stayed, (int, float)) and 0 <= stayed <= 1:
        text += f"; {round(stayed * 100)}% stayed rather than swiped"
    return text


def first_seconds_lines(channel_id: str, *, limit: int = 8) -> list[str]:
    """#1426: the newest measured videos' retention at 3 seconds, from each one's curve."""
    from datetime import datetime, timezone

    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    dated: list[tuple[datetime, int, Any]] = []
    for log in get_publish_log_repository().list_timed_outcomes(channel_id) or []:
        when = getattr(log, "published_at", None)
        if log.content_run_id and isinstance(when, datetime):
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            dated.append((when, int(log.content_run_id), log))
    out: list[str] = []
    for _when, run_id, log in sorted(dated, key=lambda d: (d[0], d[1]), reverse=True):
        try:
            metrics = json.loads(log.metrics_json or "{}") or {}
            curve = _parse_curve(metrics.get("retention_curve"))
        except (ValueError, TypeError, AttributeError):
            continue
        if not curve:
            continue
        stayed = metrics.get("stayed_share")
        run = get_content_run_repository().get(run_id)
        text = first_seconds_text(
            curve,
            _render_seconds(run),
            stayed=float(stayed) if isinstance(stayed, (int, float)) else None,
        )
        if text:
            title = str(getattr(run, "title", "") or "")[:45]
            out.append(f"run {run_id} {title}: {text}")
        if len(out) >= limit:
            break
    return out
