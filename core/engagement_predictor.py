"""Predicted engaged-rate from pre-publish quality scores (Pillar 2, data-gated).

A deliberately explainable model — channel baseline plus least-squares
adjustments for the hook and authenticity deltas — over runs that have BOTH a
persisted quality dict (Pillar 1) and a realized engaged-rate. No sklearn, no
opaque weights: the note says exactly what moved the prediction.

Data-gated per the roadmap: below ``PREDICTOR_MIN_SAMPLES`` (default 15)
measured runs it returns None — a prediction from single-digit history would
be noise wearing a number. Follows the `core/recommender_confidence.py`
philosophy: thin bases must say so.

#945: `predict_views_7d` fits the same two inputs to log 7-day organic views (the
recommenders' target since #938), so the ledger can say whether quality predicts views.
"""

from __future__ import annotations

import json
import math
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


def run_views_map(channel_id: str) -> dict[int, float]:
    """run_id -> log1p of 7-day organic views (#945), the scale the views target ranks on."""
    try:
        from core.success.target import TARGET_VIEWS, outcome
        from storage.repositories.publish_log import get_publish_log_repository

        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("views map load failed: %s", exc)
        return {}
    out: dict[int, float] = {}
    for log in logs:
        value = outcome(log.metrics_json, log.published_at, target_name=TARGET_VIEWS)
        if value is not None and log.content_run_id:
            out[int(log.content_run_id)] = float(value)
    return out


def _training_rows(
    channel_id: str,
    *,
    exclude_run_id: int | None = None,
    outcomes: dict[int, float] | None = None,
) -> list[tuple[float, float, float]]:
    """(hook, authenticity, engaged_rate) for measured runs with quality.

    #559: `exclude_run_id` leaves one run out, so a video's prediction is never fitted
    on its own outcome.

    #815: the authenticity column is the binary gate sum on both sides of the
    v3/v4 boundary. #804 made ``authenticity_score`` continuous, and fitting a
    slope across two different rubrics measures the rubric change, not the work.
    """
    from core.run_quality import authenticity_gate_value

    engagement = run_engagement_map(channel_id) if outcomes is None else outcomes
    if not engagement:
        return []
    rows: list[tuple[float, float, float]] = []
    try:
        from storage.repositories.content_runs import get_content_run_repository

        for run in get_content_run_repository().list_for_channel(channel_id):
            if exclude_run_id is not None and int(run.id) == int(exclude_run_id):
                continue
            rate = engagement.get(run.id)
            if rate is None:
                continue
            try:
                quality = json.loads(run.quality_json or "{}")
            except Exception as exc:
                logger.debug(
                    "Unreadable quality_json on run %s — excluded from the fit: %s", run.id, exc
                )
                continue
            hook = quality.get("hook_score")
            auth = authenticity_gate_value(quality)
            if hook is None or auth is None:
                continue
            rows.append((float(hook), auth, rate))
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


def predict_engaged_rate(
    channel_id: str, *, quality: dict, exclude_run_id: int | None = None
) -> Prediction | None:
    """Expected engaged-rate for a draft's quality dict, or None below the gate.

    `exclude_run_id` fits without that run (#559) - the publish-time freeze passes the
    video's own run, so its outcome is never part of its prediction.
    """
    from core.run_quality import authenticity_gate_value

    hook = quality.get("hook_score")
    # #815: same series as `_training_rows` — the draft must be measured on the
    # scale the slope was fitted on.
    auth = authenticity_gate_value(quality)
    if hook is None and auth is None:
        return None
    rows = _training_rows(channel_id, exclude_run_id=exclude_run_id)
    if len(rows) < _min_samples():
        return None
    predicted, band, baseline, deltas = _fit(rows, hook, auth, high=0.95)
    n = len(rows)
    parts = [f"baseline {baseline * 100:.1f}%"]
    parts += [f"{name} {delta * 100:+.1f}pp" for name, delta in deltas if abs(delta) >= 0.0005]
    return Prediction(
        rate=round(predicted, 4),
        band=round(band, 4),
        n=n,
        note=f"{', '.join(parts)}; n={n}, ±{band * 100:.1f}pp",
    )


def _fit(
    rows: list[tuple[float, float, float]],
    hook: float | None,
    auth: float | None,
    *,
    high: float,
) -> tuple[float, float, float, list[tuple[str, float]]]:
    """(prediction, residual band, baseline, [(input, delta)]): the channel mean plus a
    least-squares slope per input, clamped to 0..`high`."""
    hooks = [r[0] for r in rows]
    auths = [r[1] for r in rows]
    values = [r[2] for r in rows]
    n = len(rows)
    baseline = sum(values) / n
    slope_h = _slope(hooks, values)
    slope_a = _slope(auths, values)
    mean_h, mean_a = sum(hooks) / n, sum(auths) / n

    predicted = baseline
    deltas: list[tuple[str, float]] = []
    if hook is not None:
        delta = (float(hook) - mean_h) * slope_h
        predicted += delta
        deltas.append(("hook", delta))
    if auth is not None:
        delta = (float(auth) - mean_a) * slope_a
        predicted += delta
        deltas.append(("authenticity", delta))
    predicted = max(0.0, min(high, predicted))
    residuals = [
        value - min(high, max(0.0, baseline + (h - mean_h) * slope_h + (a - mean_a) * slope_a))
        for h, a, value in rows
    ]
    band = (sum(r * r for r in residuals) / n) ** 0.5
    return predicted, band, baseline, deltas


@dataclass
class ViewsPrediction:
    log_views: float  # predicted log1p(7-day organic views)
    views: int  # the same, in views
    band: float  # +/- residual std on the log scale
    n: int
    note: str


def predict_views_7d(
    channel_id: str, *, quality: dict, exclude_run_id: int | None = None
) -> ViewsPrediction | None:
    """#945: expected 7-day organic views for a draft's quality, or None below the gate."""
    from core.run_quality import authenticity_gate_value

    hook = quality.get("hook_score")
    auth = authenticity_gate_value(quality)
    if hook is None and auth is None:
        return None
    rows = _training_rows(
        channel_id, exclude_run_id=exclude_run_id, outcomes=run_views_map(channel_id)
    )
    if len(rows) < _min_samples():
        return None
    predicted, band, baseline, deltas = _fit(rows, hook, auth, high=math.log1p(1e9))
    n = len(rows)
    parts = [f"baseline {math.expm1(baseline):,.0f} views"]
    parts += [f"{name} x{math.exp(delta):.2f}" for name, delta in deltas if abs(delta) >= 0.005]
    log_views = round(predicted, 4)
    return ViewsPrediction(
        log_views=log_views,
        views=round(math.expm1(log_views)),
        band=round(band, 4),
        n=n,
        note=f"{', '.join(parts)}; n={n}, x{math.exp(band):.2f} either way",
    )


def surprise_residual(actual: float | None, predicted: float | None) -> float | None:
    """actual − predicted engaged-rate. None when either side is missing."""
    if actual is None or predicted is None:
        return None
    try:
        return round(float(actual) - float(predicted), 4)
    except (TypeError, ValueError):
        return None
