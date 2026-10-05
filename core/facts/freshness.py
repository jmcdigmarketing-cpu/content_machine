"""Settled or fresh: does this topic need the operator's articles? (#964)

Operator, 2026-10-05: a known topic should need no paste - "vs if a game has just come out
it may be harder to get accurate and useful info so i would paste articles. obviously not
hardcoded". Nothing told the two apart: the facts prompt asked the same way every time, and
recent-news research (#899) ran only when no fact named the topic's event.

`assess` decides from what the run already found - no list of franchises or sports:

- **fresh** when any of: a release date in the last `FRESH_DAYS` (default 30) - Wikidata's
  (#963) or RAWG's; the main name has no Wikipedia article, or one created in the last
  `FRESH_DAYS`; `FRESH_NEWS_BURST` (default 3) or more Google News headlines named it in 48
  hours; or event research ran because no fact named the topic's event (#899).
- **settled** otherwise: an article that has stood for years, nothing released lately, a
  quiet news day.

`attach_fresh_research` then gives a fresh topic the recent-news research (Wikipedia, Google
News and web search over seven days) for its main name, without waiting for a miss. The
verdict is stored as `features["research"]` and read by the facts prompt (#965) and
`ops auto-research` (#967). Never raises.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

from apis.cache_manager import build_key, get_cached, set_cache
from core.logging import get_logger

logger = get_logger("core.facts.freshness")

_NEWS_CACHE_TTL = 60 * 60


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default)) or default))
    except ValueError:
        return default


def fresh_days() -> int:
    return _env_int("FRESH_DAYS", 30)


def _today() -> date:
    return date.today()


def _day(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _entities(signals: dict[str, Any]) -> list[dict[str, Any]]:
    sig = (signals or {}).get("entity_research") or {}
    data = sig.get("data") if isinstance(sig, dict) else None
    entities = data.get("entities") if isinstance(data, dict) else None
    return [e for e in entities or [] if isinstance(e, dict)]


def _rawg_releases(signals: dict[str, Any]) -> list[tuple[str, str]]:
    sig = (signals or {}).get("rawg") or {}
    data = sig.get("data") if isinstance(sig, dict) and sig.get("active") else None
    out: list[tuple[str, str]] = []
    for game in data if isinstance(data, list) else []:
        if isinstance(game, dict) and game.get("name") and game.get("released"):
            out.append((str(game["name"]), str(game["released"])))
    return out[:3]


def main_name(topic: str, signals: dict[str, Any], event_report: dict[str, Any] | None) -> str:
    """The name the topic is mainly about: the first one looked up, else the event's."""
    for entity in _entities(signals):
        if entity.get("label") or entity.get("name"):
            return str(entity.get("label") or entity.get("name"))
    if event_report and event_report.get("name"):
        return str(event_report["name"])
    from core.event_coverage import event_name

    return event_name(topic)


