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
    pct = int(round(pos * 100))
    floor = int(round(_retained_floor() * 100))
    return (
        f"RETENTION DATA: on this channel the average viewer has dropped below "
        f"{floor}% retention by roughly {pct}% of the way in. Front-load the payoff "
        f"and land your strongest hook/pivot BEFORE the {pct}% mark — do not save the "
        "best beat for the end."
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
        bar = "█" * int(round(r * 20))
        print_fn(f"    {int(p * 100):3d}%  {bar:<20} {r:.0%}")
    if pos is not None:
        print_fn(
            f"\n    ↳ Drop-off below {int(_retained_floor() * 100)}% by ~{int(pos * 100)}% "
            "in — front-load the payoff."
        )
