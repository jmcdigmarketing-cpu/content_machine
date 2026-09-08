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
    fps: float = 30.0,
) -> tuple[int, bool]:
    """J/K/L = 5s jump; comma/period = one frame. Position is clamped to the clip."""
    raw = (key or "").strip()
    token = raw.lower()
    pos = max(0, min(int(position_ms), int(duration_ms)))
    dur = max(0, int(duration_ms))
    holding = bool(paused)
    frame_ms = max(1, int(round(1000.0 / float(fps or 30.0))))
    if token == "j":
        pos = max(0, pos - int(step_ms))
    elif token == "l":
        pos = min(dur, pos + int(step_ms))
    elif token == "k":
        holding = not holding
    elif raw in {",", "<"}:
        pos = max(0, pos - frame_ms)
    elif raw in {".", ">"}:
        pos = min(dur, pos + frame_ms)
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
