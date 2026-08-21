"""TTS provider Bayesian report (candidate 67) — report-only.

Joins published engaged-rates to inferred TTS arms (ElevenLabs vs local/Piper)
using the same evaluator as hook_style. Never writes experiments.json, never
calls start_experiment, never changes TTS_PROVIDER.
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger

logger = get_logger("core.tts_provider_report")

_ARMS = ("elevenlabs", "piper")


def _load_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def infer_arm(*, tts_cost: float, tts_provider: str = "", rendered: bool = True) -> str | None:
    """Map a run to an arm. Explicit provider wins; else billed TTS vs $0 local."""
    name = (tts_provider or "").strip().lower()
    if name in ("piper", "kokoro", "xtts", "qwen"):
        return "piper"
    if name == "elevenlabs":
        return "elevenlabs"
    if not rendered:
        return None
    try:
        cost = float(tts_cost)
    except (TypeError, ValueError):
        return None
    if cost > 0:
        return "elevenlabs"
    return "piper"


def arm_outcomes(
    rows: list[dict[str, Any]],
) -> dict[str, list[float]]:
    """rows: {engaged_rate, tts_cost, tts_provider?, rendered?}."""
    out: dict[str, list[float]] = {a: [] for a in _ARMS}
    for row in rows:
        try:
            rate = float(row.get("engaged_rate"))
        except (TypeError, ValueError):
            continue
        arm = infer_arm(
            tts_cost=float(row.get("tts_cost") or 0.0),
            tts_provider=str(row.get("tts_provider") or ""),
            rendered=bool(row.get("rendered", True)),
        )
        if arm in out:
            out[arm].append(rate)
    return out


def _rows_from_channel(channel_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from core.engagement import engaged_rate
        from storage.repositories.content_runs import get_content_run_repository
        from storage.repositories.publish_log import get_publish_log_repository

        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
        runs = {r.id: r for r in get_content_run_repository().list_for_channel(channel_id)}
    except Exception as exc:
        logger.debug("tts provider rows skipped: %s", exc)
        return rows
    for log in logs:
        rate = engaged_rate(log.metrics_json)
        if rate is None or not log.content_run_id:
            continue
        rec = runs.get(int(log.content_run_id))
        features = _load_json(getattr(rec, "features_json", None) if rec else None)
        cost = features.get("cost") or {}
        rows.append(
            {
                "engaged_rate": float(rate),
                "tts_cost": float(cost.get("tts") or 0.0),
                "tts_provider": str(features.get("tts_provider") or ""),
                "rendered": str(getattr(rec, "status", "") or "") in ("rendered", "published")
                or bool(cost.get("tts") or cost.get("render")),
            }
        )
    return rows


def report(channel_id: str, *, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from core import experiment_stats

    data = rows if rows is not None else _rows_from_channel(channel_id)
    outcomes = arm_outcomes(data)
    evaluation = experiment_stats.evaluate(outcomes)
    return {
        "channel_id": channel_id,
        "auto_switch": False,
        "arms": evaluation.get("arms") or {},
        "winner": evaluation.get("winner"),
        "status": evaluation.get("status"),
        "baseline": evaluation.get("baseline"),
        "n": {arm: len(outcomes.get(arm) or []) for arm in _ARMS},
    }


def render_report(data: dict[str, Any]) -> str:
    lines = [
        f"TTS provider report (report-only, no auto-switch) — {data.get('channel_id')}",
        "=" * 56,
        f"  status : {data.get('status')}",
    ]
    if data.get("winner"):
        lines.append(f"  leader : {data['winner']} (do not flip TTS_PROVIDER from this)")
    for arm in _ARMS:
        d = (data.get("arms") or {}).get(arm) or {}
        n = int(d.get("n") or 0)
        line = f"    {arm:<12} measured {n:>2}"
        if n:
            line += (
                f", avg {float(d.get('rate') or 0):.0%}, P(best) {float(d.get('p_best') or 0):.0%}"
            )
        lines.append(line)
    lines.append("  TTS_PROVIDER is unchanged. Piper remains an operator taste call.")
    return "\n".join(lines)
