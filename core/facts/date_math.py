"""Date arithmetic: "18 months since" must match the dates it counts from (#551).

Grounding checks that a script's names and numbers appear in the facts; nothing checked the
arithmetic between them, so "it's been 18 months since the trade" passed when the facts date
the trade 8 months ago. `find_elapsed_mismatches` reads each elapsed-time phrase - "N
days/weeks/months/years since/ago/after/later/before", "for N years" - and checks it:

- against a date in the same sentence ("since 2019", "since March 2025") - always;
- against the facts: the lines holding a date (written out, ISO or a bare year) that share a
  topic word with the sentence (`apis/topic_tokens.content_tokens`). Flagged only when such a
  line exists and none of its dates fits.

A count fits within one unit, or a quarter of the span when that is more. Pure; never raises.
"""

from __future__ import annotations

import datetime
import re

from apis.topic_tokens import content_tokens
from core.facts.recency import _MONTH_RE, _MONTHS, _dates_in

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}  # fmt: skip
_COUNT = r"(\d{1,3}|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
_UNIT = r"(day|week|month|year)s?"
_ELAPSED = re.compile(
    rf"\b{_COUNT}\s+{_UNIT}\s+(since|ago|after|later|before)\b"
    rf"|\bfor\s+(?:the\s+(?:last|past)\s+)?{_COUNT}\s+{_UNIT}\b",
    re.I,
)
_SINCE_DATE = re.compile(
    rf"\bsince\s+(?:(?:({_MONTH_RE})\s+)?(?:\d{{1,2}},?\s+)?((?:19|20)\d{{2}}))\b", re.I
)
_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_DAYS = {"day": 1.0, "week": 7.0, "month": 30.44, "year": 365.25}
_UNIT_WORDS = {"day", "days", "week", "weeks", "month", "months", "year", "years", "ago",
               "since", "later", "after", "before"}  # fmt: skip


def _count(raw: str) -> int | None:
    raw = raw.lower()
    return int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw)


def _fits(claimed: int, actual: float) -> bool:
    return abs(claimed - actual) <= max(1.0, 0.25 * actual)


def _span(start: datetime.date, today: datetime.date, unit: str) -> float:
    if unit == "year":
        return today.year - start.year - ((today.month, today.day) < (start.month, start.day))
    if unit == "month":
        months = (today.year - start.year) * 12 + today.month - start.month
        return months - (today.day < start.day)
    return (today - start).days / _DAYS[unit]


def _fact_dates(line: str, today: datetime.date) -> list[tuple[datetime.date, bool]]:
    """(date, year only) for each date in a fact line."""
    found = [(d, False) for d in _dates_in(line, today.year)]
    for m in _ISO.finditer(line):
        try:
            found.append((datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), False))
        except ValueError:
            continue
    if not found:
        found = [(datetime.date(int(m.group(1)), 7, 1), True) for m in _YEAR.finditer(line)]
    return found


def _words(text: str) -> set[str]:
    return {t for t in content_tokens(text, min_len=3) if t not in _UNIT_WORDS and not t.isdigit()}


def _show(value: float) -> str:
    return f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"


def find_elapsed_mismatches(
    script: str, facts: str, *, today: datetime.date | None = None
) -> list[str]:
    """Elapsed-time phrases the dates do not support: '"ten years since" - 2019 gives 7'."""
    today = today or datetime.date.today()
    fact_lines = [line for line in (facts or "").splitlines() if line.strip()]
    found: list[str] = []
    for sentence in _SENTENCE.split(script or ""):
        for match in _ELAPSED.finditer(sentence):
            raw = match.group(1) or match.group(4)
            unit = (match.group(2) or match.group(5)).lower()
            claimed = _count(raw or "")
            if claimed is None:
                continue
            phrase = match.group(0)
            note = _check_sentence(sentence, claimed, unit, today) or _check_facts(
                sentence, claimed, unit, today, fact_lines
            )
            if note:
                found.append(f'"{phrase}" - {note}')
    return found


def _check_sentence(sentence: str, claimed: int, unit: str, today: datetime.date) -> str:
    match = _SINCE_DATE.search(sentence)
    if not match:
        return ""
    month = _MONTHS.get((match.group(1) or "").lower(), 0)
    if unit in ("day", "week") and not month:
        return ""
    start = datetime.date(int(match.group(2)), month or 1, 1)
    if unit == "year" and not month:
        actual: float = today.year - start.year
    else:
        actual = _span(start, today, unit)
    if actual < 0 or _fits(claimed, actual):
        return ""
    return f"{match.group(0).split(None, 1)[1]} gives {_show(actual)} {unit}(s)"


def _check_facts(
    sentence: str, claimed: int, unit: str, today: datetime.date, fact_lines: list[str]
) -> str:
    words = _words(sentence)
    if not words:
        return ""
    anchored: list[tuple[datetime.date, float]] = []
    for line in fact_lines:
        if not words & _words(line):
            continue
        for day, year_only in _fact_dates(line, today):
            if day > today or (year_only and unit != "year"):
                continue
            actual = (today.year - day.year) if year_only else _span(day, today, unit)
            anchored.append((day, actual))
    if not anchored or any(_fits(claimed, actual) for _day, actual in anchored):
        return ""
    day, actual = anchored[0]
    return f"the facts date it {day.isoformat()} ({_show(actual)} {unit}(s))"
