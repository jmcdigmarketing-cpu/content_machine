"""API-SPORTS MMA — fighter profiles + career records for UFC/MMA scripts.

Replaces the structured half of the retired Tapology scrape (`apis/tapology_api.py`,
Cloudflare-blocked since ~2026-07). Uses the **MMA host** (`v1.mma.api-sports.io`) with
the `API_SPORTS_KEY` already configured for `apis/api_sports_api.py`, which points at
the *football* host and queries `/teams` — meaningless for MMA.

**What this does and does not provide.** The free plan gates `/fights` to seasons
2022–2024, so upcoming fight cards are *not* available here; those come from RSS
(Sherdog, UFC.com, MMA Fighting) and NewsAPI via `ufc_context`. What does work live is
fighter identity: physicals (height/weight/reach) and career record (W-L-D, KO, SUB).

Three hazards drive the conservatism below, all observed live on 2026-08-14:

1. **Rate-limit masquerades as "not found."** The free tier allows 10 req/min and 100
   req/day, and when exceeded it returns **HTTP 200 with `results: 0`** and an
   `errors.rateLimit` string. Treating that as "no such fighter" is precisely the
   silent-failure mode this wave exists to remove, so `_api_error()` inspects the body
   and the signal reports `STATUS_RATE_LIMIT` (which `register_signals` already gives a
   cooldown) instead of a quiet empty result.
2. **Surname search returns the wrong person.** `search=Topuria` resolves to
   *Aleksandre* Topuria, not Ilia. Feeding that into a script would be exactly the fact
   contamination the vault cleanup just undid, so `_name_matches()` requires the
   surname to match and rejects a conflicting first name.
3. **Records are often absent.** Many fighters return `None` for record and physicals;
   only populated fields are emitted, and a fighter with nothing usable yields no line.

Fail-open throughout: any error returns an error-status signal, never raises
(`apis/CLAUDE.md`). No cache here — `register_signals._fetch_one` already caches.
"""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    STATUS_RATE_LIMIT,
    STATUS_UPSTREAM,
    classify_exception,
    make_signal,
)
from core.logging import get_logger

logger = get_logger("apis.mma_stats")

_BASE = os.getenv("API_SPORTS_MMA_BASE", "https://v1.mma.api-sports.io").rstrip("/")
_TIMEOUT = 12

# Free tier is 10 req/min: each fighter costs 2 calls (search + records), so cap the
# lookups per topic well under the ceiling and leave headroom for other signals.
_MAX_FIGHTERS = 2

_MMA_KEYWORDS = ("ufc", "mma", "bellator", "pfl", "octagon", "fight night", "ppv")

# Words that look like names in a topic but aren't.
_NOT_NAMES = frozenset(
    {
        "ufc",
        "mma",
        "pfl",
        "ppv",
        "the",
        "and",
        "for",
        "why",
        "how",
        "what",
        "who",
        "fight",
        "fights",
        "night",
        "card",
        "main",
        "event",
        "title",
        "belt",
        "champion",
        "rankings",
        "division",
        "divisional",
        "breakdown",
        "preview",
        "predictions",
        "prediction",
        "results",
        "highlights",
        "vs",
    }
)


def _key() -> str:
    return os.getenv("API_SPORTS_KEY", "").strip()


def is_mma_topic(topic: str) -> bool:
    lowered = (topic or "").lower()
    return any(k in lowered for k in _MMA_KEYWORDS)


def _api_error(payload: dict[str, Any]) -> str:
    """Return a failure reason from a 200 body, or "" when the response is genuinely fine.

    API-SPORTS reports rate limits and plan gates in `errors` while still returning 200.
    `errors` is `[]` on success but a dict when something went wrong.
    """
    errors = payload.get("errors")
    if not errors:
        return ""
    if isinstance(errors, dict):
        return "; ".join(f"{k}: {v}" for k, v in errors.items() if v)
    if isinstance(errors, list):
        return "; ".join(str(e) for e in errors if e)
    return str(errors)


