"""Earnings-calendar signal (MoneyWise / finance) — upcoming earnings as a catalyst.

A company reporting earnings in the next few weeks is a high-interest short-form
finance topic, so a near-term earnings date scores high. Free via Finnhub's
earnings-calendar endpoint (the same free-tier FINNHUB_API_KEY the finnhub signal
uses).

Contract (apis/CLAUDE.md): returns the make_signal() shape, is thread-safe, and
NEVER raises (returns an error-status signal instead). Adds NO internal cache —
register_signals._fetch_one caches every signal call. Domain-gated to finance
(apis/register_signals._DOMAIN_SIGNALS).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import requests  # type: ignore[import-untyped]

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)

_BASE = "https://finnhub.io/api/v1"
_HORIZON_DAYS = 21


def _api_key() -> str:
    return os.getenv("FINNHUB_API_KEY", "").strip()


def _ticker_guess(topic: str) -> str | None:
    """First 1-5 uppercase token that looks like a ticker (e.g. AAPL, TSLA)."""
    m = re.search(r"\b([A-Z]{1,5})\b", topic or "")
    return m.group(1) if m else None


def _days_until(date_str: str) -> int | None:
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return (day - datetime.now(timezone.utc).date()).days


def get_earnings_signal(topic: str) -> dict:
    """Score a finance topic by how soon the company's next earnings date is."""
    key = _api_key()
    if not key:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set FINNHUB_API_KEY (free tier at finnhub.io) for earnings",
        )

    ticker = _ticker_guess(topic)
    if not ticker:
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="No ticker symbol in topic",
        )

    try:
        today = datetime.now(timezone.utc).date()
        resp = requests.get(
            f"{_BASE}/calendar/earnings",
            params={
                "from": today.isoformat(),
                "to": (today + timedelta(days=_HORIZON_DAYS)).isoformat(),
                "symbol": ticker,
                "token": key,
            },
            timeout=10,
        )
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)

    if resp.status_code != 200:
        status, detail = classify_http(resp.status_code, resp.text)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)

    try:
        rows = (resp.json() or {}).get("earningsCalendar") or []
    except ValueError:
        rows = []

    upcoming = []
    for row in rows:
        days = _days_until(str(row.get("date") or ""))
        if days is not None and days >= 0:
            upcoming.append((days, row))

    if not upcoming:
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail=f"No earnings for {ticker} in the next {_HORIZON_DAYS}d",
        )

    upcoming.sort(key=lambda x: x[0])
    days, row = upcoming[0]
    # Sooner = hotter: same-week earnings peak the score, tapering out to the horizon.
    score = max(40.0, 95.0 - days * 2.5)
    return make_signal(
        connected=True,
        active=True,
        score=float(round(score, 1)),
        confidence=0.8,
        status=STATUS_OK,
        status_detail=f"{ticker} earnings in {days}d ({row.get('date')})",
        data={
            "symbol": ticker,
            "date": row.get("date"),
            "days_until": days,
            "eps_estimate": row.get("epsEstimate"),
        },
    )
