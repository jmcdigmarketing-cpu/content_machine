"""Per-run cost estimation (v0) — unit economics for every video.

You cannot optimize monetization you cannot measure (roadmap §5). This is a cheap,
heuristic estimate of the fully-loaded cost of a run — LLM + TTS + Apify + web
search + render — stored on the run's features so margin can be tracked later.

These are ESTIMATES, not billed amounts: counts × configurable rates. Rates default
to rough public pricing and can be overridden via env vars so the model improves
without code changes. The point of v0 is to start accruing the number.
"""

from __future__ import annotations

import os
from typing import Any

# Signals that incur a paid Apify actor run.
_APIFY_SIGNALS = ("reddit", "twitter", "tiktok_trends", "youtube_competitors")


def _rate(env: str, default: float) -> float:
    try:
        return float(os.getenv(env, str(default)))
    except (TypeError, ValueError):
        return default


def estimate_run_cost(
    *,
    script: str = "",
    signals: dict[str, Any] | None = None,
    rendered: bool = False,
) -> dict[str, float]:
    """Estimate the fully-loaded cost of a run. Returns a breakdown + total (USD)."""
    signals = signals or {}
    words = len([w for w in script.split() if w])
    chars = len(script)

    # LLM: discovery variants + brief + content + expansion are many calls; approximate
    # total tokens as a multiple of the final script length (blended in+out rate).
    llm_tokens = max(words * 8, 1500)
    llm = (llm_tokens / 1000.0) * _rate("COST_LLM_PER_1K_TOKENS", 0.005)

    # TTS only happens on render.
    tts = (chars / 1000.0) * _rate("COST_TTS_PER_1K_CHARS", 0.30) if rendered else 0.0

    # Apify: one actor run per active paid social signal.
    apify_runs = sum(1 for name in _APIFY_SIGNALS if (signals.get(name) or {}).get("active"))
    apify = apify_runs * _rate("COST_APIFY_PER_RUN", 0.02)

    # Web search: one query if the web_search signal was active.
    ws_active = bool((signals.get("web_search") or {}).get("active"))
    web_search = (1 if ws_active else 0) * _rate("COST_WEB_SEARCH_PER_QUERY", 0.008)

    # Render compute is local/near-free; track a nominal cost for completeness.
    render = _rate("COST_RENDER_PER_VIDEO", 0.0) if rendered else 0.0

    total = round(llm + tts + apify + web_search + render, 4)
    return {
        "llm": round(llm, 4),
        "tts": round(tts, 4),
        "apify": round(apify, 4),
        "web_search": round(web_search, 4),
        "render": round(render, 4),
        "total": total,
    }


# Order + short labels for the operator-facing breakdown.
_COST_PARTS = (
    ("llm", "llm"),
    ("tts", "tts"),
    ("apify", "apify"),
    ("web_search", "web"),
    ("render", "render"),
)


def format_cost_line(cost: dict[str, float] | None) -> str:
    """One-line operator summary: total + the non-zero components.

    Returns "" when there's nothing to show, so callers can skip the line.
    """
    if not cost:
        return ""
    total = float(cost.get("total") or 0.0)
    parts = [
        f"{label} ${cost[key]:.4f}" for key, label in _COST_PARTS if float(cost.get(key) or 0.0) > 0
    ]
    breakdown = f" ({' · '.join(parts)})" if parts else ""
    return f"Est. run cost: ${total:.4f}{breakdown}"
