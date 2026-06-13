"""
Explainability layer — why now / why this / contrarian angle.

The analyst product is the rationale, not the number.
"""

from __future__ import annotations

from typing import Any


def build_explainability(
    *,
    topic: str,
    composite_score: float,
    signals: dict[str, Any],
    signal_breakdown: dict[str, float],
    corroboration: dict[str, Any],
    trajectory: dict[str, Any],
    opportunity_window: dict[str, Any],
    research_brief: dict[str, Any],
) -> dict[str, Any]:
    fired = _signals_fired(signals, signal_breakdown)
    why_now = _why_now(trajectory, corroboration, opportunity_window)
    why_this = _why_this(topic, composite_score, fired, signal_breakdown)
    contrarian = _contrarian_angle(research_brief, opportunity_window, fired)

    return {
        "why_now": why_now,
        "why_this": why_this,
        "contrarian_angle": contrarian,
        "signals_fired": fired,
        "corroboration_label": corroboration.get("label", ""),
    }


def _signals_fired(
    signals: dict[str, Any],
    breakdown: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, weight in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
        sig = signals.get(name) or {}
        rows.append(
            {
                "signal": name,
                "score": round(float(sig.get("score", 0) or 0), 1),
                "confidence": round(float(sig.get("confidence", 0) or 0), 2),
                "weighted_contribution": round(weight, 3),
                "status": sig.get("status", ""),
            }
        )
    return rows[:10]


def _why_now(
    trajectory: dict[str, Any],
    corroboration: dict[str, Any],
    window: dict[str, Any],
) -> str:
    parts: list[str] = []
    if trajectory.get("summary"):
        parts.append(trajectory["summary"])
    label = corroboration.get("label")
    if label:
        parts.append(f"Corroboration: {label}.")
    if window.get("summary"):
        parts.append(window["summary"])
    return " ".join(parts) if parts else "Run additional snapshots for temporal context."


def _why_this(
    topic: str,
    score: float,
    fired: list[dict[str, Any]],
    breakdown: dict[str, float],
) -> str:
    if not fired:
        return f"Topic '{topic}' lacks active weighted signals at score {score:.1f}."

    top = fired[0]
    second = fired[1]["signal"] if len(fired) > 1 else None
    lead = (
        f"Composite {score:.1f} driven primarily by {top['signal']} "
        f"(signal {top['score']:.0f}, weight share {top['weighted_contribution']:.2f})."
    )
    if second:
        lead += f" Secondary lift from {second}."
    return lead


def _contrarian_angle(
    brief: dict[str, Any],
    window: dict[str, Any],
    fired: list[dict[str, Any]],
) -> str:
    angles = list(brief.get("debate_angles") or [])
    if window.get("window_status") == "closed" and angles:
        return f"Saturation is high — lead with a contrarian take: {angles[0]}"
    if angles and len(angles) > 1:
        return f"Under-covered angle to test: {angles[-1]}"
    if angles:
        return angles[0]
    if fired:
        return (
            f"Flip the consensus implied by {fired[0]['signal']} — "
            "preview what skeptics are missing."
        )
    return "No strong contrarian hook — narrow the topic or wait for corroboration."
