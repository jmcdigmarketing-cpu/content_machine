"""Who's who: the people, teams and games a topic names, looked up on every run (#963).

Operator, 2026-10-05: "i shouldnt have to fact intake such a known topic" - what team LeBron
is on. Nothing looked them up. Event research (#899) reads Wikipedia only when the topic
names an event no fact covers; the key-facts prompt asked the operator for "Who holds what
NOW"; and the script prompt forbids specifics that are not in VERIFIED FACTS, so a current
team was pasted by hand or left out. Overnight and batch drafts never get a paste.

For up to four names (`names_for`: Title-Case runs in the topic and the angle, plus seeded
or learned athlete names, which a lower-case topic still finds):

1. **Wikidata** resolves the name - aliases too, so "Wemby" is Victor Wembanyama - and reads
   the claims that go stale: current team (P54) and position held (P39) with no end date,
   head coach (P286), a game's release date (P577), developer (P178) and platforms (P400).
   Lines carry the day they were read: "LeBron James - current team: ... (Wikidata, as of
   2026-10-05)". Structured data, so signal tier, like Tapology or RAWG.
2. **Wikipedia** - the intro of the entity's English article (Wikidata's sitelink, or a
   search whose title names it) and the day the article was created (#964 reads it). Prose,
   so web tier.

Keyless, parallel, bounded by `ENTITY_RESEARCH_DEADLINE_S`; a find is cached a day, a miss
not at all (#899's rule). Rides as the `entity_research` signal with score 0, so no score
moves. `ENTITY_RESEARCH_ENABLED=false` turns it off; the suite pins it off.
"""

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import date
from typing import Any

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import STATUS_OK, make_signal
from core.logging import get_logger

logger = get_logger("core.facts.entity_lookup")

SIGNAL_NAME = "entity_research"
MAX_NAMES = 4
_CACHE_TTL = 24 * 60 * 60
_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_WIKI_API = "https://en.wikipedia.org/w/api.php"
_HEADERS = {"User-Agent": "ContentMachine/1.0 (entity lookup)"}
_TIMEOUT = 8
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_INTRO_SENTENCES = 3
# Claims that hold an item (a team, a studio) and are current while they have no end date.
_CURRENT_ITEM_CLAIMS = (
    ("P54", "current team"),
    ("P39", "position held"),
    ("P286", "head coach"),
)
_ITEM_CLAIMS = (("P178", "developer"), ("P400", "platforms"))
_END_TIME = "P582"
# What #964 reads about each entity; the lines themselves travel separately.
_SUMMARY_KEYS = (
    "name",
    "label",
    "description",
    "released",
    "created",
    "has_article",
    "wikipedia_title",
)
_MAX_VALUES = 4


def research_enabled() -> bool:
    from core.providers import flag_enabled

    return flag_enabled("ENTITY_RESEARCH_ENABLED", default=True)


def _deadline_s() -> float:
    try:
        return max(0.5, min(60.0, float(os.getenv("ENTITY_RESEARCH_DEADLINE_S", "10") or 10)))
    except ValueError:
        return 10.0


def _today() -> str:
    return date.today().isoformat()


def names_for(topic: str, *, angle: str = "") -> list[str]:
    """Up to `MAX_NAMES` names to look up: Title-Case names in the topic, then the angle,
    then any seeded or learned athlete name (lower-case topics have no Title-Case runs)."""
    from apis.topic_scorer import sport_names_in
    from apis.topic_tokens import title_phrases

    out: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        name = re.sub(r"['’]s$", "", name.strip())
        key = name.lower()
        if len(key) < 3 or key in seen:
            return
        # "LeBron" after "LeBron James" adds nothing.
        if any(key in s.split() or key == s for s in seen):
            return
        seen.add(key)
        out.append(name)

    for text in (topic, angle):
        for phrase in title_phrases(text or "", max_words=5, connectors=True):
            add(phrase)
    for name in sport_names_in(f"{topic} {angle}"):
        add(name)
    return out[:MAX_NAMES]


def _get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    if resp.status_code != 200:
        return {}
    data = resp.json()
    return data if isinstance(data, dict) else {}


def _names_it(name: str, text: str) -> bool:
    from core.event_coverage import covered

    return covered(name, [text])


def _search_wikidata(name: str) -> dict[str, Any] | None:
    hits = _get_json(
        _WIKIDATA_API,
        {"action": "wbsearchentities", "search": name, "language": "en", "type": "item",
         "limit": "5", "format": "json"},
    ).get("search") or []  # fmt: skip
    for hit in hits:
        if not isinstance(hit, dict) or not hit.get("id"):
            continue
        if "disambiguation" in str(hit.get("description") or "").lower():
            continue
        matched = str((hit.get("match") or {}).get("text") or hit.get("label") or "")
        if _names_it(name, matched) or _names_it(name, str(hit.get("label") or "")):
            return hit
    return None


