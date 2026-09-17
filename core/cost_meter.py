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

# TTS rate, derived from the operator's plan rather than list price:
# ElevenLabs **Creator** = $22/month for 100,000 characters -> $0.22 per 1k chars.
# Re-derive as (monthly cost / monthly character quota) when the plan changes.
# Note this is the *marginal* rate, matching how Apify and LLM are priced here. On a
# subscription the allocated cost per video is higher whenever the quota is under-used.
TTS_RATE_ENV = "COST_TTS_PER_1K_CHARS"
TTS_RATE_DEFAULT = 0.22

# Paid thumbnail APIs (Flux / Ideogram / Recraft). Pillow title cards are $0.
THUMBNAIL_RATE_ENV = "COST_THUMBNAIL_PER_IMAGE"
THUMBNAIL_RATE_DEFAULT = 0.045
_PAID_THUMBNAIL_PROVIDERS = frozenset({"flux", "ideogram", "recraft"})

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


def llm_cost_by_provider(calls: list[dict[str, Any]] | None) -> dict[str, float]:
    """Price a token ledger per provider (O12) -> {provider: usd}.

    Free-by-construction calls (local Ollama, OpenRouter ':free' slugs) price at
    $0 but are still reported, so the operator can see WHERE the free-first chain
    actually served a run rather than only what it cost.
    """
    out: dict[str, float] = {}
    for c in calls or []:
        provider = str(c.get("provider", "") or "unknown").lower()
        model = str(c.get("model", ""))
        free = provider == "ollama" or ":free" in model.lower()
        cost = 0.0
        if not free:
            in_price, out_price = _price_for_model(model)
            cost = (int(c.get("input_tokens", 0)) / 1_000_000.0) * in_price
            cost += (int(c.get("output_tokens", 0)) / 1_000_000.0) * out_price
        out[provider] = round(out.get(provider, 0.0) + cost, 6)
    return out


def llm_cost_by_stage(calls: list[dict[str, Any]] | None) -> dict[str, float]:
    """Price a token ledger per pipeline stage (script/brief/title/...)."""
    out: dict[str, float] = {}
    for c in calls or []:
        stage = str(c.get("stage") or c.get("tier") or "unknown").lower()
        provider = str(c.get("provider", "") or "unknown").lower()
        model = str(c.get("model", ""))
        free = provider == "ollama" or ":free" in model.lower()
        cost = 0.0
        if not free:
            in_price, out_price = _price_for_model(model)
            cost = (int(c.get("input_tokens", 0)) / 1_000_000.0) * in_price
            cost += (int(c.get("output_tokens", 0)) / 1_000_000.0) * out_price
        out[stage] = round(out.get(stage, 0.0) + cost, 6)
    return out


def llm_cost_from_usage(calls: list[dict[str, Any]] | None) -> float:
    """Price a token ledger (from core.llm_router.get_usage) in USD.

    Returns 0.0 for an empty ledger so callers can detect "no real data" and
    fall back to the heuristic estimate.
    """
    if not calls:
        return 0.0
    return round(sum(llm_cost_by_provider(calls).values()), 6)


def local_tts_selected(length_choice: str = "") -> bool:
    """True when TTS_PROVIDER names a zero-marginal-cost engine.

    Includes Edge (cloud, $0). Env is read directly rather than importing core.tts
    — that would be an import cycle.
    """
    provider = os.getenv("TTS_PROVIDER", "elevenlabs").strip().lower() or "elevenlabs"
    if length_choice:
        # #768: the render follows #758's per-length voice policy, so the meter must too -
        # an Extended render on piper was projected and stored as $1.25 of ElevenLabs.
        try:
            from core.tts import long_form_provider

            resolved = long_form_provider(provider, length_choice)
        except Exception:  # a meter must not raise; keep the env provider
            resolved = provider
        provider = resolved
    return provider in (
        "kokoro",
        "xtts",
        "piper",
        "qwen",
        "edge",
    )


