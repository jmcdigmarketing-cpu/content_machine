"""#209 J/K/L review keys — toolkit-agnostic so CI can call them without decoding."""

from __future__ import annotations

from typing import Any

_STEP_MS = 5_000


def apply_review_key(
    key: str,
    *,
    position_ms: int,
    duration_ms: int,
    paused: bool,
    step_ms: int = _STEP_MS,
) -> tuple[int, bool]:
    """J = back, K = pause/play, L = forward. Position is clamped to the clip."""
    token = (key or "").strip().lower()
    pos = max(0, min(int(position_ms), int(duration_ms)))
    dur = max(0, int(duration_ms))
    holding = bool(paused)
    if token == "j":
        pos = max(0, pos - int(step_ms))
    elif token == "l":
        pos = min(dur, pos + int(step_ms))
    elif token == "k":
        holding = not holding
    return pos, holding


def approve_command(ctx: dict[str, Any] | None) -> str:
    """Same string the HTML booth prints — not a second queue."""
    data = ctx or {}
    cmd = str(data.get("approve_cmd") or "").strip()
    if cmd:
        return cmd
    run_id = data.get("run_id")
    try:
        if run_id is not None and run_id != "":
            return f"py -m scripts.ops requeue-upload --run-id {int(run_id)}"
    except (TypeError, ValueError):
        pass
    return "py -m scripts.ops list-uploads"
