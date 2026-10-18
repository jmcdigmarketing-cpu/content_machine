"""#1301: a preview is a prediction - the call and the why. #1304: from the game, kept, scored.

The operator, 2026-10-18: "predictions are still lazy". A preview on the idea menu was the
matchup, the kickoff and the records ("Cowboys 3-3 at Packers 4-1"); the script was left to find
a take of its own, and the take check held drafts that had none. Asked "a call + the why", one
cheap model call per preview reads the matchup, the board's line and this week's headlines that
name either side, and returns who wins and one reason.

#1304 (wave 111): this week's feeds name few of the teams, so the why was often the season
records. For an NFL or NBA game ESPN's free summary supplies the matchup projection, the injury
report, each side's leaders and the last five results as more lines. Every call is kept in
`data/preview_calls.json`, keyed by the event: it is made once (a second menu build reuses it -
the menu had grown to 10-13 s), and once the game is final ESPN's result scores it - `ops
predictions` prints "Calls: N of M right". UFC calls are kept but not scored (no result source).

The reason may only use what it was given: a number in it that no supplied line carries drops
the reason (the call stays). Fail-open - no model, no call, the preview reads as it did.
`PREVIEW_CALLS=false` turns it off; the suite pins it off.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.predictions.calls")

CALLS_FILE = os.path.join(DATA_DIR, "preview_calls.json")
_LOCK = threading.Lock()
_SUMMARY_PATHS = {"nfl": "football/nfl", "nba": "basketball/nba"}
_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/summary"
_SETTLE = timedelta(hours=3)  # a game is scored this long after its start, once ESPN says final
_INJURY_STATUSES = ("out", "doubtful", "questionable")

# Live 2026-10-18 the first wording gave "Experts backing Giants" (a reason that is not one)
# and "49ers are 5-0 at home" (a season record, said as a home one).
_SYSTEM = (
    "You make one prediction for a short sports video. Use only the lines you are given - no "
    "stat, injury or result that is not in them. A record is the season record; say home or "
    "road only if a line does. The why is a reason in the game itself - form, a matchup, an "
    "injury, a record - never that experts, analysts or bettors pick a side. Reply as JSON: "
    '{"call": "<who wins, at most 8 words>", "why": "<one reason, at most 18 words, from the '
    'lines>"}. With no such reason in the lines, give the call and an empty why.'
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_MAX_HEADLINES = 6


def enabled() -> bool:
    return os.getenv("PREVIEW_CALLS", "true").strip().lower() not in ("0", "false", "no", "off")


def _named(topic: str, headlines: list[str]) -> list[str]:
    """This week's headlines that name a side of `topic`."""
    from apis.topic_tokens import names_any, subject_markers, subject_terms

    markers = subject_markers(subject_terms(topic, limit=6))
    if not markers:
        return []
    return [h for h in headlines if h and names_any(h, markers)][:_MAX_HEADLINES]


def _summary(league: str, event_id: str) -> dict[str, Any]:
    """ESPN's game summary for an NFL/NBA event, or {} (free, no key; fail-open)."""
    path = _SUMMARY_PATHS.get(str(league or "").lower())
    if not path or not event_id:
        return {}
    try:
        import requests

        resp = requests.get(_SUMMARY_URL.format(path=path), params={"event": event_id}, timeout=8)
        body = resp.json() if resp.status_code == 200 else {}
        return body if isinstance(body, dict) else {}
    except Exception as exc:
        logger.debug("ESPN summary for %s %s unread: %s", league, event_id, exc)
        return {}


def _team_names(summary: dict[str, Any]) -> dict[str, str]:
    comps = ((summary.get("header") or {}).get("competitions") or [{}])[0] or {}
    out: dict[str, str] = {}
    for side in comps.get("competitors") or []:
        team = side.get("team") or {}
        if team.get("id"):
            out[str(team["id"])] = str(team.get("displayName") or "")
    return out


def game_lines(summary: dict[str, Any]) -> list[str]:
    """The summary as lines a call may use: the matchup projection, the injury report (out,
    doubtful, questionable), each side's leaders and its last five results (#1304)."""
    lines: list[str] = []
    names = _team_names(summary)
    pred = summary.get("predictor") or {}
    sides = [pred.get("homeTeam") or {}, pred.get("awayTeam") or {}]
    try:
        best = max(sides, key=lambda s: float(s.get("gameProjection") or 0))
        team = names.get(str(best.get("id") or ""), "")
        if team and best.get("gameProjection"):
            lines.append(f"ESPN's matchup predictor: {team} {best['gameProjection']}% to win")
    except (TypeError, ValueError):
        pass
    for block in summary.get("injuries") or []:
        team = str((block.get("team") or {}).get("displayName") or "")
        hurt = [
            f"{(i.get('athlete') or {}).get('displayName')} ({i.get('status')})"
            for i in block.get("injuries") or []
            if str(i.get("status") or "").lower() in _INJURY_STATUSES
            and (i.get("athlete") or {}).get("displayName")
        ][:3]
        if team and hurt:
            lines.append(f"{team} injury report: {', '.join(hurt)}")
    for block in summary.get("leaders") or []:
        team = str((block.get("team") or {}).get("displayName") or "")
        for cat in (block.get("leaders") or [])[:2]:
            top = (cat.get("leaders") or [{}])[0] or {}
            who = (top.get("athlete") or {}).get("displayName")
            if team and who and top.get("displayValue"):
                label = str(cat.get("displayName") or cat.get("name") or "").lower()
                lines.append(f"{team} {label} leader: {who}, {top['displayValue']}")
    for block in summary.get("lastFiveGames") or []:
        team = str((block.get("team") or {}).get("displayName") or "")
        form = " ".join(str(e.get("gameResult") or "") for e in block.get("events") or [])
        if team and form.strip():
            lines.append(f"{team} last five: {form.strip()}")
    return lines


