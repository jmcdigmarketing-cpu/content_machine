"""
Temporal intelligence — topic demand trajectory from stored snapshots.

Records composite/demand on each intelligence run; surfaces rising / peaking /
decaying so the analyst answers "still worth jumping on?" not just "hot now".
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any

from config.paths import ensure_data_dir

_lock = threading.Lock()
_MAX_SNAPSHOTS = 40
_TRAJECTORY_FILE = os.path.join("data", "topic_trajectory.json")

PHASE_RISING = "rising"
PHASE_PEAKING = "peaking"
PHASE_DECAYING = "decaying"
PHASE_EMERGING = "emerging"
PHASE_STABLE = "stable"
PHASE_UNKNOWN = "insufficient_data"


def _trajectory_path() -> str:
    ensure_data_dir()
    return _TRAJECTORY_FILE


def _topic_key(channel_id: str, topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", " ", topic.lower()).strip()
    return f"{channel_id}::{slug}"


def _load_store() -> dict[str, list[dict]]:
    path = _trajectory_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_store(store: dict[str, list[dict]]) -> None:
    path = _trajectory_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def record_topic_snapshot(
    channel_id: str,
    topic: str,
    *,
    composite_score: float,
    demand_index: float | None = None,
) -> None:
    """Append a snapshot (deduped if same score within 30 minutes)."""
    key = _topic_key(channel_id, topic)
    now = time.time()
    entry = {
        "ts": now,
        "composite_score": round(float(composite_score), 2),
        "demand_index": round(float(demand_index or composite_score), 2),
    }

    with _lock:
        store = _load_store()
        rows = list(store.get(key) or [])
        if rows:
            last = rows[-1]
            if (
                abs(last.get("composite_score", 0) - entry["composite_score"]) < 0.5
                and now - float(last.get("ts", 0)) < 1800
            ):
                return
        rows.append(entry)
        store[key] = rows[-_MAX_SNAPSHOTS:]
        _save_store(store)


def _linear_slope(points: list[tuple[float, float]]) -> float:
    """Slope of y over x (x = hours since first point)."""
    if len(points) < 2:
        return 0.0
    x0 = points[0][0]
    xs = [p[0] - x0 for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den


def compute_trajectory(
    channel_id: str,
    topic: str,
    *,
    current_score: float | None = None,
) -> dict[str, Any]:
    """
    Analyze stored snapshots for phase, velocity (pts/hour), acceleration.
    """
    key = _topic_key(channel_id, topic)
    with _lock:
        rows = list(_load_store().get(key) or [])

    if current_score is not None and rows:
        rows = [
            *rows,
            {"ts": time.time(), "composite_score": current_score, "demand_index": current_score},
        ]

    if len(rows) < 2:
        return {
            "phase": PHASE_UNKNOWN,
            "snapshot_count": len(rows),
            "velocity_per_hour": 0.0,
            "acceleration": 0.0,
            "summary": "Not enough history yet — run again over hours/days for trajectory.",
        }

    t0 = float(rows[0]["ts"])
    points = [((float(r["ts"]) - t0) / 3600.0, float(r.get("composite_score", 0))) for r in rows]
    recent = points[-min(8, len(points)) :]
    slope = _linear_slope(recent)

    older = points[: max(2, len(points) - len(recent))]
    slope_older = _linear_slope(older) if len(older) >= 2 else slope
    acceleration = slope - slope_older

    latest = float(rows[-1].get("composite_score", 0))
    phase = _classify_phase(latest, slope, acceleration)

    return {
        "phase": phase,
        "snapshot_count": len(rows),
        "velocity_per_hour": round(slope, 3),
        "acceleration": round(acceleration, 3),
        "latest_score": round(latest, 2),
        "summary": _phase_summary(phase, slope, latest),
    }


def _classify_phase(score: float, slope: float, acceleration: float) -> str:
    if score >= 55 and abs(slope) < 1.5 and acceleration <= 0:
        return PHASE_PEAKING
    if slope >= 2.0:
        return PHASE_RISING if score >= 40 else PHASE_EMERGING
    if slope <= -2.0:
        return PHASE_DECAYING
    if score < 45 and slope > 0.8:
        return PHASE_EMERGING
    return PHASE_STABLE


def _phase_summary(phase: str, slope: float, score: float) -> str:
    messages = {
        PHASE_RISING: f"Demand is accelerating (+{slope:.1f} pts/hr) — window likely still opening.",
        PHASE_PEAKING: f"High level ({score:.0f}) with flattening velocity — act before saturation.",
        PHASE_DECAYING: f"Interest fading ({slope:.1f} pts/hr) — late to lead; pivot angle or skip.",
        PHASE_EMERGING: "Early lift on a lower base — higher risk/reward if corroboration holds.",
        PHASE_STABLE: "Flat trajectory — opportunity depends on competitor gap, not momentum.",
        PHASE_UNKNOWN: "Insufficient snapshots for trajectory.",
    }
    return messages.get(phase, "")