def _get(path: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """One API call -> (response rows, error reason). Never raises."""
    try:
        resp = requests.get(
            f"{_BASE}{path}",
            headers={"x-apisports-key": _key()},
            params=params,
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        logger.debug("MMA stats request failed %s: %s", path, exc)
        return [], str(exc)

    if resp.status_code != 200:
        return [], f"HTTP {resp.status_code}"
    try:
        payload = resp.json()
    except ValueError as exc:
        return [], f"bad JSON: {exc}"

    reason = _api_error(payload)
    if reason:
        return [], reason
    rows = payload.get("response") or []
    return (rows if isinstance(rows, list) else []), ""


def extract_fighter_names(topic: str) -> list[str]:
    """Best-effort fighter names from a topic line.

    Prefers an explicit `A vs B` split; otherwise takes capitalised word runs. Returns
    the *full* candidate names — `_name_matches` needs the first name to reject the
    wrong Topuria.
    """
    text = (topic or "").strip()
    if not text:
        return []

    names: list[str] = []
    parts = re.split(r"\bv(?:s\.?|ersus)\b", text, flags=re.I)
    if len(parts) >= 2:
        for part in parts[:2]:
            # Strip event prefixes ("UFC 330 Makhachev" -> "Makhachev") and trailing
            # commentary after punctuation.
            cleaned = re.split(r"[:;,—\-]", part)[-1]
            cleaned = re.sub(r"\b(ufc|bellator|pfl)\s*\d*\b", " ", cleaned, flags=re.I)
            words = [
                w for w in re.findall(r"[A-Za-z'\-]{2,}", cleaned) if w.lower() not in _NOT_NAMES
            ]
            if words:
                names.append(" ".join(words[:3]))
    else:
        for run in re.findall(r"\b([A-Z][a-z'\-]+(?:\s+[A-Z][a-z'\-]+){0,2})", text):
            words = [w for w in run.split() if w.lower() not in _NOT_NAMES]
            if words:
                names.append(" ".join(words))

    out: list[str] = []
    for name in names:
        name = name.strip()
        if len(name) >= 3 and name.lower() not in {n.lower() for n in out}:
            out.append(name)
    return out[:_MAX_FIGHTERS]


def _name_matches(query: str, found: str) -> bool:
    """True when `found` is confidently the fighter named by `query`.

    Guards the wrong-person hazard: `search=Topuria` returns "Aleksandre Topuria", which
    must not satisfy a topic about "Ilia Topuria". Requires the surname to match, and
    if both sides give a first name, requires those to agree too.
    """
    q = re.findall(r"[a-z'\-]{2,}", (query or "").lower())
    f = re.findall(r"[a-z'\-]{2,}", (found or "").lower())
    if not q or not f:
        return False
    if q[-1] != f[-1]:  # surnames must agree
        return False
    if len(q) >= 2 and len(f) >= 2:
        # Compare given names; the API often carries a middle name ("Ian Machado Garry").
        return q[0] == f[0] or q[0] in f[:-1]
    return True


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in ("", "none", "null") else text


def _fighter_line(fighter: dict[str, Any], record: dict[str, Any]) -> str:
    """One verified-fact line, built only from fields that are actually present."""
    name = _clean(fighter.get("name"))
    if not name:
        return ""

    bits: list[str] = []
    total = record.get("total") or {}
    wins, losses, draws = total.get("win"), total.get("loss"), total.get("draw")
    if wins is not None and losses is not None:
        rec = f"{wins}-{losses}-{draws if draws is not None else 0}"
        finishes = []
        ko = (record.get("ko") or {}).get("win")
        sub = (record.get("sub") or {}).get("win")
        if ko:
            finishes.append(f"{ko} KO")
        if sub:
            finishes.append(f"{sub} SUB")
        bits.append(f"record {rec}" + (f" ({', '.join(finishes)})" if finishes else ""))

    for label, key in (("height", "height"), ("weight", "weight"), ("reach", "reach")):
        val = _clean(fighter.get(key))
        if val:
            bits.append(f"{label} {val}")

    if not bits:
        return ""
    return f"{name} — {', '.join(bits)} — API-SPORTS"


def gather_mma_stats(topic: str) -> dict[str, Any]:
    """Fighter facts for a topic. Returns lines + an explicit failure reason."""
    names = extract_fighter_names(topic)
    if not names:
        return {
            "connected": True,
            "lines": [],
            "fighters": [],
            "reason": "no fighter name in topic",
        }

    lines: list[str] = []
    fighters: list[dict[str, Any]] = []
    reason = ""

    for name in names:
        # Surname search: the API misses on some full names ("Ian Garry" -> 0 results)
        # but resolves the surname ("Garry" -> "Ian Machado Garry"). _name_matches then
        # rejects a wrong-person hit.
        surname = name.split()[-1]
        rows, err = _get("/fighters", {"search": surname})
        if err:
            reason = err
            break
        match = next((r for r in rows if _name_matches(name, _clean(r.get("name")))), None)
        if not match:
            continue

        record: dict[str, Any] = {}
        fighter_id = match.get("id")
        if fighter_id is not None:
            rec_rows, rec_err = _get("/fighters/records", {"id": str(fighter_id)})
            if rec_err:
                reason = rec_err
                break
            if rec_rows:
                record = rec_rows[0]

        line = _fighter_line(match, record)
        if line:
            lines.append(line)
            fighters.append({"name": _clean(match.get("name")), "id": fighter_id})

    return {
        "connected": True,
        "lines": lines,
        "fighters": fighters,
        "reason": reason,
        "source": "api_sports_mma",
    }


def get_mma_stats_signal(topic: str) -> dict:
    if not _key():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set API_SPORTS_KEY (api-sports.io)",
        )
    if not is_mma_topic(topic):
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="Not an MMA/UFC topic",
        )

    try:
        data = gather_mma_stats(topic)
        lines = data.get("lines") or []
        reason = str(data.get("reason") or "")

        if not lines and reason:
            # A rate limit or plan gate is a FAILURE, not "no match" — surface it so the
            # breaker and `ops reliability` can see it.
            lowered = reason.lower()
            if "ratelimit" in lowered or "rate limit" in lowered or "too many requests" in lowered:
                status = STATUS_RATE_LIMIT
            elif "plan" in lowered:
                status = STATUS_QUOTA
            else:
                status = STATUS_UPSTREAM
            return make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=f"API-SPORTS MMA: {reason[:120]}",
            )

        if not lines:
            return make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="API-SPORTS MMA: no fighter match",
                data=data,
            )

        return make_signal(
            connected=True,
            active=True,
            score=float(min(50 + len(lines) * 20, 90)),
            confidence=0.9,
            status=STATUS_OK,
            status_detail=f"API-SPORTS MMA: {len(lines)} fighter(s)",
            data=data,
        )
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
