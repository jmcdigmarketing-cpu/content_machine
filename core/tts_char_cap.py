"""Hard character cap before TTS (candidate 75).

Extended is a cost multiplier on the ~91% TTS line. Refuse the synth rather
than regen-then-pay or silently clip (clipping would gut the script). Default
ceiling covers Long (~750 words / ~4.5k chars). A 15% overage is a warning,
not a hard stop (run 76: 5,720 vs 5,000). Choosing Extended raises the floor
to the preset's max words. ``--force`` / interactive y still bypasses a hard
stop. ``0`` / ``off`` disables.
"""

from __future__ import annotations

import os

from core.utils import clean_script_for_tts

_DEFAULT_MAX = 5000
_GRACE = 0.15
_CHARS_PER_WORD = 6


def max_chars() -> int | None:
    """Character ceiling, or None when the cap is disabled."""
    raw = os.getenv("TTS_MAX_CHARS", str(_DEFAULT_MAX)).strip()
    if raw.lower() in ("", "off", "false", "no"):
        return None
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_MAX
    if val <= 0:
        return None
    return val


def effective_cap(*, length_choice: str = "") -> int | None:
    """Env ceiling, raised to the selected length preset's max when larger."""
    cap = max_chars()
    if cap is None:
        return None
    choice = (length_choice or "").strip()
    if not choice:
        return cap
    try:
        from core.script_length import get_length_preset

        floor = get_length_preset(choice).max_words * _CHARS_PER_WORD
    except Exception:
        return cap
    return max(cap, floor)


def tts_char_count(script: str) -> int:
    return len(clean_script_for_tts(script or ""))


def _hard_ceiling(cap: int) -> int:
    return int(cap * (1 + _GRACE))


def tts_char_cap_reason(
    script: str = "",
    *,
    force: bool = False,
    length_choice: str = "",
    char_count: int | None = None,
) -> str | None:
    """Why TTS should be refused, or None when the script may synth.

    Force skips the hard stop. A count inside the 15% grace band is not a
    refusal — see ``tts_char_cap_warn``. ``char_count`` is the persistable
    feeder for publish-time checks that no longer have the full script (#738).
    """
    if force:
        return None
    cap = effective_cap(length_choice=length_choice)
    if cap is None:
        return None
    n = int(char_count) if char_count is not None else tts_char_count(script)
    if n <= _hard_ceiling(cap):
        return None
    return (
        f"TTS character cap: {n:,} chars > {cap:,} "
        "(TTS_MAX_CHARS; Extended is a cost multiplier — raise the cap or shorten)"
    )


def tts_char_cap_warn(script: str, *, length_choice: str = "") -> str | None:
    """Overage inside the 15% grace band — tell the operator, then render."""
    cap = effective_cap(length_choice=length_choice)
    if cap is None:
        return None
    n = tts_char_count(script)
    if n <= cap:
        return None
    if n <= _hard_ceiling(cap):
        return (
            f"TTS character cap: {n:,} chars > {cap:,} "
            f"(within {int(_GRACE * 100)}% grace; rendering)"
        )
    return None


_last_forecast: dict[str, float | int | None] | None = None


def reset_tts_forecast() -> None:
    global _last_forecast
    _last_forecast = None


def last_tts_forecast() -> dict[str, float | int | None] | None:
    return dict(_last_forecast) if _last_forecast else None


def forecast_tts(script: str) -> dict[str, float | int | None]:
    """Estimate chars and $ before synth (#371). Does not call a provider."""
    global _last_forecast
    from core.cost_meter import TTS_RATE_DEFAULT, TTS_RATE_ENV, _rate
    from core.utils import clean_script_for_tts

    chars = len(clean_script_for_tts(script or ""))
    usd = round((chars / 1000.0) * _rate(TTS_RATE_ENV, TTS_RATE_DEFAULT), 4)
    _last_forecast = {
        "forecast_chars": chars,
        "forecast_usd": usd,
        "actual_chars": None,
        "delta_chars": None,
    }
    return dict(_last_forecast)


def record_tts_actual(actual_chars: int) -> dict[str, float | int | None]:
    """Stamp actual synth chars against the last forecast."""
    global _last_forecast
    snap = dict(_last_forecast) if _last_forecast else forecast_tts("")
    snap["actual_chars"] = int(actual_chars)
    forecast = int(snap.get("forecast_chars") or 0)
    snap["delta_chars"] = int(actual_chars) - forecast
    _last_forecast = snap
    return dict(snap)
