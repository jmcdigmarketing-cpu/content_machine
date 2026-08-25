"""Unattended render requires a recent human operator (candidate 90).

Overnight drafts stay render-free. The cron path that *does* render is
``scripts/auto_generate`` plus ``job_type=render`` worker jobs. Autonomy vs the
2026 policy gate: do not auto-render unless ``main.py`` or an attended ``ops``
command ran in the last N hours.

Opt-in (``HUMAN_PRESENCE_HOURS`` empty/0/off = disabled) so leftover env cannot
freeze the unit suite. Missing heartbeat fail-closes when the gate is on.
Heartbeat writes ``data/operator_heartbeat.json`` only — never quota_state.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.human_presence")

HEARTBEAT_FILE = os.path.join(DATA_DIR, "operator_heartbeat.json")

# Cron / loop entry points must not stamp a heartbeat (would always pass).
UNATTENDED_OPS = frozenset({"overnight", "daily-sync", "worker"})


def hours_window() -> float | None:
    raw = os.getenv("HUMAN_PRESENCE_HOURS", "").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return val if val > 0 else None


def gate_enabled() -> bool:
    return hours_window() is not None


def touch(*, at: float | None = None, path: str | None = None) -> None:
    """Record that a human is at the keyboard. Fail-open on IO errors.

    Default path is a no-op unless the gate is on, so ``ops.main()`` in the
    unit suite cannot write ``data/operator_heartbeat.json``. Tests pass
    ``path=`` to exercise the file.
    """
    dest = path or HEARTBEAT_FILE
    if path is None and not gate_enabled():
        return
    payload = {"at": float(at if at is not None else time.time())}
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    except Exception as exc:
        logger.debug("operator heartbeat not written: %s", exc)


def last_human_at(*, path: str | None = None) -> float | None:
    dest = path or HEARTBEAT_FILE
    try:
        with open(dest, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return float(data.get("at"))
    except (TypeError, ValueError):
        return None


def last_seen_label(*, now: float | None = None, path: str | None = None) -> str:
    """Compact, honest heartbeat age for the tray."""
    if not gate_enabled():
        return "Human: heartbeat off"
    stamp = last_human_at(path=path)
    if stamp is None:
        return "Human: never"
    age_s = max(0.0, float(now if now is not None else time.time()) - stamp)
    if age_s < 60:
        return "Human: just now"
    if age_s < 3600:
        return f"Human: {int(age_s // 60)}m ago"
    if age_s < 86400:
        return f"Human: {int(age_s // 3600)}h ago"
    return f"Human: {int(age_s // 86400)}d ago"


def unattended_render_block_reason(
    *,
    now: float | None = None,
    path: str | None = None,
) -> str | None:
    """Why an unattended render must wait for a human, or None when allowed."""
    hours = hours_window()
    if hours is None:
        return None
    stamp = last_human_at(path=path)
    if stamp is None:
        return (
            f"human-presence gate: no operator heartbeat "
            f"(run main.py or attended ops within {hours:g}h)"
        )
    age_h = (float(now if now is not None else time.time()) - stamp) / 3600.0
    if age_h > hours:
        return f"human-presence gate: last operator {age_h:.1f}h ago " f"(need within {hours:g}h)"
    return None


def maybe_touch_ops(command: str, **kwargs: Any) -> None:
    """Stamp heartbeat for attended ops commands. Nested try: import-safe."""
    if command in UNATTENDED_OPS:
        return
    try:
        touch(**kwargs)
    except Exception as exc:
        logger.debug("ops heartbeat skipped: %s", exc)
