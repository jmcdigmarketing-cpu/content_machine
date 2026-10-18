"""Paid-signal outcome attribution + catalog recommendation (candidates 57 / 73).

Did ``tiktok_trends`` / ``youtube_competitors`` move composite score or
engaged-rate on measured runs? Pure over traces (no network). Never flips
``enabled: false`` in the Apify catalog — the operator decides. Missing
metrics fail-open to "wait" rather than a disable recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.paid_signal_attribution")

PAID_SIGNALS = ("tiktok_trends", "youtube_competitors")
MIN_SAMPLES = 5
_FAIL = {
    "no_key",
    "quota_exceeded",
    "rate_limited",
    "auth_error",
    "upstream_error",
    "http_error",
    "unavailable",
    "error",
}


@dataclass
class ArmStats:
    n: int = 0
    mean: float = 0.0


@dataclass
class SignalLift:
    name: str
    metric: str
    with_signal: ArmStats = field(default_factory=ArmStats)
    without_signal: ArmStats = field(default_factory=ArmStats)

    @property
    def lift(self) -> float | None:
        if self.with_signal.n < 1 or self.without_signal.n < 1:
            return None
        return self.with_signal.mean - self.without_signal.mean

    @property
    def enough(self) -> bool:
        return self.with_signal.n >= MIN_SAMPLES and self.without_signal.n >= MIN_SAMPLES


def _active(sig: Any) -> bool:
    if not isinstance(sig, dict):
        return False
    status = str(sig.get("status") or "")
    if status in _FAIL:
        return False
    return bool(sig.get("active"))


def _mean(values: list[float]) -> ArmStats:
    if not values:
        return ArmStats()
    return ArmStats(n=len(values), mean=sum(values) / len(values))


def _outcome(
    trace: dict[str, Any], *, prefer: str, outcomes: dict[str, dict[int, float]] | None = None
) -> float | None:
    if outcomes is not None:
        # Wave 112: the measured outcome, joined by run id - traces carry no engaged rate, so
        # every run fell back to the composite score these signals themselves feed.
        table = outcomes.get(prefer) or {}
        try:
            value = table.get(int(trace.get("run_id")))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            value = None
        return float(value) if value is not None else None
    if prefer == "engaged_rate":
        raw = trace.get("engaged_rate")
        if raw is None:
            metrics = trace.get("metrics") or {}
            raw = metrics.get("engaged_rate") if isinstance(metrics, dict) else None
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
    raw = trace.get("composite_score")
    if raw is None:
        quality = trace.get("quality") or {}
        raw = quality.get("hook_score") if isinstance(quality, dict) else None
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def attribute_signal(
    traces: list[dict[str, Any]],
    name: str,
    *,
    metric: str = "engaged_rate",
    outcomes: dict[str, dict[int, float]] | None = None,
) -> SignalLift:
    on: list[float] = []
    off: list[float] = []
    for trace in traces:
        value = _outcome(trace, prefer=metric, outcomes=outcomes)
        if value is None:
            continue
        sig = (trace.get("signals") or {}).get(name)
        (on if _active(sig) else off).append(value)
    return SignalLift(
        name=name,
        metric=metric,
        with_signal=_mean(on),
        without_signal=_mean(off),
    )


def attribute_paid_signals(
    traces: list[dict[str, Any]],
    *,
    names: tuple[str, ...] = PAID_SIGNALS,
    outcomes: dict[str, dict[int, float]] | None = None,
) -> list[SignalLift]:
    """Engaged-rate first. With `outcomes` (wave 112) each run's measured engaged rate and
    7-day views are joined by run id, and there is no fallback to the composite score - a
    signal's lift on the score it feeds says nothing about viewers. Without them, the old
    behaviour: composite when no rates exist."""
    out: list[SignalLift] = []
    for name in names:
        lift = attribute_signal(traces, name, metric="engaged_rate", outcomes=outcomes)
        if outcomes is None and lift.with_signal.n + lift.without_signal.n == 0:
            lift = attribute_signal(traces, name, metric="composite_score")
        out.append(lift)
        if outcomes and outcomes.get("views_7d"):
            out.append(attribute_signal(traces, name, metric="views_7d", outcomes=outcomes))
    return out


def recommend_catalog_action(lift: SignalLift) -> str:
    """keep / disable / wait — never writes the catalog."""
    if not lift.enough:
        return "wait"
    delta = lift.lift
    if delta is None:
        return "wait"
    if delta <= 0:
        return "disable"
    return "keep"


def render_report(lifts: list[SignalLift]) -> str:
    lines = ["Paid-signal attribution", "=" * 40]
    lines.append("Does not change apify_sources.json (operator decides).")
    lines.append("Read on measured outcomes: engaged rate, and 7-day views on a log scale.")
    for lift in lifts:
        action = recommend_catalog_action(lift)
        delta = lift.lift
        delta_s = f"{delta:+.4f}" if delta is not None else "n/a"
        lines.append(
            f"  {lift.name} ({lift.metric}): "
            f"on n={lift.with_signal.n} mean={lift.with_signal.mean:.4f} / "
            f"off n={lift.without_signal.n} mean={lift.without_signal.mean:.4f} "
            f"lift={delta_s} -> {action}"
        )
        if action == "disable":
            lines.append(
                f"    recommend enabled: false for {lift.name} "
                f"(no positive lift at n>={MIN_SAMPLES} per arm)"
            )
        elif action == "wait":
            lines.append(f"    need {MIN_SAMPLES} measured runs per arm before a catalog call")
    return "\n".join(lines)


def report_from_traces(
    traces: list[dict[str, Any]] | None = None,
    *,
    limit: int = 50,
    channel_id: str | None = None,
) -> str:
    if traces is None:
        try:
            from core.run_trace import list_traces

            traces = list_traces(limit=limit, channel_id=channel_id)
        except Exception as exc:
            logger.debug("paid-signal traces skipped: %s", exc)
            traces = []
    outcomes = _channel_outcomes(channel_id) if channel_id else None
    return render_report(attribute_paid_signals(traces or [], outcomes=outcomes))


def _channel_outcomes(channel_id: str) -> dict[str, dict[int, float]]:
    """Each measured run's engaged rate and 7-day views (log), by run id (wave 112)."""
    out: dict[str, dict[int, float]] = {}
    try:
        from core.engagement_predictor import run_engagement_map

        out["engaged_rate"] = {int(k): float(v) for k, v in run_engagement_map(channel_id).items()}
    except Exception as exc:
        logger.debug("paid-signal engaged rates unread: %s", exc)
    try:
        from core.predictions.ledger import _views_outcomes

        out["views_7d"] = {int(k): float(v) for k, v in _views_outcomes(channel_id).items()}
    except Exception as exc:
        logger.debug("paid-signal views unread: %s", exc)
    return out
