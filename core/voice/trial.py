"""#1799 (B09.3, wave 159; the operator approved, 11-07): a cheaper voice on news Shorts as a trial.

Nov 8-21 a news draft takes an arm of `news_voice`: "piper" (the free local voice) or
"elevenlabs". The arm is chosen when the draft is written - the one with fewer drafts among the
drafts of the same length arm (#1637's trial runs over the same news drafts; two round-robins over
one stream would move in lockstep, so every Piper draft would also be a short one) - recorded in the
experiments store, and read at render (`pipeline.run_media_only` -> `tts.forced_voice`): Piper
voices the render, and the ElevenLabs arm keeps the 1-in-6 Piper mix (`TTS_PIPER_MIX_EVERY`, unset
= 6) off, so each arm is what it says. Piper not ready falls back to ElevenLabs (its cost says so).
The weekly report reads the arms on stayed share and first-week organic views (`voice_trial_lines`).
`VOICE_TRIAL=false` stops it (the suite does).
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Callable
from datetime import date
from typing import Any

from core.logging import get_logger

logger = get_logger("core.voice.trial")

VOICE_LEVER = "news_voice"
VOICE_TRIAL = ("2026-11-08", "2026-11-21")
VOICE_ARMS = ("piper", "elevenlabs")


def enabled() -> bool:
    return os.getenv("VOICE_TRIAL", "true").strip().lower() not in ("0", "false", "no", "off")


def _rows(channel_id: str, lever: str) -> list[dict[str, Any]]:
    from core.experiments import _assignments

    return list(_assignments(channel_id, lever))


def voice_trial_arm(
    channel_id: str,
    intent: str,
    *,
    length_arm: str = "",
    today: date | None = None,
    rows: list[dict[str, Any]] | None = None,
    length_rows: list[dict[str, Any]] | None = None,
) -> str | None:
    """The arm for a news draft inside `VOICE_TRIAL`, balanced within its length arm; None outside
    it, for another intent, or with `VOICE_TRIAL` off."""
    from core.angle_intent import ANGLE_NEWS

    day = (today or date.today()).isoformat()
    if not enabled() or intent != ANGLE_NEWS or not VOICE_TRIAL[0] <= day <= VOICE_TRIAL[1]:
        return None
    try:
        voice = rows if rows is not None else _rows(channel_id, VOICE_LEVER)
        if length_rows is None:
            from core.batch_generation import LENGTH_LEVER

            length_rows = _rows(channel_id, LENGTH_LEVER)
    except Exception as exc:
        logger.debug("voice arms unread: %s", exc)
        voice, length_rows = [], []
    length_of = {int(r.get("run_id") or 0): str(r.get("arm") or "") for r in length_rows or []}
    same = [r for r in voice if length_of.get(int(r.get("run_id") or 0), "") == length_arm]
    counts = {arm: sum(1 for r in same if r.get("arm") == arm) for arm in VOICE_ARMS}
    return min(VOICE_ARMS, key=lambda a: counts[a])


def arm_for_run(channel_id: str, run_id: int | None) -> str | None:
    """The `news_voice` arm a run was drafted with, or None."""
    if not run_id:
        return None
    try:
        for row in _rows(channel_id, VOICE_LEVER):
            if int(row.get("run_id") or 0) == int(run_id):
                arm = str(row.get("arm") or "")
                return arm if arm in VOICE_ARMS else None
    except Exception as exc:
        logger.debug("voice arm unread for run %s: %s", run_id, exc)
    return None


def voice_trial_lines(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
    features: Callable[[int], dict[str, Any]] | None = None,
    arms: dict[int, str] | None = None,
) -> list[str]:
    """#1799's readout: each arm's median first-week organic views and stayed share, or [] before
    a draft of each arm is measured."""
    try:
        if arms is None:
            arms = {int(r.get("run_id") or 0): str(r.get("arm") or "")
                    for r in _rows(channel_id, VOICE_LEVER)}  # fmt: skip
        if not arms:
            return []
        from core.success.formats import measured_shorts

        by_arm: dict[str, list[dict[str, Any]]] = {}
        for short in measured_shorts(channel_id, today=today, rows=rows, features=features):
            arm = arms.get(int(short.get("run_id") or 0))
            if arm:
                by_arm.setdefault(arm, []).append(short)
        if len(by_arm) < 2:
            return []
        parts = []
        for arm in sorted(by_arm):
            shorts = by_arm[arm]
            stayed = [s["stayed"] for s in shorts if s.get("stayed") is not None]
            share = f", stayed {statistics.median(stayed):.0%}" if stayed else ""
            parts.append(f"{arm} {statistics.median(s['views7'] for s in shorts):g} (n={len(shorts)}"
                         f"{share})")  # fmt: skip
        return ["Voice on news Shorts (#1799, Piper against ElevenLabs; median first-week organic "
                "views): " + " · ".join(parts)]  # fmt: skip
    except Exception as exc:
        logger.debug("voice trial lines skipped: %s", exc)
        return []