def _prompt(bet: Any, detail: dict[str, Any], headlines: list[str], game: list[str]) -> str:
    lines = [f"Event: {bet.topic}", f"When and records: {bet.rationale}"]
    if detail.get("line"):
        total = f" (total {detail['total']})" if detail.get("total") else ""
        lines.append(f"Betting line: {detail['line']}{total}")
    if game:
        lines.append("From the game:")
        lines.extend(f"- {g}" for g in game)
    if headlines:
        lines.append("Headlines this week:")
        lines.extend(f"- {h}" for h in headlines)
    return "\n".join(lines)


# Live 2026-10-18 (wave 111): "Rams are 2-3 at home against Cardinals 1-4 on road" - no
# supplied line said home or road.
_VENUE = re.compile(
    r"\b(at home|home record|on the road|on road|road record|away from home)\b", re.I
)


def _grounded(why: str, prompt: str) -> str:
    """The reason, or "" when it carries a number no supplied line does, or a home or road
    claim no supplied line makes."""
    supplied = set(_NUMBER.findall(prompt))
    if any(n not in supplied for n in _NUMBER.findall(why)):
        return ""
    if _VENUE.search(why) and not _VENUE.search(prompt):
        return ""
    return why


def _names_a_side(call: str, topic: str) -> bool:
    """A call names one of the event's sides; "No prediction available" (live, 2026-10-18,
    the Moicano card) does not."""
    from apis.topic_tokens import names_any, subject_markers, subject_terms

    markers = subject_markers(subject_terms(topic, limit=6))
    return bool(markers) and names_any(call, markers)


def _detail(topic: str) -> dict[str, Any]:
    try:
        from core.seasonal_calendar import game_details

        return dict(game_details(topic) or {})
    except Exception:
        return {}


def _one(bet: Any, detail: dict[str, Any], headlines: list[str]) -> dict[str, str] | None:
    from core.llm_router import complete_json

    game = game_lines(_summary(str(detail.get("league") or ""), str(detail.get("event_id") or "")))
    prompt = _prompt(bet, detail, _named(bet.topic, headlines), game)
    try:
        payload = complete_json(prompt, tier="cheap", system=_SYSTEM, temperature=0.4,
                                max_tokens=200, stage="preview_call")  # fmt: skip
    except Exception as exc:
        logger.debug("preview call for %r failed: %s", bet.topic, exc)
        return None
    call = str((payload or {}).get("call") or "").strip().rstrip(".")
    if not call or not _names_a_side(call, bet.topic):
        return None
    why = _grounded(str((payload or {}).get("why") or "").strip().rstrip("."), prompt)
    return {"call": call, "why": why, "line": str(detail.get("line") or "")}


def _load() -> dict[str, Any]:
    try:
        with open(CALLS_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(CALLS_FILE) or ".", exist_ok=True)
        tmp = f"{CALLS_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
        os.replace(tmp, CALLS_FILE)
    except OSError as exc:
        logger.debug("preview calls not saved: %s", exc)


def _key(topic: str, detail: dict[str, Any]) -> str:
    if detail.get("event_id"):
        return f"{detail.get('league') or 'event'}:{detail['event_id']}"
    return f"{topic.strip().lower()}|{str(detail.get('date') or '')[:10]}"


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def preview_calls(
    previews: list[Any],
    *,
    headlines: list[str] | Callable[[], list[str]],
    now: datetime | None = None,
) -> dict[str, dict[str, str]]:
    """{topic: {call, why, line}} for each preview with a call - from the ledger when the event
    already has one, else made side by side and kept. `headlines` may be a function, called only
    when a call is still to be made."""
    if not previews or not enabled():
        return {}
    with _LOCK:
        store = _load()
    calls = store.setdefault("calls", {})
    out: dict[str, dict[str, str]] = {}
    todo: list[tuple[Any, dict[str, Any], str]] = []
    for bet in previews:
        detail = _detail(bet.topic)
        key = _key(bet.topic, detail)
        entry = calls.get(key) or {}
        if entry.get("call") and _names_a_side(str(entry["call"]), bet.topic):
            out[bet.topic] = {k: str(entry.get(k) or "") for k in ("call", "why", "line")}
        else:
            todo.append((bet, detail, key))
    if not todo:
        return out
    week = headlines() if callable(headlines) else headlines
    with ThreadPoolExecutor(max_workers=min(5, len(todo))) as pool:
        made = list(pool.map(lambda item: _one(item[0], item[1], week), todo))
    stamp = _now(now).isoformat(timespec="seconds")
    for (bet, detail, key), call in zip(todo, made, strict=True):
        if not call:
            continue
        out[bet.topic] = call
        calls[key] = {
            **call,
            "topic": bet.topic,
            "league": str(detail.get("league") or getattr(bet, "domain", "") or ""),
            "event_id": str(detail.get("event_id") or ""),
            "date": str(detail.get("date") or ""),
            "made": stamp,
        }
    with _LOCK:
        _save(store)
    return out


