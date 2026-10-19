"""The competitor list: suggest, add, remove (#1120).

The outlier watch (#1063) needs three or more channels in the channel's own niches. The list
was one tech reviewer, edited by hand in `config/competitors/<channel>.json`, and nothing
helped fill it. `suggest` searches YouTube per niche and prints a shortlist - it adds
nothing; the operator approves each one with `add`.

Quota: a channel search is 100 units, a lookup by id or handle is 1. Both are refused when
they would eat into the units kept back for uploads (`COMPETITOR_SYNC_RESERVE_UNITS`).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.competitor_list")

SEARCH_UNITS = 100
LOOKUP_UNITS = 1
_UC_ID = re.compile(r"\bUC[0-9A-Za-z_-]{22}\b")
_HANDLE = re.compile(r"@[A-Za-z0-9._-]{3,30}")


def _path(channel_id: str) -> str:
    from config.competitors import competitors_config_path

    return competitors_config_path(channel_id)


def _read(channel_id: str) -> dict[str, Any]:
    try:
        with open(_path(channel_id), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"channel_id": channel_id, "youtube_channels": []}
    if not isinstance(data, dict):
        return {"channel_id": channel_id, "youtube_channels": []}
    if "youtube_channels" not in data:
        data["youtube_channels"] = list(data.get("channels") or [])
    return data


def _write(channel_id: str, data: dict[str, Any]) -> None:
    from config.competitors import get_competitor_channels

    path = _path(channel_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    get_competitor_channels.cache_clear()  # the sync reads the list through an lru_cache


def _rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in data.get("youtube_channels") or []:
        if isinstance(item, dict) and item.get("id"):
            out.append(item)
        elif isinstance(item, str):
            out.append({"id": item, "label": item})
    return out


def channel_ref(source: str) -> tuple[str, str]:
    """("id", "UC...") or ("handle", "@name") from an id, a handle or a channel URL."""
    text = str(source or "").strip()
    found = _UC_ID.search(text)
    if found:
        return "id", found.group(0)
    found = _HANDLE.search(text)
    if found:
        return "handle", found.group(0)
    return "", ""


def block_reason(units: int) -> str | None:
    """Why a Data API call of `units` must not run, or None. The upload reserve only -
    the per-sync cap is for the unattended sync, and this is a command the operator typed."""
    from analytics.competitor_sync import _reserve_units

    try:
        from apis.youtube_quota import get_usage_summary

        remaining = int(get_usage_summary().get("remaining") or 0)
    except Exception as exc:
        logger.debug("competitor list: quota not read: %s", exc)
        return None
    reserve = _reserve_units()
    if reserve and remaining < reserve + units:
        return (
            f"{remaining} YouTube units left today and {reserve} are kept for uploads - "
            f"this needs {units}. Try again tomorrow."
        )
    return None


def _spend(units: int) -> None:
    try:
        from apis.youtube_quota import record_usage

        record_usage(units=units, caller="competitors")
    except Exception as exc:
        logger.debug("competitor list: usage not recorded: %s", exc)


def resolve(service: Any, source: str) -> dict[str, str] | None:
    """{"id", "title"} for an id, a handle or a URL - one lookup - or None."""
    kind, value = channel_ref(source)
    if not kind or service is None:
        return None
    query = {"id": value} if kind == "id" else {"forHandle": value}
    try:
        _spend(LOOKUP_UNITS)
        reply = service.channels().list(part="snippet", **query).execute()
    except Exception as exc:
        logger.warning("competitor lookup failed for %s: %s", value, exc)
        return None
    items = reply.get("items") or []
    if not items:
        return None
    title = str((items[0].get("snippet") or {}).get("title") or value)
    return {"id": str(items[0].get("id") or ""), "title": title}


def add(channel_id: str, youtube_channel_id: str, label: str, *, note: str = "") -> bool:
    """Put one channel on the list. False when it is already there or the id is not one."""
    if not _UC_ID.fullmatch(str(youtube_channel_id or "")):
        return False
    data = _read(channel_id)
    rows = _rows(data)
    if any(str(r.get("id")) == youtube_channel_id for r in rows):
        return False
    row = {"id": youtube_channel_id, "label": str(label or youtube_channel_id).strip()}
    if note:
        row["note"] = note
    data["youtube_channels"] = [*rows, row]
    _write(channel_id, data)
    return True


def remove(channel_id: str, key: str) -> list[str]:
    """Take channels off the list by id or by a word of the label. Returns the labels removed."""
    needle = str(key or "").strip().lower()
    if not needle:
        return []
    data = _read(channel_id)
    rows = _rows(data)
    gone = [
        r
        for r in rows
        if str(r.get("id", "")).lower() == needle or needle in str(r.get("label", "")).lower()
    ]
    if not gone:
        return []
    data["youtube_channels"] = [r for r in rows if r not in gone]
    _write(channel_id, data)
    return [str(r.get("label") or r.get("id")) for r in gone]


def list_lines(channel_id: str) -> list[str]:
    rows = _rows(_read(channel_id))
    if not rows:
        return ["  (none) - py -m scripts.ops competitors suggest"]
    return [f"  {r.get('label') or r['id']}  [{r['id']}]" for r in rows]


def niche_queries(channel_id: str, *, limit: int = 4) -> list[str]:
    """One search per niche the channel sorts its videos into: its sports, then gaming."""
    try:
        from config.paths import ROOT_DIR

        with open(os.path.join(ROOT_DIR, "config", "playlists.json"), encoding="utf-8") as fh:
            rows = json.load(fh).get(channel_id) or []
    except (OSError, ValueError, AttributeError):
        rows = []
    if isinstance(rows, dict):
        rows = rows.get("playlists") or []
    named = [r for r in rows if isinstance(r, dict) and r.get("name")]
    # "news", not "shorts": a search for "UFC shorts" returns channels *named* UFC Shorts -
    # clip reposts - where "UFC news" returns the commentary channels a topic can come from.
    sports = [f"{str(r['name']).split('/')[0].strip()} news" for r in named if r.get("domain")]
    gaming = any("gaming" in f"{r.get('name')} {r.get('parent')}".lower() for r in named)
    queries = sports[: limit - 1] if gaming else sports[:limit]
    if gaming:
        queries.append("gaming news")
    return list(dict.fromkeys(queries))[:limit]


def niche_keys(channel_id: str) -> dict[str, list[str]]:
    """{search: that niche's own words} (#1127). "NFL news" brought back the league's channel
    and four soccer "football news" channels; a candidate must use one of the niche's words."""
    try:
        from config.paths import ROOT_DIR

        with open(os.path.join(ROOT_DIR, "config", "playlists.json"), encoding="utf-8") as fh:
            rows = json.load(fh).get(channel_id) or []
    except (OSError, ValueError, AttributeError):
        return {}
    if isinstance(rows, dict):
        rows = rows.get("playlists") or []
    out: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        keys = [str(k).lower() for k in row.get("keys") or [] if str(k).strip()]
        if row.get("domain"):
            out[f"{str(row['name']).split('/')[0].strip()} news"] = keys
        elif str(row.get("name")).lower() == "gaming":
            out["gaming news"] = keys
    return out


def on_niche(text: str, keys: list[str] | None) -> bool:
    """True when `text` uses one of the niche's words as a whole word (or no words are set)."""
    if not keys:
        return True
    lowered = f" {str(text or '').lower()} "
    return any(re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", lowered) for key in keys)


def from_shortlist(channel_id: str, name: str) -> dict[str, Any] | None:
    """A kept shortlist row by its channel name - exact first, then the only partial match -
    so `competitors add --name "Full Mount MMA"` needs no id pasted."""
    wanted = " ".join(str(name or "").lower().split())
    if not wanted:
        return None
    _searched, rows = load_shortlist(channel_id)
    exact = [r for r in rows if str(r.get("title", "")).lower() == wanted]
    if exact:
        return exact[0]
    partial = [r for r in rows if wanted in str(r.get("title", "")).lower()]
    return partial[0] if len(partial) == 1 else None


def suggest(
    channel_id: str,
    service: Any,
    *,
    queries: list[str] | None = None,
    per_query: int = 10,
    keys: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Channels YouTube returns for each niche search, minus the ones already listed.

    Adds nothing. Each row: id, title, about (first words of the description), query.
    """
    if service is None:
        return []
    have = {str(r.get("id")) for r in _rows(_read(channel_id))}
    out: list[dict[str, Any]] = []
    for query in queries if queries is not None else niche_queries(channel_id):
        try:
            _spend(SEARCH_UNITS)
            reply = (
                service.search()
                .list(part="snippet", type="channel", q=query, maxResults=per_query)
                .execute()
            )
        except Exception as exc:
            logger.warning("competitor search failed for %r: %s", query, exc)
            continue
        for item in reply.get("items") or []:
            snippet = item.get("snippet") or {}
            cid = str((item.get("id") or {}).get("channelId") or snippet.get("channelId") or "")
            if not cid or cid in have:
                continue
            title = " ".join(str(snippet.get("title") or cid).split())
            description = " ".join(str(snippet.get("description") or "").split())
            if not on_niche(f"{title} {description}", (keys or {}).get(query)):
                continue  # #1127: off the niche (soccer under an NFL search)
            have.add(cid)
            about = description[:80]
            out.append({"id": cid, "title": title, "about": about, "query": query})
    return _with_sizes(service, out)


MIN_SUBSCRIBERS = 1000


def _with_sizes(service: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Subscribers and video count for every candidate in one lookup, so the shortlist can be
    judged; channels under `MIN_SUBSCRIBERS` are dropped and the rest sorted largest first
    within each search. A failed lookup leaves the list as it was."""
    if not rows:
        return rows
    try:
        _spend(LOOKUP_UNITS)
        reply = (
            service.channels()
            .list(part="statistics", id=",".join(r["id"] for r in rows[:50]), maxResults=50)
            .execute()
        )
    except Exception as exc:
        logger.warning("competitor sizes not read: %s", exc)
        return rows
    stats = {str(i.get("id")): i.get("statistics") or {} for i in reply.get("items") or []}
    if not stats:
        return rows
    sized: list[dict[str, Any]] = []
    for row in rows:
        found = stats.get(row["id"]) or {}
        try:
            subs = int(found.get("subscriberCount") or 0)
            videos = int(found.get("videoCount") or 0)
        except (TypeError, ValueError):
            subs, videos = 0, 0
        if subs >= MIN_SUBSCRIBERS:
            sized.append(dict(row, subscribers=subs, videos=videos))
    order = {query: n for n, query in enumerate(dict.fromkeys(r["query"] for r in rows))}
    return sorted(sized, key=lambda r: (order[r["query"]], -r["subscribers"]))


def _count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    return f"{n / 1000:.0f}K" if n >= 1000 else str(n)


SHORTLIST_DAYS = 7


def _shortlist_path(channel_id: str) -> str:
    import config.competitors as competitors

    return os.path.join(competitors.DATA_DIR, f"competitor_shortlist_{channel_id}.json")


def save_shortlist(channel_id: str, rows: list[dict[str, Any]]) -> None:
    """Keep the shortlist: a search is 100 units a niche, and the operator reads it later."""
    from datetime import date

    try:
        path = _shortlist_path(channel_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"searched": date.today().isoformat(), "rows": rows}, fh, indent=2)
    except OSError as exc:
        logger.warning("competitor shortlist not saved: %s", exc)


def load_shortlist(channel_id: str, *, today: Any = None) -> tuple[str, list[dict[str, Any]]]:
    """(day searched, rows) for a shortlist `SHORTLIST_DAYS` old or newer, minus channels
    added since; ("", []) when there is none."""
    from datetime import date

    try:
        with open(_shortlist_path(channel_id), encoding="utf-8") as fh:
            data = json.load(fh)
        searched = date.fromisoformat(str(data.get("searched") or ""))
    except (OSError, ValueError, AttributeError):
        return "", []
    if ((today or date.today()) - searched).days > SHORTLIST_DAYS:
        return "", []
    have = {str(r.get("id")) for r in _rows(_read(channel_id))}
    rows = [r for r in data.get("rows") or [] if isinstance(r, dict) and r.get("id") not in have]
    return searched.isoformat(), rows


def suggestion_lines(channel_id: str, rows: list[dict[str, Any]]) -> list[str]:
    """The shortlist, each with the command that approves it."""
    if not rows:
        return ["  No new channels found."]
    lines: list[str] = []
    query = None
    for row in rows:
        if row["query"] != query:
            query = row["query"]
            lines.append(f"  Search: {query}")
        about = f" - {row['about']}" if row.get("about") else ""
        size = ""
        if row.get("subscribers"):
            size = (
                f" ({_count(int(row['subscribers']))} subscribers, "
                f"{int(row.get('videos') or 0):,} videos)"
            )
        lines.append(f"    {row['title']}{size}{about}")
        lines.append(
            f"      py -m scripts.ops competitors add --source {row['id']} "
            f'--name "{row["title"]}" --channel {channel_id}'
        )
    lines.append("  Nothing was added. Run the add line for each channel you want watched.")
    return lines
