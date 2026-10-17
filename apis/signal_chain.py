"""
Fallback chains for signals — degrade through providers instead of returning zero.

Same pattern as assets/manager.py (local → Pexels → Pixabay).
"""

from __future__ import annotations

from collections.abc import Callable

from apis.signal_contract import classify_exception, make_signal, normalize_signal

ProviderFn = Callable[[str], dict]


def chain_signal(
    topic: str,
    providers: list[tuple[str, ProviderFn]],
    *,
    min_score: float = 1.0,
) -> dict:
    """
    Try providers in order; return first connected+active signal above min_score.

    Attaches data.provider and data.fallback_chain for explainability.
    """
    attempts: list[dict[str, str]] = []
    last: dict | None = None
    answered: tuple[str, dict] | None = None  # #1233: the first provider that connected

    for name, fn in providers:
        try:
            sig = normalize_signal(fn(topic))
        except Exception as exc:
            status, detail = classify_exception(exc)
            sig = make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=f"{name}: {detail}",
            )

        attempts.append(
            {
                "provider": name,
                "status": str(sig.get("status", "")),
                "active": bool(sig.get("active")),
                "score": float(sig.get("score", 0) or 0),
            }
        )
        last = sig
        if answered is None and sig.get("connected"):
            answered = (name, sig)

        if (
            sig.get("connected")
            and sig.get("active")
            and float(sig.get("score", 0) or 0) >= min_score
        ):
            return _tag_provider(sig, name, attempts)

    if last and last.get("connected"):
        provider = attempts[-1]["provider"] if attempts else "unknown"
        return _tag_provider(last, provider, attempts, fallback=True)
    if answered is not None:
        # #1233: AniList said "no anime match" and Jikan could not be reached; the canary and
        # the data-quality streak read "All providers in chain failed". A provider that answered
        # is the answer.
        return _tag_provider(answered[1], answered[0], attempts, fallback=True)

    return make_signal(
        connected=False,
        active=False,
        status="unavailable",
        status_detail="All providers in chain failed",
        data={"fallback_chain": attempts},
    )


def _tag_provider(
    sig: dict,
    provider: str,
    attempts: list[dict[str, str]],
    *,
    fallback: bool = False,
) -> dict:
    out = dict(sig)
    data = dict(out.get("data") or {})
    data["provider"] = provider
    data["fallback_chain"] = attempts
    if fallback:
        data["fallback_only"] = True
    out["data"] = data
    detail = out.get("status_detail") or ""
    via = f"via {provider}" + (" (fallback)" if fallback else "")
    out["status_detail"] = f"{detail} — {via}" if detail else via
    return out