def _winner(summary: dict[str, Any]) -> str:
    """The winning side's name once ESPN calls the game final, else ""."""
    comps = ((summary.get("header") or {}).get("competitions") or [{}])[0] or {}
    if not ((comps.get("status") or {}).get("type") or {}).get("completed"):
        return ""
    for side in comps.get("competitors") or []:
        if side.get("winner") is True:
            return str((side.get("team") or {}).get("displayName") or "")
    return ""


def _when(raw: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def score_calls(*, now: datetime | None = None) -> int:
    """Score each kept NFL/NBA call whose game is final: right when the call names the winner.
    Returns how many were scored now. One ESPN request a game, once."""
    from apis.topic_tokens import names_any, subject_markers

    moment = _now(now)
    with _LOCK:
        store = _load()
    calls = store.get("calls") or {}
    scored = 0
    for entry in calls.values():
        if entry.get("result") or str(entry.get("league") or "") not in _SUMMARY_PATHS:
            continue
        start = _when(str(entry.get("date") or ""))
        if not entry.get("event_id") or start is None or moment < start + _SETTLE:
            continue
        winner = _winner(_summary(str(entry["league"]), str(entry["event_id"])))
        if not winner:
            continue
        right = names_any(str(entry.get("call") or ""), subject_markers([winner]))
        entry["result"] = {
            "winner": winner,
            "right": bool(right),
            "scored": moment.isoformat(timespec="seconds"),
        }
        scored += 1
    if scored:
        with _LOCK:
            _save(store)
    return scored


def scored_calls(*, days: int = 30, now: datetime | None = None) -> list[dict[str, Any]]:
    """The kept calls made in the last `days`, newest first (#991 reads the scored ones)."""
    since = _now(now) - timedelta(days=days)
    rows = []
    for entry in (_load().get("calls") or {}).values():
        made = _when(str(entry.get("made") or ""))
        if made is not None and made >= since:
            rows.append(entry)
    return sorted(rows, key=lambda e: str(e.get("made") or ""), reverse=True)


def calls_line(*, days: int = 30, now: datetime | None = None) -> str:
    """ "Calls: 7 of 10 right in the last 30 days (3 waiting on a result)", or ""."""
    rows = scored_calls(days=days, now=now)
    if not rows:
        return ""
    done = [r for r in rows if r.get("result")]
    right = sum(1 for r in done if (r.get("result") or {}).get("right"))
    waiting = sum(
        1 for r in rows if not r.get("result") and str(r.get("league") or "") in _SUMMARY_PATHS
    )
    unscored = len(rows) - len(done) - waiting
    line = f"Calls: {right} of {len(done)} right in the last {days} days"
    extra = []
    if waiting:
        extra.append(f"{waiting} waiting on a result")
    if unscored:
        extra.append(f"{unscored} UFC or other, not scored")
    return line + (f" ({'; '.join(extra)})" if extra else "")


def call_text(call: dict[str, str]) -> str:
    """ "Packers win - Dallas allows the most deep completions" (the brief's call)."""
    text = str(call.get("call") or "")
    return f"{text} - {call['why']}" if call.get("why") else text


def call_line(call: dict[str, str]) -> str:
    """The menu's line: "Call: Packers win - Dallas allows ... (GB -3.5)"."""
    line = f" ({call['line']})" if call.get("line") else ""
    return f"Call: {call_text(call)}{line}"


def headlines_for(previews: list[Any]) -> list[str]:
    """This week's headlines from the feeds of each preview's league - fetched side by side."""
    from config.data_sources import domain_rss_feeds

    domains = sorted({str(getattr(bet, "domain", "") or "") for bet in previews} - {""})
    feeds: list[dict] = []
    for domain in domains:
        feeds.extend(domain_rss_feeds(domain))
    if not feeds:
        return []
    from core.best_bet import _fetch_feeds

    return [str(row.get("title") or "") for rows in _fetch_feeds(feeds) for row in rows[:25]]