def assess(
    topic: str,
    signals: dict[str, Any] | None,
    *,
    event_report: dict[str, Any] | None = None,
    news_count: int | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """{"need": "settled"|"fresh", "why": [...], "main", "looked_up", "news_48h"}."""
    signals = dict(signals or {})
    today = today or _today()
    window = fresh_days()
    fresh: list[str] = []
    settled: list[str] = []
    entities = _entities(signals)
    main = main_name(topic, signals, event_report)

    if event_report:
        fresh.append(f"no fact named '{event_report.get('name', '')}' before research")
    releases = [(str(e.get("label") or e.get("name")), str(e.get("released") or ""))
                for e in entities if e.get("released")]  # fmt: skip
    for label, released in releases + _rawg_releases(signals):
        day = _day(released)
        if day is None:
            continue
        age = (today - day).days
        if -window <= age <= window:
            when = f"{age} day(s) ago" if age >= 0 else f"in {-age} day(s)"
            fresh.append(f"{label} released {released} ({when})")
        else:
            settled.append(f"{label} released {released}")
    if entities:
        first = entities[0]
        label = str(first.get("label") or first.get("name") or main)
        created = _day(first.get("created"))
        if not first.get("has_article"):
            fresh.append(f"no Wikipedia article for {label} yet")
        elif created and (today - created).days <= window:
            fresh.append(f"{label}'s Wikipedia article was created {created.isoformat()}")
        elif created:
            settled.append(f"{label} has had a Wikipedia article since {created.year}")
    burst = _env_int("FRESH_NEWS_BURST", 3)
    if news_count is not None:
        if news_count >= burst:
            fresh.append(f"{news_count} news headline(s) named {main} in 48 hours")
        else:
            settled.append(f"{news_count} news headline(s) in 48 hours")
    return {
        "need": "fresh" if fresh else "settled",
        "why": fresh or settled,
        "main": main,
        "looked_up": len(entities),
        "news_48h": news_count,
    }


def recent_news_count(name: str) -> int:
    """Google News headlines naming `name` in the last 48 hours; 0 on an outage."""
    if not (name or "").strip():
        return 0
    key = build_key("fresh_news_48h", name.lower())
    cached = get_cached(key)
    if isinstance(cached, int):
        return cached
    try:
        from core.event_research import google_news_headlines

        count = len(google_news_headlines(name, window="2d"))
    except Exception as exc:
        logger.debug("news count failed for %r: %s", name, exc)
        return 0
    set_cache(key, count, ttl_seconds=_NEWS_CACHE_TTL)
    return count


def attach_fresh_research(
    signals: dict[str, Any] | None, *, topic: str, event_report: dict[str, Any] | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(signals, verdict). A fresh topic whose event research has not run gets it now, for
    its main name. Keyless lookups run only when the who's-who lookup is on (#963)."""
    base = dict(signals or {})
    try:
        from core.event_research import SIGNAL_NAME, research_enabled, research_event
        from core.facts.entity_lookup import research_enabled as lookups_enabled

        main = main_name(topic, base, event_report)
        news = recent_news_count(main) if lookups_enabled() else None
        verdict = assess(topic, base, event_report=event_report, news_count=news, today=_today())
        if verdict["need"] != "fresh" or SIGNAL_NAME in base or not research_enabled():
            return base, verdict
        found = research_event(main)
        lines = list(found.get("lines") or [])
        verdict["deeper"] = {"name": main, "lines": len(lines),
                             "sources": list(found.get("sources") or [])}  # fmt: skip
        if lines:
            from apis.signal_contract import STATUS_OK, make_signal

            base[SIGNAL_NAME] = make_signal(
                connected=True,
                active=True,
                score=0,
                confidence=0.6,
                status=STATUS_OK,
                status_detail=f"Fresh-topic research: {len(lines)} line(s) naming {main!r}",
                data={"name": main, "lines": lines, "sources": list(found.get("sources") or [])},
            )
        return base, verdict
    except Exception as exc:  # a verdict is a notice; the run goes on without it
        logger.debug("freshness skipped: %s", exc)
        return base, {"need": "settled", "why": [], "main": "", "looked_up": 0}


def script_mode(verdict: dict[str, Any] | None, fact_lines: int) -> str:
    """#339: "unconfirmed" for a fresh topic with fewer than `UNCONFIRMED_MAX_FACTS` (5)
    verified fact lines - the script labels what is not confirmed instead of dropping it -
    else "standard"."""
    if not verdict or verdict.get("need") != "fresh":
        return "standard"
    return "unconfirmed" if fact_lines < _env_int("UNCONFIRMED_MAX_FACTS", 5) else "standard"


def mode_note(verdict: dict[str, Any] | None) -> str:
    """`ops batch-review`: a draft written in unconfirmed mode says so."""
    if not verdict or verdict.get("script_mode") != "unconfirmed":
        return ""
    return (
        "written in unconfirmed mode (fresh topic, thin facts) - claims are labelled, not dropped"
    )


def review_note(verdict: dict[str, Any] | None, *, pasted: int) -> str:
    """#965: a fresh draft nobody pasted facts for, named in `ops batch-review`."""
    if not verdict or verdict.get("need") != "fresh" or pasted > 0:
        return ""
    why = "; ".join(verdict.get("why") or []) or "a new topic"
    return f"fresh topic ({why}) and no facts pasted - paste a link and regenerate if thin"


def verdict_line(verdict: dict[str, Any] | None) -> str:
    """ "Fresh: Ghost of Yōtei released 2026-10-01 (4 day(s) ago)" / "Settled: ..." """
    if not verdict or not verdict.get("need"):
        return ""
    why = "; ".join(verdict.get("why") or []) or "nothing new found"
    return f"{str(verdict['need']).capitalize()}: {why}"
