import os
import re

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)
from core.logging import get_logger

logger = get_logger("apis.steam_api")


def steam_search_url(topic: str) -> str:
    from urllib.parse import quote_plus

    url = (
        "https://store.steampowered.com/api/storesearch/"
        f"?term={quote_plus(topic or '')}&l=english&cc=us"
    )
    key = os.getenv("STEAM_API_KEY", "").strip()
    if key:
        url += f"&key={quote_plus(key)}"
    return url


NEWS_URL = (
    "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
    "?appid={appid}&count=10&maxlength=200&format=json"
)
_PATCH_TITLE = re.compile(r"\b(?:patch|update|hotfix|hot fix|notes|changelog|season)\b", re.I)


def patch_notes(payload, *, limit: int = 3) -> list[dict]:
    """The developer's own update posts out of a GetNewsForApp reply, newest first (#1119).

    Kept: a post tagged `patchnotes`, or a developer announcement (`feed_type` 1) whose title
    names a patch, update, hotfix or season. Press coverage Steam syndicates is not a patch
    note. Each row: title, date (YYYY-MM-DD), url.
    """
    from datetime import datetime, timezone

    try:
        items = (payload.get("appnews") or {}).get("newsitems") or []
    except AttributeError:
        return []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split())
        tags = [str(t).lower() for t in item.get("tags") or []]
        official = item.get("feed_type") == 1
        if not title or not ("patchnotes" in tags or (official and _PATCH_TITLE.search(title))):
            continue
        try:
            day = datetime.fromtimestamp(int(item.get("date") or 0), tz=timezone.utc).date()
        except (TypeError, ValueError, OSError, OverflowError):
            continue
        out.append({"title": title, "date": day.isoformat(), "url": str(item.get("url") or "")})
    out.sort(key=lambda row: row["date"], reverse=True)
    return out[:limit]


def _fetch_patch_notes(appid) -> list[dict]:
    """One keyless request for the matched game. [] on any failure - the store result stands.
    Inside the signal call, so the registry's one cache covers it; no cache of its own."""
    try:
        response = requests.get(NEWS_URL.format(appid=int(appid)), timeout=6)
        if response.status_code != 200:
            return []
        return patch_notes(response.json())
    except Exception as exc:
        logger.debug("steam news for app %s failed: %s", appid, exc)
        return []


# Words a topic adds to a game's name that the store search then looks for in the name.
_STORE_NOISE = (
    "update",
    "updates",
    "patch",
    "hotfix",
    "season",
    "changes",
    "notes",
    "review",
    "news",
    "leak",
    "leaks",
    "trailer",
    "dlc",
)


def name_terms(topic: str) -> list[str]:
    """The game's name out of a typed topic, for a second look when the whole sentence finds
    nothing (#1119): "Hades II update" -> "Hades II". Words come from `apis.topic_tokens`."""
    from apis.topic_tokens import search_query, title_phrases

    text = str(topic or "").strip()
    terms = [search_query(text, drop=_STORE_NOISE, mode="entity")]
    terms.extend(title_phrases(text, connectors=True)[:1])
    seen = {text.lower(), ""}
    out: list[str] = []
    for term in terms:
        term = str(term or "").strip()
        if term.lower() not in seen:
            seen.add(term.lower())
            out.append(term)
    return out[:2]


def _relevant_items(payload, topic_tokens) -> list[dict]:
    from apis.rawg_api import _is_relevant

    items = payload.get("items", []) if isinstance(payload, dict) else []
    return [
        r for r in items if isinstance(r, dict) and _is_relevant(r.get("name") or "", topic_tokens)
    ]


def _second_look(topic: str, topic_tokens) -> list[dict]:
    """The store search again with the game's name alone. [] on any failure."""
    for term in name_terms(topic):
        try:
            response = requests.get(steam_search_url(term), timeout=6)
            if response.status_code != 200:
                continue
            found = _relevant_items(response.json(), topic_tokens)
        except Exception as exc:
            logger.debug("steam second look for %r failed: %s", term, exc)
            continue
        if found:
            return found
    return []


def get_steam_signal(topic):
    try:
        url = steam_search_url(topic)
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            status, detail = classify_http(response.status_code, response.text)
            return make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=detail,
            )

        # Steam's store search returns *something* for almost any string; keep only
        # results whose name is the topic's subject (the RAWG rule, run 98).
        from apis.rawg_api import _sig_tokens

        topic_tokens = set(_sig_tokens(topic or ""))
        results = _relevant_items(response.json(), topic_tokens)
        if not results:
            # #1119: the store matches the term against game names, so a topic with one
            # extra word ("Hades II update") found nothing. Ask again with the name alone.
            results = _second_look(topic or "", topic_tokens)

        if not results:
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.6,
                status=STATUS_INACTIVE,
                status_detail="No Steam results for topic",
            )

        results = [dict(r) for r in results[:5]]
        if results[0].get("id"):
            notes = _fetch_patch_notes(results[0]["id"])  # #1119: the game the topic names
            if notes:
                results[0]["patch_notes"] = notes
        return make_signal(
            connected=True,
            active=True,
            score=min(len(results) * 10, 100),
            confidence=0.7,
            data=results,
            status=STATUS_OK,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
