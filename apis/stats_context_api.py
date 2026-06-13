"""
Unified stats context: BALLDONTLIE API (preferred) → reference scrapers (fallback).

Registered as signal `stats_context`. Also used by research brief.
"""

from __future__ import annotations

import os
from typing import Any

from apis.api_sports_api import gather_api_sports_context
from apis.balldontlie_api import gather_balldontlie_context
from apis.pro_sports_stats_api import gather_nflverse_context, gather_pybaseball_context
from apis.scrapers.base import detect_stat_domains, scrape_enabled
from apis.scrapers.basketball_reference import fetch_bref_stats
from apis.scrapers.espn_stats import fetch_espn_stats
from apis.scrapers.football_reference import fetch_pfr_stats
from apis.signal_chain import chain_signal
from apis.signal_contract import STATUS_INACTIVE, STATUS_OK, STATUS_UNAVAILABLE, make_signal


def _score_from_lines(sources: list[dict[str, Any]]) -> float:
    total_lines = sum(len(s.get("lines") or []) for s in sources)
    if total_lines >= 4:
        return 85.0
    if total_lines >= 2:
        return 70.0
    if total_lines >= 1:
        return 55.0
    return 0.0


def _gather_scraper_context(topic: str) -> dict[str, Any]:
    if not scrape_enabled():
        return {"connected": False, "sources": [], "lines": []}

    domains = detect_stat_domains(topic)
    if not domains:
        return {"connected": True, "sources": [], "lines": [], "domains": []}

    sources: list[dict[str, Any]] = []
    for domain in domains:
        if domain == "nba":
            sources.append(fetch_bref_stats(topic))
            sources.append(fetch_espn_stats(topic, domain="nba"))
        elif domain == "nfl":
            sources.append(fetch_pfr_stats(topic))
            sources.append(fetch_espn_stats(topic, domain="nfl"))

    lines: list[str] = []
    for src in sources:
        name = src.get("source") or "stats"
        for line in src.get("lines") or []:
            if line:
                lines.append(f"[{name}] {line}")

    return {
        "connected": True,
        "domains": domains,
        "sources": sources,
        "lines": lines[:12],
        "provider": "scrapers",
    }


def _stats_signal_from_context(ctx: dict[str, Any], *, provider_label: str) -> dict:
    lines = ctx.get("lines") or []
    ctx.get("domains") or detect_stat_domains(ctx.get("topic", ""))
    if not lines:
        return make_signal(
            connected=bool(ctx.get("connected")),
            active=False,
            score=0,
            data=ctx,
            status=STATUS_INACTIVE,
            status_detail=f"No stat lines ({provider_label})",
        )
    score = _score_from_lines([{"lines": lines}])
    return make_signal(
        connected=True,
        active=True,
        score=score,
        confidence=0.9 if provider_label == "balldontlie" else 0.75,
        data=ctx,
        status=STATUS_OK,
        status_detail=f"{len(lines)} stat lines via {provider_label}",
    )


def _balldontlie_provider(topic: str) -> dict:
    ctx = gather_balldontlie_context(topic)
    ctx["topic"] = topic
    if not ctx.get("connected"):
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_UNAVAILABLE,
            status_detail="BALLDONTLIE not configured",
        )
    sig = _stats_signal_from_context(ctx, provider_label="balldontlie")
    if sig.get("active"):
        return sig
    return make_signal(
        connected=True,
        active=False,
        score=0,
        data=ctx,
        status=STATUS_INACTIVE,
        status_detail="BALLDONTLIE: no match",
    )


def _scraper_provider(topic: str) -> dict:
    domains = detect_stat_domains(topic)
    if not domains:
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="Not an NBA/NFL stats topic",
        )
    ctx = _gather_scraper_context(topic)
    ctx["topic"] = topic
    return _stats_signal_from_context(ctx, provider_label="scrapers")


def _merge_context_lines(*contexts: dict[str, Any]) -> dict[str, Any]:
    lines: list[str] = []
    sources: list[dict[str, Any]] = []
    for ctx in contexts:
        if ctx.get("lines"):
            lines.extend(ctx["lines"])
            sources.append(ctx)
    return {"connected": True, "lines": lines[:12], "sources": sources}


def gather_stats_context(topic: str) -> dict[str, Any]:
    """Fetch stats using API-first chain."""
    order = os.getenv(
        "STATS_PROVIDER_ORDER", "balldontlie,api_sports,nflverse,pybaseball,scrapers"
    ).lower()
    collected: list[dict[str, Any]] = []
    for name in order.split(","):
        key = name.strip().lower()
        if key == "balldontlie":
            ctx = gather_balldontlie_context(topic)
            if ctx.get("lines"):
                collected.append(ctx)
        elif key == "api_sports":
            ctx = gather_api_sports_context(topic)
            if ctx.get("lines"):
                collected.append(ctx)
        elif key == "nflverse":
            ctx = gather_nflverse_context(topic)
            if ctx.get("lines"):
                collected.append(ctx)
        elif key == "pybaseball":
            ctx = gather_pybaseball_context(topic)
            if ctx.get("lines"):
                collected.append(ctx)
        elif key == "scrapers" and scrape_enabled():
            ctx = _gather_scraper_context(topic)
            if ctx.get("lines"):
                collected.append(ctx)
    if collected:
        merged = _merge_context_lines(*collected)
        merged["topic"] = topic
        return merged
    if scrape_enabled():
        return _gather_scraper_context(topic)
    return {"connected": False, "sources": [], "lines": []}


def get_stats_context_signal(topic: str):
    domains = detect_stat_domains(topic)
    if not domains:
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="Not an NBA/NFL/MMA stats topic — try player/team names",
        )

    from apis.pro_sports_stats_api import nflverse_provider, pybaseball_provider

    def _api_sports_provider(topic: str) -> dict:
        ctx = gather_api_sports_context(topic)
        ctx["topic"] = topic
        return _stats_signal_from_context(ctx, provider_label="api_sports")

    providers = []
    order = os.getenv("STATS_PROVIDER_ORDER", "balldontlie,api_sports,nflverse,pybaseball,scrapers")
    for name in order.split(","):
        key = name.strip().lower()
        if key == "balldontlie":
            providers.append(("balldontlie", _balldontlie_provider))
        elif key == "api_sports":
            providers.append(("api_sports", _api_sports_provider))
        elif key == "nflverse":
            providers.append(("nflverse", nflverse_provider))
        elif key == "pybaseball":
            providers.append(("pybaseball", pybaseball_provider))
        elif key == "scrapers" and scrape_enabled():
            providers.append(("scrapers", _scraper_provider))

    if not providers:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_UNAVAILABLE,
            status_detail="No stats providers enabled",
        )

    try:
        return chain_signal(topic, providers, min_score=1)
    except Exception as exc:
        from apis.signal_contract import classify_exception

        status, detail = classify_exception(exc)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