def thumbnail_cost(provider: str | None) -> float:
    """USD for one generated image. Pillow / missing / unknown → $0 (don't invent billing)."""
    name = (provider or "").strip().lower()
    if name not in _PAID_THUMBNAIL_PROVIDERS:
        return 0.0
    return round(_rate(THUMBNAIL_RATE_ENV, THUMBNAIL_RATE_DEFAULT), 4)


def escaped_free_first(calls: list[dict[str, Any]] | None = None) -> bool:
    """True when a cheap/extract/premium call landed on a paid provider after a free miss."""
    if calls is None:
        try:
            from core.llm_router import get_usage

            calls = get_usage()
        except Exception:
            calls = []
    return any(bool(c.get("escaped_free_first")) for c in (calls or []))


def _tts_cache_fraction(tts_cached: bool | float) -> float:
    """True -> 1.0 (free), False -> 0.0 (full price), float -> clamp 0..1 (#402)."""
    if tts_cached is True:
        return 1.0
    if tts_cached is False:
        return 0.0
    try:
        return min(1.0, max(0.0, float(tts_cached)))
    except (TypeError, ValueError):
        return 0.0


def render_cost_lines(
    script: str = "",
    *,
    thumbnail_provider: str = "",
    tts_cached: bool | float = False,
    length_choice: str = "",
) -> dict[str, float]:
    """The cost lines that only exist once a render actually happened.

    Split out of `estimate_run_cost` so the render path can persist these *after* the
    fact. Both operator flows (`main.py`, `scripts/auto_generate.py`) finalize the run
    before rendering, so the stored cost carried `tts: 0.0` on every rendered run and
    `unit_economics` computed margin against a cost missing most of itself.

    Deliberately excludes llm/apify/web_search: those are session-metered and already
    persisted by the pre-render estimate, so recomputing them here (after the session
    ledger has moved on) would overwrite good values with wrong ones.
    """
    chars = len(script or "")
    full = (chars / 1000.0) * _rate(TTS_RATE_ENV, TTS_RATE_DEFAULT)
    if local_tts_selected(length_choice):
        tts = 0.0
    else:
        frac = _tts_cache_fraction(tts_cached)
        tts = full * (1.0 - frac)
    return {
        "tts": round(tts, 4),
        "render": round(_rate("COST_RENDER_PER_VIDEO", 0.0), 4),
    }


def merge_render_cost(
    existing: dict[str, Any] | None,
    script: str = "",
    *,
    thumbnail_provider: str | None = None,
    tts_cached: bool | float = False,
    length_choice: str = "",
) -> dict[str, float]:
    """Fold the render lines into an already-persisted cost dict and re-total it.

    `thumbnail_provider` is the backend that actually wrote the image (`flux` /
    `ideogram` / `recraft` / `pillow`). Omit it to leave a previously stored
    thumbnail line alone (idempotent TTS-only re-merge). Pillow and missing
    images meter $0.
    """
    merged: dict[str, float] = {}
    for key, value in (existing or {}).items():
        if key == "total":
            continue
        try:
            merged[key] = round(float(value), 4)
        except (TypeError, ValueError):
            continue
    merged.update(render_cost_lines(script, tts_cached=tts_cached, length_choice=length_choice))
    if thumbnail_provider is not None:
        merged["thumbnail"] = thumbnail_cost(thumbnail_provider)
    merged["total"] = round(sum(v for k, v in merged.items() if k != "total"), 4)
    return merged


def estimate_run_cost(
    *,
    script: str = "",
    signals: dict[str, Any] | None = None,
    rendered: bool = False,
    length_choice: str = "",
) -> dict[str, float]:
    """Estimate the fully-loaded cost of a run. Returns a breakdown + total (USD)."""
    signals = signals or {}
    words = len([w for w in script.split() if w])

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

    # TTS only happens on render; local providers meter $0 (see render_cost_lines).
    tts = render_cost_lines(script, length_choice=length_choice)["tts"] if rendered else 0.0

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
    ("thumbnail", "thumb"),
    ("render", "render"),
)


