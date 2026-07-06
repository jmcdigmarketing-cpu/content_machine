"""Predicted engaged-rate from pre-publish quality scores (Pillar 2, data-gated).

A deliberately explainable model — channel baseline plus least-squares
adjustments for the hook and authenticity deltas — over runs that have BOTH a
persisted quality dict (Pillar 1) and a realized engaged-rate. No sklearn, no
opaque weights: the note says exactly what moved the prediction.

Data-gated per the roadmap: below ``PREDICTOR_MIN_SAMPLES`` (default 15)
measured runs it returns None — a prediction from single-digit history would
be noise wearing a number. Follows the `core/recommender_confidence.py`
philosophy: thin bases must say so.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger("core.engagement_predictor")


def _min_samples() -> int:
    try:
        return int(os.getenv("PREDICTOR_MIN_SAMPLES", "15"))
    except ValueError:
        return 15


@dataclass
class Prediction:
    rate: float  # predicted engaged-rate, 0..1
    band: float  # +/- residual std
    n: int  # measured runs behind it
    note: str


def run_engagement_map(channel_id: str) -> dict[int, float]:
    """run_id -> realized engaged_rate (same join the experiment harness uses)."""
    try:
        from core.engagement import engaged_rate
        from storage.repositories.publish_log import get_publish_log_repository

        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("engagement map load failed: %s", exc)
        return {}
    out: dict[int, float] = {}
    for log in logs:
        rate = engaged_rate(log.metrics_json)
        if rate is not None and log.content_run_id:
            out[int(log.content_run_id)] = float(rate)
    return out


def _training_rows(channel_id: str) -> list[tuple[float, float, float]]:
    """(hook, authenticity, engaged_rate) for measured runs with quality."""
    engagement = run_engagement_map(channel_id)
    if not engagement:
        return []
    rows: list[tuple[float, float, float]] = []
    try:
        from storage.repositories.content_runs import get_content_run_repository

        for run in get_content_run_repository().list_for_channel(channel_id):
            rate = engagement.get(run.id)
            if rate is None:
                continue
            try:
                quality = json.loads(run.quality_json or "{}")
            except Exception:
                continue
            hook = quality.get("hook_score")
            auth = quality.get("authenticity_score")
            if hook is None or auth is None:
                continue
            rows.append((float(hook), float(auth), rate))
    except Exception as exc:
        logger.debug("training rows load failed: %s", exc)
    return rows


def _slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of y on x (0 when x has no variance)."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var <= 1e-9:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    return cov / var


def predict_engaged_rate(channel_id: str, *, quality: dict) -> Prediction | None:
    """Expected engaged-rate for a draft's quality dict, or None below the gate."""
    hook = quality.get("hook_score")
    auth = quality.get("authenticity_score")
    if hook is None and auth is None:
        return None
    rows = _training_rows(channel_id)
    if len(rows) < _min_samples():
        return None

    hooks = [r[0] for r in rows]
    auths = [r[1] for r in rows]
    rates = [r[2] for r in rows]
    n = len(rows)
    baseline = sum(rates) / n
    slope_h = _slope(hooks, rates)
    slope_a = _slope(auths, rates)

    predicted = baseline
    parts = [f"baseline {baseline * 100:.1f}%"]
    if hook is not None:
        delta = (float(hook) - sum(hooks) / n) * slope_h
        predicted += delta
        if abs(delta) >= 0.0005:
            parts.append(f"hook {delta * 100:+.1f}pp")
    if auth is not None:
        delta = (float(auth) - sum(auths) / n) * slope_a
        predicted += delta
        if abs(delta) >= 0.0005:
            parts.append(f"authenticity {delta * 100:+.1f}pp")

    predicted = max(0.0, min(0.95, predicted))
    residuals = [
        rate
        - min(
            0.95,
            max(
                0.0,
                baseline + (h - sum(hooks) / n) * slope_h + (a - sum(auths) / n) * slope_a,
            ),
        )
        for h, a, rate in rows
    ]
    band = (sum(r * r for r in residuals) / n) ** 0.5
    return Prediction(
        rate=round(predicted, 4),
        band=round(band, 4),
        n=n,
        note=f"{', '.join(parts)}; n={n}, ±{band * 100:.1f}pp",
    )
