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

# Per-1M-token public pricing (USD), input/output, by provider+model prefix.
# Used to price the real token ledger from core/llm_router. Override-friendly:
# unknown models fall back to a conservative default. Free credits don't change
# the modeled cost — they offset the bill, but the unit economics still inform
# routing (a free DeepSeek call is ~10x "cheaper value" than a paid gpt-4o one).
_LLM_PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # DeepSeek-V3 (deepseek-chat) — near-gpt-4o quality, ~10x cheaper
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    # Groq — free tier ($0); paid rates listed so a ledger still reflects value.
    "llama-3.1-8b": (0.05, 0.08),
    "llama-3.3-70b": (0.59, 0.79),
    "llama-3": (0.59, 0.79),
    # Ollama / local — zero marginal cost.
    "ollama": (0.0, 0.0),
    # Doubao (Volcengine Ark) — cheapest tier; lite vs pro
    "doubao-lite": (0.04, 0.08),
    "doubao-pro": (0.11, 0.28),
    "doubao": (0.11, 0.28),
    # Anthropic
    "claude-haiku": (1.00, 5.00),
    "claude-sonnet": (3.00, 15.00),
    "claude-opus": (15.00, 75.00),
}
_LLM_PRICE_DEFAULT = (1.00, 4.00)  # conservative blended fallback


def _rate(env: str, default: float) -> float:
    try:
        return float(os.getenv(env, str(default)))
    except (TypeError, ValueError):
        return default


def _price_for_model(model: str) -> tuple[float, float]:
    """Match a model id against the price table by longest known prefix."""
    m = (model or "").lower()
    best: tuple[float, float] | None = None
    best_len = -1
    for key, price in _LLM_PRICES.items():
        if key in m and len(key) > best_len:
            best, best_len = price, len(key)
    return best or _LLM_PRICE_DEFAULT


def llm_cost_from_usage(calls: list[dict[str, Any]] | None) -> float:
    """Price a token ledger (from core.llm_router.get_usage) in USD.

    Returns 0.0 for an empty ledger so callers can detect "no real data" and
    fall back to the heuristic estimate.
    """
    if not calls:
        return 0.0
    total = 0.0
    for c in calls:
        # Local Ollama has no marginal cost regardless of model name.
        if str(c.get("provider", "")).lower() == "ollama":
            continue
        model = str(c.get("model", ""))
        # OpenRouter free models (the `:free` suffix) are $0.
        if ":free" in model.lower():
            continue
        in_price, out_price = _price_for_model(model)
        total += (int(c.get("input_tokens", 0)) / 1_000_000.0) * in_price
        total += (int(c.get("output_tokens", 0)) / 1_000_000.0) * out_price
    return round(total, 6)


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

    # LLM: prefer the real per-provider token ledger (core/llm_router) when a run
    # recorded usage; fall back to the old word-count heuristic otherwise.
    llm = 0.0
    try:
        from core.llm_router import get_usage

        llm = llm_cost_from_usage(get_usage())
    except Exception:
        llm = 0.0
    if llm <= 0.0:
        # Heuristic fallback: total tokens ≈ a multiple of final script length.
        llm_tokens = max(words * 8, 1500)
        llm = (llm_tokens / 1000.0) * _rate("COST_LLM_PER_1K_TOKENS", 0.005)

    # TTS only happens on render. Local providers (Kokoro/XTTS/Piper via
    # TTS_PROVIDER, core/tts.py) have zero marginal cost — env read directly to
    # avoid an import cycle with core.tts.
    _local_tts = os.getenv("TTS_PROVIDER", "elevenlabs").strip().lower() in (
        "kokoro",
        "xtts",
        "piper",
    )
    tts = (chars / 1000.0) * _rate("COST_TTS_PER_1K_CHARS", 0.30) if rendered else 0.0
    if _local_tts:
        tts = 0.0

    # Apify: one actor run per active paid social signal — except youtube_competitors
    # when it was served by a free in-process backend (data.backend == "free"), which
    # costs $0 (see apis/free_backends.py, apis/youtube_apify_signal.py).
    def _billed_to_apify(name: str) -> bool:
        sig = signals.get(name) or {}
        if not sig.get("active"):
            return False
        return ((sig.get("data") or {}).get("backend") or "apify") == "apify"

    apify_runs = sum(1 for name in _APIFY_SIGNALS if _billed_to_apify(name))
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