def _current(claim: dict[str, Any]) -> bool:
    return claim.get("rank") != "deprecated" and not (claim.get("qualifiers") or {}).get(_END_TIME)


def _item_id(claim: dict[str, Any]) -> str:
    value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
    return str(value.get("id") or "") if isinstance(value, dict) else ""


def _time_value(claim: dict[str, Any]) -> str:
    value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
    text = str(value.get("time") or "") if isinstance(value, dict) else ""
    match = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return ""
    year, month, day = match.groups()
    if month == "00":
        return year
    return f"{year}-{month}" if day == "00" else f"{year}-{month}-{day}"


def _labels(ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    entities = _get_json(
        _WIKIDATA_API,
        {"action": "wbgetentities", "ids": "|".join(ids[:50]), "props": "labels",
         "languages": "en", "format": "json"},
    ).get("entities") or {}  # fmt: skip
    out: dict[str, str] = {}
    for qid, entity in entities.items():
        label = (((entity or {}).get("labels") or {}).get("en") or {}).get("value")
        if label:
            out[str(qid)] = str(label)
    return out


def _wikidata(name: str, today: str) -> dict[str, Any]:
    hit = _search_wikidata(name)
    if not hit:
        return {}
    qid = str(hit["id"])
    entity = (
        _get_json(
            _WIKIDATA_API,
            {"action": "wbgetentities", "ids": qid, "props": "labels|descriptions|claims|sitelinks",
             "languages": "en", "sitefilter": "enwiki", "format": "json"},
        ).get("entities") or {}
    ).get(qid) or {}  # fmt: skip
    label = str(((entity.get("labels") or {}).get("en") or {}).get("value") or hit.get("label"))
    description = str(
        ((entity.get("descriptions") or {}).get("en") or {}).get("value")
        or hit.get("description")
        or ""
    )
    claims = entity.get("claims") or {}
    wanted: dict[str, list[str]] = {}
    for prop, _what in _CURRENT_ITEM_CLAIMS:
        wanted[prop] = [_item_id(c) for c in claims.get(prop) or [] if _current(c)]
    for prop, _what in _ITEM_CLAIMS:
        wanted[prop] = [
            _item_id(c) for c in claims.get(prop) or [] if c.get("rank") != "deprecated"
        ]
    ids = [i for values in wanted.values() for i in values if i]
    names = _labels(list(dict.fromkeys(ids)))
    released = min((v for v in (_time_value(c) for c in claims.get("P577") or []) if v), default="")

    stamp = f"(Wikidata, as of {today})"
    lines: list[str] = []
    who = f"{label} ({description})" if description else label
    for prop, what in _CURRENT_ITEM_CLAIMS:
        values = [names[i] for i in wanted[prop] if i in names][:_MAX_VALUES]
        if values:
            lines.append(f"{who} - {what}: {', '.join(values)} {stamp}")
    if released:
        made = [names[i] for i in wanted["P178"] if i in names][:_MAX_VALUES]
        on = [names[i] for i in wanted["P400"] if i in names][:_MAX_VALUES]
        line = f"{label} - released {released}"
        if made:
            line += f" by {', '.join(made)}"
        if on:
            line += f"; platforms: {', '.join(on)}"
        lines.append(f"{line} {stamp}")
    if not lines and description:
        lines.append(f"{label}: {description} {stamp}")
    title = str(((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title") or "")
    return {
        "qid": qid,
        "label": label,
        "description": description,
        "lines": lines,
        "released": released,
        "title": title,
    }


def _wikipedia_title(name: str) -> str:
    hits = (
        _get_json(
            _WIKI_API,
            {"action": "query", "list": "search", "srsearch": name, "srlimit": "3",
             "format": "json"},
        ).get("query") or {}
    ).get("search") or []  # fmt: skip
    return next(
        (str(h["title"]) for h in hits if h.get("title") and _names_it(name, str(h["title"]))), ""
    )


def _wikipedia(title: str) -> dict[str, Any]:
    """{lines, created} for one article: the intro's first sentences, the creation day."""
    pages = (
        _get_json(
            _WIKI_API,
            {"action": "query", "prop": "extracts|revisions", "exintro": "1",
             "explaintext": "1", "redirects": "1", "rvprop": "timestamp", "rvdir": "newer",
             "rvlimit": "1", "titles": title, "format": "json"},
        ).get("query") or {}
    ).get("pages") or {}  # fmt: skip
    for page in pages.values():
        if not isinstance(page, dict) or "missing" in page:
            continue
        extract = str(page.get("extract") or "")
        sentences = [s.strip() for s in _SENTENCE.split(extract) if len(s.strip()) > 20]
        revisions = page.get("revisions") or []
        created = str((revisions[0] or {}).get("timestamp") or "")[:10] if revisions else ""
        return {"lines": sentences[:_INTRO_SENTENCES], "created": created}
    return {"lines": [], "created": ""}


def lookup_entity(name: str) -> dict[str, Any]:
    """Everything known about one name - never raises; a find is cached a day."""
    key = build_key(SIGNAL_NAME, name.lower())
    cached = get_cached(key)
    if isinstance(cached, dict) and "wikidata_lines" in cached:
        return cached
    today = _today()
    found: dict[str, Any] = {
        "name": name,
        "label": name,
        "description": "",
        "wikidata_lines": [],
        "wikipedia_title": "",
        "wikipedia_lines": [],
        "created": "",
        "released": "",
        "has_article": False,
    }
    try:
        data = _wikidata(name, today)
        if data:
            found.update(
                label=data["label"],
                description=data["description"],
                wikidata_lines=data["lines"],
                released=data["released"],
            )
        title = (data or {}).get("title") or _wikipedia_title(found["label"])
        if title:
            article = _wikipedia(title)
            found.update(
                wikipedia_title=title,
                wikipedia_lines=article["lines"],
                created=article["created"],
                has_article=bool(article["lines"]),
            )
    except Exception as exc:  # a lookup is a bonus; the run goes on without it
        logger.debug("entity lookup failed for %r: %s", name, exc)
        return found
    if found["wikidata_lines"] or found["wikipedia_lines"]:
        set_cache(key, found, ttl_seconds=_CACHE_TTL)
    return found


def lookup_entities(names: list[str]) -> dict[str, Any]:
    """{entities, seconds} for every name, in order, under the deadline."""
    started = time.monotonic()
    results: dict[str, dict[str, Any]] = {}
    if names:
        executor = ThreadPoolExecutor(max_workers=min(len(names), MAX_NAMES))
        futures = {executor.submit(lookup_entity, name): name for name in names}
        try:
            for future in as_completed(futures, timeout=_deadline_s()):
                try:
                    results[futures[future]] = future.result()
                except Exception as exc:
                    logger.debug("entity lookup skipped %r: %s", futures[future], exc)
        except FuturesTimeout:
            logger.debug("entity lookup deadline reached")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    return {
        "entities": [results[n] for n in names if n in results],
        "seconds": round(time.monotonic() - started, 1),
    }


def attach_entity_research(
    signals: dict[str, Any] | None, *, topic: str, angle: str = ""
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """(signals, report). The report is None when the lookup is off or names nothing."""
    base = dict(signals or {})
    try:
        if not research_enabled():
            return base, None
        names = names_for(topic, angle=angle)
        if not names:
            return base, None
        looked = lookup_entities(names)
        entities = looked["entities"]
        wikidata = [line for e in entities for line in e.get("wikidata_lines") or []]
        wikipedia = [line for e in entities for line in e.get("wikipedia_lines") or []]
        sources = [s for s, lines in (("Wikidata", wikidata), ("Wikipedia", wikipedia)) if lines]
        if wikidata or wikipedia:
            base[SIGNAL_NAME] = make_signal(
                connected=True,
                active=True,
                score=0,
                confidence=0.7,
                status=STATUS_OK,
                status_detail=f"Who's who: {len(wikidata) + len(wikipedia)} line(s) for "
                + ", ".join(names),
                data={
                    "names": names,
                    "as_of": _today(),
                    "wikidata_lines": wikidata,
                    "wikipedia_lines": wikipedia,
                    "entities": [{k: e.get(k) for k in _SUMMARY_KEYS} for e in entities],
                },
            )
        report = {
            "names": names,
            "lines": len(wikidata) + len(wikipedia),
            "wikidata": len(wikidata),
            "wikipedia": len(wikipedia),
            "sources": sources,
            "seconds": looked["seconds"],
            # #967: kept so `ops auto-research` can count which lines a claim cited.
            "kept_lines": (wikidata + wikipedia)[:12],
        }
        return base, report
    except Exception as exc:  # never in the way of a run
        logger.debug("entity research skipped: %s", exc)
        return base, None


def report_line(report: dict[str, Any] | None) -> str:
    """One line for the run output and the facts prompt."""
    if not report:
        return ""
    names = ", ".join(report.get("names") or [])
    if not report.get("lines"):
        return f"Who's who: nothing found for {names}"
    return (
        f"Who's who: {report['lines']} line(s) for {names} "
        f"({', '.join(report.get('sources') or [])}, {report.get('seconds', 0)}s)"
    )