def standard_would_have_billed(
    script: str = "",
    *,
    include_thumbnail: bool = True,
) -> dict[str, float]:
    """Counterfactual Standard bill: ElevenLabs TTS + paid thumbnail rates.

    Ignores TTS_PROVIDER so a Free/Piper run can show what the Creator plan
    would have charged. Does not mutate the persisted cost dict (no double-bill).
    """
    chars = len(script or "")
    tts = (chars / 1000.0) * _rate(TTS_RATE_ENV, TTS_RATE_DEFAULT)
    thumb = thumbnail_cost("flux") if include_thumbnail else 0.0
    return {
        "tts": round(tts, 4),
        "thumbnail": round(thumb, 4),
        "total": round(tts + thumb, 4),
    }


def format_standard_billed_line(
    script: str = "",
    *,
    include_thumbnail: bool = True,
) -> str:
    """Operator dry-run line when this run did not pay ElevenLabs/Flux."""
    if not (script or "").strip():
        return ""
    if not local_tts_selected() and os.getenv("FREE_MODE_STRICT", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return ""
    billed = standard_would_have_billed(script, include_thumbnail=include_thumbnail)
    return (
        f"Standard would have billed: ${billed['total']:.4f} "
        f"(tts ${billed['tts']:.4f} · thumb ${billed['thumbnail']:.4f})"
    )


def free_mode_cost_proof(cost: dict[str, float] | None) -> str:
    """#580: prove a Free/Piper run actually billed $0, or say that it did not."""
    billed = dict(cost or {})
    tts = float(billed.get("tts") or 0.0)
    total = float(billed.get("total") or 0.0)
    if tts <= 0.0 and total <= 0.0:
        return "free-mode billed $0.0000 (tts $0.0000)"
    return f"free-mode billed ${total:.4f} — not $0 (tts ${tts:.4f})"


def format_cost_line(
    cost: dict[str, float] | None,
    *,
    llm_by_provider: dict[str, float] | None = None,
    llm_by_stage: dict[str, float] | None = None,
    escaped_free_first_llm: bool | None = None,
) -> str:
    """One-line operator summary: total + the non-zero components.

    `llm_by_provider` (O12) appends which provider served the LLM spend, e.g.
    `llm $0.0049 [deepseek $0.0049 · openrouter $0]` — the free-first chain's whole
    point is that most calls land on a $0 provider, which the aggregate hides.

    Returns "" when there's nothing to show, so callers can skip the line.
    """
    if not cost:
        return ""
    total = float(cost.get("total") or 0.0)
    parts = []
    for key, label in _COST_PARTS:
        if float(cost.get(key) or 0.0) <= 0:
            continue
        part = f"{label} ${cost[key]:.4f}"
        if key == "llm":
            if llm_by_provider:
                inner = " · ".join(
                    f"{prov} ${amt:.4f}" if amt > 0 else f"{prov} $0"
                    for prov, amt in sorted(llm_by_provider.items(), key=lambda kv: (-kv[1], kv[0]))
                )
                if inner:
                    part += f" [{inner}]"
            if llm_by_stage:
                stages = " · ".join(
                    f"{stg} ${amt:.4f}" if amt > 0 else f"{stg} $0"
                    for stg, amt in sorted(llm_by_stage.items(), key=lambda kv: (-kv[1], kv[0]))
                )
                if stages:
                    part += f" stages[{stages}]"
        parts.append(part)
    breakdown = f" ({' · '.join(parts)})" if parts else ""
    line = f"Est. run cost: ${total:.4f}{breakdown}"
    if escaped_free_first_llm:
        line += "  ! escaped free-first LLM"
    return line
