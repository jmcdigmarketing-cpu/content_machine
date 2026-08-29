"""Hard character cap before TTS (candidate 75).

Extended is a cost multiplier on the ~91% TTS line. Refuse the synth rather
than regen-then-pay or silently clip (clipping would gut the script). Default
ceiling covers Long (~750 words / ~4.5k chars); Extended must raise
``TTS_MAX_CHARS`` or pass ``--force``. Unset-but-present default is on;
``0`` / ``off`` disables.
"""

from __future__ import annotations

import os

from core.utils import clean_script_for_tts

_DEFAULT_MAX = 5000


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


def tts_char_cap_reason(script: str) -> str | None:
    """Why TTS should be refused, or None when the script is under the ceiling."""
    cap = max_chars()
    if cap is None:
        return None
    n = len(clean_script_for_tts(script or ""))
    if n <= cap:
        return None
    return (
        f"TTS character cap: {n:,} chars > {cap:,} "
        "(TTS_MAX_CHARS; Extended is a cost multiplier — raise the cap or shorten)"
    )


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
