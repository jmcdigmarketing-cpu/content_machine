"""Drop self-contradictory future-dated "facts" from the corpus.

A live run grounded a script on a web-search line claiming a fighter "lost ... on
July 18" when the run date was June 23 — a *completed* event on a *future* date.
That's almost always a speculative/garbled source, and grounding will happily let
the model repeat it (grounding stops invention, not propagation of a bad source).

This is a narrow, high-precision guard: a line is dropped only when a future date
co-occurs with a completed-action verb (lost/won/signed/…). It does NOT touch
legitimate future-event previews ("the card is set for July 18"), which have no
past-tense claim. It cannot judge plausible-but-fake headlines — that's a
source-reputation problem, out of scope.
"""

from __future__ import annotations

import datetime
import re

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_RE = "|".join(_MONTHS)
# "July 18", "July 18, 2026", "18 July 2026"
_DATE_RE = re.compile(
    rf"\b(?:({_MONTH_RE})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?|(\d{{1,2}})\s+({_MONTH_RE})\s+(\d{{4}}))\b",
    re.IGNORECASE,
)
# Verbs that assert a *completed* event — a past claim on a future date is bogus.
_PAST_ACTION = re.compile(
    r"\b(lost|won|beat|beaten|defeated|knocked|signed|traded|fired|hired|"
    r"announced|released|launched|died|retired|scored|finished|avenged|"
    r"clinched|secured|completed|debuted|resigned|stepped down)\b",
    re.IGNORECASE,
)


def _dates_in(line: str, default_year: int) -> list[datetime.date]:
    """Parsed dates in a line; year-less dates use `default_year`."""
    resolved: list[datetime.date] = []
    for m in _DATE_RE.finditer(line):
        try:
            if m.group(1):  # "Month day[, year]"
                month = _MONTHS[m.group(1).lower()]
                day = int(m.group(2))
                year = int(m.group(3)) if m.group(3) else default_year
            else:  # "day Month year"
                day = int(m.group(4))
                month = _MONTHS[m.group(5).lower()]
                year = int(m.group(6))
            resolved.append(datetime.date(year, month, day))
        except (ValueError, KeyError):
            continue
    return resolved


def is_future_dated_claim(line: str, today: datetime.date) -> bool:
    """True iff the line asserts a completed action on a date after `today`.

    Year-less dates assume `today`'s year; a future month/day is treated as bogus
    only when paired with a past-action verb (keeps false positives low — legit
    future-event previews have no completed-action claim).
    """
    if not _PAST_ACTION.search(line):
        return False
    return any(d > today for d in _dates_in(line, today.year))


def drop_future_dated(text: str, today: datetime.date | None = None) -> tuple[str, list[str]]:
    """Remove contradictory future-dated past-event lines. Returns (kept_text, dropped)."""
    today = today or datetime.date.today()
    kept: list[str] = []
    dropped: list[str] = []
    for line in (text or "").splitlines():
        if line.strip() and is_future_dated_claim(line, today):
            dropped.append(line.strip())
        else:
            kept.append(line)
    return "\n".join(kept), dropped
