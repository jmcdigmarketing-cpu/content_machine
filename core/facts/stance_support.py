"""The facts that back the operator's stance, counted - and looked for when there are none (#1095).

Run 125 ("Chargers Hopeium going into week 5") asked for reasons for hope; its research was the
topic's own web search and the news for the event name, so the facts were the 0-4 record and the
losses. Wave 68 told the writer to make the case for hope from verified facts, and wave 69's idea
check may not add one - with no fact to give, the script can only say where things stand.

For a hope or plan run this counts the fact lines that back the stance (`stance_support` on the
run record and the facts preview) and, when fewer than two do, makes one stance search
(`apis.web_search_api.search_recent`: keyed provider chain, cached, never raises) and keeps the
results that name the subject and back the stance, as web research. Neutral and take runs are
untouched. `STANCE_RESEARCH=false` keeps the count and skips the search.
"""

from __future__ import annotations

import os
import re
from typing import Any

from apis.topic_tokens import names_any, search_query, subject_markers, subject_terms
from apis.web_search_api import search_recent
from core.logging import get_logger

logger = get_logger("core.facts.stance_support")

_HOPE = "hope"
_PLAN = "plan"
# Phrases that carry a reason for optimism - a return, a high, a streak, a rank near the top.
_BACKS = {
    _HOPE: re.compile(
        r"\b(?:return(?:s|ed|ing)?|back from|activated|cleared to|healthy|career[- ]high|"
        r"season[- ]high|leads? the (?:league|nfl|nba|nhl|mlb|afc|nfc)|league[- ]leading|"
        r"top[- ](?:3|5|10|three|five|ten)|ranks? (?:1st|2nd|3rd|4th|5th|first|second|third)|"
        r"win(?:ning)? streak|improv\w*|upgrade\w*|breakout|on pace|personal best|undefeated|"
        r"bounce[- ]back|rebound\w*|first win|upset|good news|best (?:start|game|performance))",
        re.I,
    ),
    # What has to happen - the needs, the schedule left, the odds.
    _PLAN: re.compile(
        r"\b(?:needs? to|must|has to|have to|remaining (?:schedule|games)|games? left|"
        r"weeks? left|next (?:\d+|two|three|four|five|six) games|playoff (?:odds|chances|picture)|"
        r"path to|to make the playoffs|strength of schedule)\b",
        re.I,
    ),
}
_SEARCH_WORDS = {_HOPE: "positives good news", _PLAN: "what needs to change"}
_LABEL = {_HOPE: "reasons for hope", _PLAN: "what has to happen"}
_MIN_SUPPORT = 2
_MAX_ADDED = 6
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_BULLET = re.compile(r"^\s*(?:[-*•→]|\d+[.)])\s*")


def stance_lines(lines: list[str], intent: str) -> list[str]:
    """The lines that back a hope or plan idea, in order; [] for any other intent."""
    pattern = _BACKS.get(intent)
    if pattern is None:
        return []
    return [line for line in lines if pattern.search(line or "")]


def _enabled() -> bool:
    return os.getenv("STANCE_RESEARCH", "true").strip().lower() not in ("0", "false", "no", "off")


def _fact_pool(signals: dict[str, Any], key_facts: list[str] | None) -> list[str]:
    from core.signal_facts import format_signal_facts

    out: list[str] = []
    for raw in format_signal_facts(signals).splitlines():
        line = _BULLET.sub("", raw).strip()
        if line and not line.endswith(":"):
            out.append(line)
    return [*[str(f) for f in key_facts or [] if str(f).strip()], *out]


def _result_lines(results: list[dict], markers: list[str], intent: str) -> list[str]:
    found: list[str] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        parts = [str(row.get("title") or "").strip()]
        parts += _SENTENCE.split(str(row.get("snippet") or row.get("content") or "").strip())
        for part in parts:
            if part and part not in found and (not markers or names_any(part, markers)):
                found.append(part)
    return stance_lines(found, intent)


def attach_stance_research(
    signals: dict[str, Any] | None,
    *,
    intent: str,
    topic: str,
    angle: str = "",
    key_facts: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(signals, report). The report is {} for an intent with no stance to back. Never raises."""
    base = dict(signals or {})
    if intent not in _BACKS:
        return base, {}
    report: dict[str, Any] = {"intent": intent, "lines": 0, "of": 0, "searched": False, "added": 0}
    try:
        pool = _fact_pool(base, key_facts)
        support = stance_lines(pool, intent)
        report.update(lines=len(support), of=len(pool))
        if len(support) >= _MIN_SUPPORT or not _enabled():
            return base, report
        # The subject by name ("Los Angeles Chargers"), not the operator's slang ("Hopeium").
        subject = next(iter(subject_terms(topic)), "") or search_query(topic)
        query = f"{subject} {_SEARCH_WORDS[intent]}".strip()
        report["searched"] = True
        try:
            results = search_recent(query, days=14)
        except Exception as exc:  # the search is a bonus; the count stands
            logger.debug("stance search failed for %r: %s", query, exc)
            return base, report
        markers = subject_markers(subject_terms(topic) or subject_terms(angle))
        added = [line for line in _result_lines(results, markers, intent) if line not in pool]
        added = added[:_MAX_ADDED]
        if not added:
            return base, report
        from apis.signal_contract import STATUS_OK, make_signal

        current = base.get("web_research")
        raw = current.get("data") if isinstance(current, dict) else None
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        lines = [*list(data.get("lines") or []), *added]
        base["web_research"] = make_signal(
            connected=True,
            active=True,
            score=0,
            confidence=0.6,
            status=STATUS_OK,
            status_detail=f"Web research: {len(lines)} line(s), {len(added)} for the stance",
            data={**data, "lines": lines, "urls": list(data.get("urls") or [])},
        )
        report.update(added=len(added), lines=len(support) + len(added), of=len(pool) + len(added))
        return base, report
    except Exception as exc:  # fail-open, like every research pass
        logger.debug("stance research skipped: %s", exc)
        return base, report


def stance_note(report: dict[str, Any] | None) -> str:
    """The facts-preview line for the stance count, or "" (#1095)."""
    if not report or report.get("intent") not in _LABEL:
        return ""
    intent = str(report["intent"])
    label = _LABEL[intent]
    if not report.get("lines"):
        searched = " (a search found none)" if report.get("searched") else ""
        what = "a reason for hope" if intent == _HOPE else "about what has to happen"
        return (
            f"! no fact here is {what}{searched} - paste one at Fact N, or the script can only "
            "say where things stand"
        )
    return f"Facts for your {intent}: {report['lines']} of {report['of']} lines read as {label}"
