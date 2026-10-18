"""#1042 (the operator, 2026-10-18: "3-second card after the hook"): owned visuals for previews.

A game preview's footage is gameplay; nothing on screen said who plays whom or how they stand.
For an NFL or NBA game not yet played, ESPN's free game summary gives each side's record, the
line, ESPN's projection and the injury report. They are drawn as a full-frame 1080x1920 card
that shows for CARD_SECONDS right after the opening sentence (from the word timings) while the
voice goes on - an overlay in the render's graph, under the captions.

Fail-open: no word timings, no summary, a game already started, or not a fixture ("A at B") -
no card, and the render command is byte-identical. `MATCHUP_CARD=false` turns it off; the
suite pins it off.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("video.matchup_card")

CARD_SECONDS = 3.0
_SIZE = (1080, 1920)
_MARGIN = 60
_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"
_LEAGUES = {"nfl": "football/nfl", "nba": "basketball/nba"}


def enabled() -> bool:
    return os.getenv("MATCHUP_CARD", "true").strip().lower() not in ("0", "false", "no", "off")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_ref(topic: str) -> tuple[str, str] | None:
    """(league, ESPN event id) for a game: the calls ledger first, else one scoreboard read."""
    key = topic.strip().lower()
    try:
        from core.predictions import calls

        for entry in (calls._load().get("calls") or {}).values():
            if str(entry.get("topic") or "").strip().lower() == key and entry.get("event_id"):
                return str(entry.get("league") or ""), str(entry["event_id"])
    except Exception as exc:
        logger.debug("matchup card: ledger unread: %s", exc)
    try:
        import requests

        for league, path in _LEAGUES.items():
            board = requests.get(_SCOREBOARD.format(path=path), timeout=8).json()
            for event in board.get("events") or []:
                if str(event.get("name") or "").strip().lower() == key:
                    return league, str(event.get("id") or "")
    except Exception as exc:
        logger.debug("matchup card: scoreboard unread: %s", exc)
    return None


def _summary_for(topic: str) -> dict[str, Any]:
    ref = _event_ref(topic)
    if not ref or not ref[1]:
        return {}
    from core.predictions.calls import _summary

    return _summary(ref[0], ref[1])


def matchup_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """The card's facts from ESPN's summary: each side's name and record, the line, ESPN's
    projection, the first player out; {} when the summary names no two sides."""
    comps = ((summary.get("header") or {}).get("competitions") or [{}])[0] or {}
    sides: dict[str, dict[str, str]] = {}
    names: dict[str, str] = {}
    for side in comps.get("competitors") or []:
        team = side.get("team") or {}
        short = str(
            team.get("shortDisplayName") or team.get("name") or team.get("displayName") or ""
        )
        record = next((str(r.get("summary")) for r in side.get("record") or []
                       if r.get("type") == "total" and r.get("summary")), "")  # fmt: skip
        sides[str(side.get("homeAway") or "")] = {"name": short, "record": record}
        if team.get("id"):
            names[str(team["id"])] = short
        if team.get("displayName"):
            names[str(team["displayName"])] = short
    if not sides.get("home") or not sides.get("away"):
        return {}
    out: dict[str, Any] = {"away": sides["away"], "home": sides["home"],
                           "date": str(comps.get("date") or "")}  # fmt: skip
    pick = next((p for p in summary.get("pickcenter") or [] if p.get("details")), None)
    if pick:
        out["line"] = str(pick["details"])
    pred = summary.get("predictor") or {}
    try:
        best = max([pred.get("homeTeam") or {}, pred.get("awayTeam") or {}],
                   key=lambda s: float(s.get("gameProjection") or 0))  # fmt: skip
        if best.get("gameProjection") and names.get(str(best.get("id"))):
            pct = round(float(best["gameProjection"]))
            out["projection"] = f"{names[str(best['id'])]} {pct}%"
    except (TypeError, ValueError):
        pass
    for block in summary.get("injuries") or []:
        team = names.get(str((block.get("team") or {}).get("displayName") or ""), "")
        hurt = next((i for i in block.get("injuries") or []
                     if str(i.get("status") or "").lower() == "out"), None)  # fmt: skip
        if hurt and (hurt.get("athlete") or {}).get("displayName"):
            out["injury"] = f"{hurt['athlete']['displayName']} ({team})" if team else (
                hurt["athlete"]["displayName"])  # fmt: skip
            break
    return out


def card_lines(m: dict[str, Any]) -> list[str]:
    if not m:
        return []
    away, home = m["away"], m["home"]
    lines = [
        f"{away['name'].upper()} {away['record']}".strip(),
        "at",
        f"{home['name'].upper()} {home['record']}".strip(),
    ]
    if m.get("line"):
        lines.append(f"Line: {m['line']}")
    if m.get("projection"):
        lines.append(f"ESPN: {m['projection']} to win")
    if m.get("injury"):
        lines.append(f"Out: {m['injury']}")
    return lines


def draw_card(lines: list[str], dest: str, *, channel_id: str | None = None) -> str:
    """A 1080x1920 card: the matchup large, the rest below, on the channel's dark ground."""
    from PIL import Image, ImageDraw

    from assets.thumbnail_compose import _font

    img = Image.new("RGB", _SIZE, (12, 16, 22))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 560), (_SIZE[0], 572)], fill=(255, 196, 0))
    y = 640
    for index, line in enumerate(lines):
        big = index in (0, 2)
        size = 118 if big else (64 if index == 1 else 70)
        font = _font(size)
        # Live 2026-10-18: "Out: Benjamin St-Juste (Packers)" ran off both edges at 70 px.
        while draw.textlength(line, font=font) > _SIZE[0] - 2 * _MARGIN and size > 30:
            size -= 4
            font = _font(size)
        width = draw.textlength(line, font=font)
        draw.text(((_SIZE[0] - width) / 2, y), line, font=font, fill=(255, 255, 255))
        y += 170 if big else 110
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    img.save(dest)
    return dest


def first_sentence_end(words: list[dict] | None) -> float | None:
    """When the first sentence is said: the end of the first word that closes one."""
    for word in words or []:
        text = str(word.get("word") or "").strip()
        if text.endswith((".", "!", "?")):
            end = word.get("end")
            if end is None:
                return None
            try:
                return round(float(end), 2)
            except (TypeError, ValueError):
                return None
    return None


def _started(m: dict[str, Any]) -> bool:
    try:
        when = datetime.fromisoformat(str(m.get("date") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return when <= _now()


def card_for_render(
    topic: str, channel_id: str | None, words: list[dict] | None, dest: str
) -> tuple[str, tuple[float, float]] | None:
    """(card path, (start, end)) for a coming game's preview, else None. `dest` is named
    after the video (like its .lower_thirds.ass), so two renders in one folder never share it."""
    if not enabled():
        return None
    from core.facts.event_dates import fixture_sides

    if not fixture_sides(topic):
        return None
    start = first_sentence_end(words)
    if start is None:
        return None
    try:
        m = matchup_from_summary(_summary_for(topic))
    except Exception as exc:
        logger.debug("matchup card: summary unread: %s", exc)
        return None
    if not m or _started(m) or not (m.get("line") or m.get("projection")):
        return None
    path = draw_card(card_lines(m), dest, channel_id=channel_id)
    return path, (start, round(start + CARD_SECONDS, 2))
